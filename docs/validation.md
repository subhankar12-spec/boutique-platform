# Validation evidence

Validated in the current cloud instance on 2026-10-08. This does not establish restoration in a fresh task or a production deployment.

| Check | Result |
|---|---|
| Node session tests | 2 passed |
| Go catalogue tests | 2 passed |
| Python cart validation tests | 6 passed |
| Java orders validation tests | 2 passed; Maven verify completed |
| HTTP integration smoke suite | Passed on actual four-service Compose stack with PostgreSQL and Redis |
| Checkout behavior | Server-side totals, repeat-key/concurrent-key idempotency and order ownership verified |
| Backup/restore | pg_dump archive restored to a separate database; expected order count verified |
| Image security policy | All four runtime images pass the fixable HIGH/CRITICAL gate; one expiring, scoped non-applicable Spring XSLT exception |
| GitOps config tests | 2 passed; promotion ordering/digest checks and three homelab environment dependency mappings |
| Kubernetes schema validation | App overlays and homelab manifests passed strict kubeconform validation; no resources skipped |
| Terraform | Nonprod, production and state bootstrap init/validate passed; formatting checked; no AWS plan/apply |
| Jenkins/Groovy | 11 pipeline/library/Job DSL files parsed with Groovy 2.4 syntax parser |
| CLI installer | kubectl, kind, Terraform and kubeconform downloads verified against official checksums |

## Important limits

- Jenkins update center returned network-policy 403. Controller plugin bootstrap, plugin version lock, Declarative linter, jobs, agents, registry publication and full Jenkins delivery have not run. Groovy parsing is not a substitute for those checks.
- Nested kind control-plane initialization failed on this cloud host. Kubernetes manifests are schema-validated, but Kubernetes rollout, Argo CD reconciliation and NetworkPolicy enforcement are unverified. The failed cluster was removed; Compose remains running.
- AWS account/roles, backend names, DNS, budget inputs and platform controller bootstrap require user configuration. No billable resources were provisioned. Terraform validate does not prove cloud permissions, quotas or runtime connectivity.
- The official RDS truststore endpoint returned network-policy 403. Fetch, review and commit the bundle before the trusted orders release. TLS verification was not disabled.
- Required network domains and Compose startup instructions were saved in the environment draft. Saving does not apply/publish those settings or validate a new task. Review/save and publish through environment settings when you want that configuration activated.
- The app intentionally omits account authentication, real payments, inventory reservation, centralized log storage, tracing and automatic signed release attestation enforcement. It is a serious learning baseline, not a claim of production readiness.

## Observability extension validation

Locally verified: seven incident adapter tests (durable retry, deduplication, resolution ordering, lost-response lookup, scripted request mapping and webhook authentication/rotation); two promtool alert-rule scenarios; Prometheus/Alertmanager/Alloy configuration checks; Grafana 13.2.3 startup, ten-panel dashboard provisioning and both datasource UIDs; real Alloy-to-Loki application log delivery; mock Slack firing/resolution and ServiceNow creation/resolution with duplicate firing; rebuilt app tests and functional checkout smoke. The Java fractional SLO boundary was corrected to `2500ms` after the live startup check rejected `2.5s`.

All monitoring profiles are rendered and checked with strict Kubernetes schemas. These checks do not establish a working Kubernetes deployment or HA behavior. The ServiceNow scripted resource is a reference, tested only at its adapter request boundary, not inside ServiceNow. The Prometheus Operator Helm reference is not rendered/deployed: downloads from `get.helm.sh` and `prometheus-community.github.io` were blocked by the current network policy; their additions are saved in the environment draft.

This runner's VFS Docker driver consumes full image copies during builds/container creation. Grafana was validated separately, then its container/image removed to preserve disk for app/Alloy tests; its data volume and credentials were preserved. Run the full simultaneous stack on a Docker host with enough storage. No live receiver credentials are present, and no real notifications or incidents were sent.

Final monitoring schema counts: homelab 32, nonprod 34, production 32 valid resources, none invalid/skipped. The adapter image has no fixable HIGH/CRITICAL findings under the configured Trivy gate; source-only secret scanning of all eight repositories found no HIGH/CRITICAL secrets. Live receiver activation and production HA deployment remain unverified.
