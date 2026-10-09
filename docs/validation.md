# Validation evidence

The checks below were exercised in this cloud workspace. They establish the stated behavior at the tested boundary; they do not establish a deployed production system or restoration in a fresh environment.

| Area | Exercised evidence |
|---|---|
| Application | Node, Go, Python and Java tests; Maven verification; actual four-service Compose HTTP smoke with PostgreSQL/Redis |
| Checkout correctness | Server-side totals, request validation, session ownership, repeated and concurrent idempotency |
| Data recovery | Logical backup restored into a disposable database and checked without changing the live database |
| Runtime image security | Fixable HIGH/CRITICAL image gate; one scoped, expiring non-applicable Spring XSLT exception remains documented |
| Delivery policy | Real temporary Git histories and Ed25519 signatures test release provenance, evidence freshness, digest/environment/history binding, stale changes and rollback guards |
| Kubernetes configuration | Application, lab and monitoring profiles rendered and checked with strict schemas; relevant custom-resource schemas checked separately |
| Terraform | State bootstrap, nonproduction and production initialization/validation/formatting; dedicated monitoring-data bootstrap exercised against a disposable TLS PostgreSQL instance |
| Jenkins | Jenkins 2.580.1 with 74 official checksum-locked plugins; real plugin-backed Declarative/Job DSL checks, JCasC and isolated downstream-job/environment-lock execution |
| Tools and controllers | Official CLI checksums and lab controller manifest/image locks verified |
| Data TLS | Disposable PostgreSQL/Redis connections accept the correct CA/hostname and reject the wrong CA, wrong hostname and plaintext PostgreSQL |
| Incident delivery | Unit/mock lifecycle checks, real shared PostgreSQL queue integration and two running adapter replicas exercising deduplication, resolution and late-firing suppression |
| Observability | Prometheus targets/rules, Alertmanager/Alloy configs, provisioned Grafana dashboard/data sources, real Alloy-to-Loki logs and mock Slack/ServiceNow delivery |

The local application smoke suite uses explicit failures rather than Python assertions, and emits machine-readable completion reports. Signed deployment evidence also checks native Kubernetes/Argo snapshots; tests of those snapshot guards use synthetic reports and are not substitutes for a live cluster run.

## Acceptance work on the target host

The cloud runner cannot validate the full Kubernetes path: Docker uses VFS with insufficient free storage for the lab, and cgroups are read-only. Earlier nested kind control-plane health failed; the new preflight blocks creation before expensive pulls. Argo reconciliation, Kubernetes rollouts, live network-policy enforcement, Kubernetes restore drills and real Jenkins-to-cluster execution remain unverified here. Run the [production lab](production-lab.md) on a supported Docker host and retain the signed outputs of each environment's verification.

GitHub repository creation/push is blocked by the current integration's `403 Resource not accessible by integration` response. Real repository protection, SCM webhooks/indexing, GHCR publication, approved PR merge and the end-to-end delivery chain have not run against GitHub. The isolated Jenkins tests use temporary local jobs and do not inherit GitHub/cloud credentials.

AWS account roles, backend settings, domain/DNS, platform controller bootstrap and cost inputs require target configuration. No AWS plan/apply or billable resource provisioning was performed. Terraform validation does not prove IAM permissions, quotas, infrastructure readiness or private endpoint connectivity.

Slack and ServiceNow integrations are prepared and tested against internal mocks. No real messages or incidents were sent. ServiceNow's scripted upsert resource and unique-index/table requirements must be installed and checked in the intended instance. A sleeping developer instance does not provide a production on-call service.

The affordable kind profile has one control plane per cluster and single-replica data services. Its two incident workers share a durable queue, but that does not make the local queue database HA. The separate Prometheus Operator HA reference is not an exercised deployment. Full monitoring/HA acceptance belongs to the selected runtime and includes failure/recovery drills.

Grafana was started and checked separately because VFS copies exhausted this runner's disk; its container/image were removed while preserving its volume and credentials. Existing application/data containers were preserved. Run simultaneous application, monitoring and Jenkins stacks on a host with sufficient resources.

Source-only secret scans and image gates cover the tested repository/runtime contents. They do not prove the absence of secrets in remote history or eliminate future vulnerabilities. Review the expiring exception and dependency updates before each release.

Reusable onboarding configuration is saved as an environment draft. Review/save and publish it in environment settings to activate it; that action still needs a fresh-task check before claiming cloud environment restoration.

Machine-readable summaries are retained in [summary.json](validation-artifacts/summary.json) and the [actual Jenkins runtime report](validation-artifacts/jenkins-runtime.json). The complete agent image remains unbuilt and unscanned here: its signed Debian snapshot endpoint returned HTTP 403. Eight checksum-locked tool distributions were independently installed and executed.
