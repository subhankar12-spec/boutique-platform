# Monitoring and incident response

This lab includes Prometheus application metrics, versioned Grafana dashboards, Alertmanager, Loki and Grafana Alloy. It exercises the same alert-to-response workflow used in production while keeping the default stack affordable. External receivers are prepared; no real Slack messages or ServiceNow incidents have been sent.

## Start locally

From `boutique-platform`:

```sh
python monitoring/init-local.py
# First start the application using scripts/local-up.sh.
docker compose --env-file local/.env -f local/compose.yaml -f monitoring/compose.yaml up -d --build
bash monitoring/capture-local-logs.sh
```

The log capture process runs in the foreground; stop it with Ctrl-C. Start it in a second terminal. Alloy reads these files and ships them to Loki without a mounted Docker socket. Ports bind only to loopback: Grafana 8085, Prometheus 9090, Alertmanager 9093, mock receivers 18080. Grafana user is `admin`; retrieve the generated password locally from `monitoring/.secrets/grafana_password` and keep it out of chat, logs and Git. Admin password changes require Grafana's password-reset flow once its persistent database already exists. Do not use the mock receiver outside local tests; it is unauthenticated and ephemeral.

## Signals and routing

The provisioned Boutique dashboard shows service availability, request rate, error ratio, HTTP p95, JVM/frontend memory, firing alerts, incident backlog and logs, with an environment selector. Metrics labels contain bounded route templates; session IDs, request IDs and product IDs are never metric labels. Logs retain request IDs as log fields for investigations. Avoid putting credentials or personal data into application logs. Logs are retained for seven days by default; set disk quotas and review retention for your workload.

Kubernetes Prometheus discovers individual pods, so replicas do not share a counter stream behind a load-balanced Service. Namespace-scoped RBAC permits only pod discovery. Missing-target rules cover services with no running pods.

Prometheus rules detect unavailable services, sustained error ratio with a traffic floor, sustained latency, failed rule evaluation, failed Alertmanager delivery, and aged incident queues. Alertmanager groups by cluster, environment, service and alert name; warning alerts are inhibited when a matching critical alert fires. Repeated notifications are limited to four hours. Local mocks use one-second grouping delay, five-second grouping interval and one-minute repeats to make drills quick; Kubernetes uses thirty seconds, five minutes and four hours. All configured alerts go to Slack; critical **production** alerts also go to ServiceNow. Delivery failures and backlog should remain visible in Slack so a ServiceNow failure does not depend solely on ServiceNow for escalation. Maintenance silences must expire and record an owner/reason. The homelab has no on-call paging provider or external dead-man receiver configured.

## Slack activation

Create an incoming webhook for a dedicated alert channel using your Slack workspace's approved app process. Store its URL in your secret manager as `slack_webhook`; never commit it. Alertmanager reads a mounted secret file. Replace the local mock URL only when you intend to enable live notifications. Receiver tests supplied here use mocks.

## ServiceNow activation

Use a free ServiceNow developer instance with ITSM Incident Management for the homelab. It teaches incident creation, correlation, resolution, retry handling and least-privilege API access without an ITOM Event Management license. Developer instances can sleep/reset and are not production services.

Create a dedicated integration user with only the ACLs required to query/create/update integration-owned incidents. Do not give it admin. Set `SERVICENOW_URL` to the HTTPS instance base URL, `SERVICENOW_USERNAME` to that user and `servicenow_password` through the secret manager. `SERVICENOW_CLOSE_CODE` must match your instance's configured choice value, and required incident fields/business rules may require adapter adjustments. TLS certificate verification remains enabled. The Table API adapter uses Basic auth over HTTPS; a production deployment should prefer your organization's OAuth credential flow.

Default `SERVICENOW_MODE=table` queries `correlation_id` before creation and resolves the existing incident when the alert resolves. The key hashes fingerprint plus alert start time, so a new alert cycle gets a new incident. Table API lookup followed by insert **cannot guarantee exactly-once creation** during ambiguous timeouts/concurrent writes. For stronger deduplication, review `monitoring/servicenow/scripted-rest-resource.js`, create its unique indexed custom field and authenticated Scripted REST API, then set `SERVICENOW_MODE=scripted`. This reference script must be validated in your instance; it has not been remotely tested.

The bridge accepts only authenticated Alertmanager webhooks, persists them before acknowledging, retries with capped exponential backoff, reloads credentials from files, and suppresses late firing updates after a resolved alert. Its SQLite queue lives on a dedicated PVC/volume; run **one replica**. Completed records are retained as deduplication tombstones; monitor queue disk use and define a reviewed archival policy. Back up the queue and Alertmanager silences; validate a restore before relying on them. There is no HA claim for this adapter. Shared PostgreSQL/managed queue and worker leasing are required before scaling it.

## Kubernetes profiles and secrets

Apply `boutique-gitops/monitoring/profiles/homelab`, `nonprod`, or `production` for the appropriate cluster. Their target lists are dev only, dev+staging, and production only, avoiding phantom alerts. Before applying, provision Secret `monitoring-integrations` in namespace `monitoring` with keys `slack_webhook`, `webhook_token`, `servicenow_password`, and `grafana_password`. Set the ServiceNow URL/user in the incident bridge deployment and replace its image placeholder with the digest from the trusted Jenkins release job (`SERVICE=incident-bridge`, source repository `boutique-platform`). Promotion of that monitoring image is a reviewed GitOps change. The app promotion job remains limited to the four app services.

Core pod secret mounts expose only the receiver-specific keys needed by that component. For production use, enable internal webhook TLS or service-mesh mTLS as well as network isolation; the homelab webhook uses cluster-internal HTTP with a bearer token.

All core pods use non-root identities, resource limits and persistent storage. Grafana anonymous access and signup are disabled; services are internal ClusterIP without public ingress. Add SSO and TLS before exposing them. Alloy's host log collector has an isolated namespace with a Pod Security exception for read-only hostPath access and root file reading; it drops capabilities and cannot escalate privileges. Its Kubernetes permission is namespace-scoped read-only pod metadata, not Secrets. Review this exception and enforce egress restrictions with your cluster CNI. Log position state is ephemeral on node restart, so duplicate replay is possible.

For HA monitoring and Kubernetes/node metrics see `boutique-gitops/monitoring/production-reference`. The hand-written stack is deliberately one replica; the production target profile is not an HA claim. Production object storage, HA incident delivery, backups, SSO, paging, dead-man detection and failure drills remain deployment work.

## Service down

1. Confirm scope in Grafana and Prometheus target health; distinguish a scrape/network failure from an application failure.
2. Inspect rollout status, pod readiness, restarts, recent deployments and dependencies. Review logs for the same environment/service and request ID.
3. Roll back through the GitOps repository to the previous tested digest when a deployment is responsible. Avoid untracked live edits.
4. Confirm error rate/latency and the incident resolution; record the cause and follow-up in the incident.

For incident backlog: check bridge readiness, PVC capacity, receiver auth/ACLs, HTTPS connectivity and instance availability. Fix the dependency; pending records retry automatically. Do not delete the queue to clear an alert. For a failed Slack webhook, rotate it through secret settings and reload/restart Alertmanager, then verify delivery in an approved channel.

## Validation

`python -m unittest discover -s monitoring/incident-bridge -p 'test_*.py' -v` exercises durable retry, deduplication and resolution ordering. Promtool validates rules/configuration; amtool validates routing; Alloy validates collectors. The end-to-end test uses local mock receivers and checks firing-to-resolved delivery. Local tests do not establish live ServiceNow ACL/business-rule compatibility or HA readiness.
