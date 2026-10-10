# Validation evidence

## Simplified delivery validation

- 44 configuration tests passed: immutable image/chart promotion, rejected
  mutations/unmerged rollback, actual Argo history/health checks, laptop profile
  and default/optional monitoring behavior.
- 13 optional production-lab safety tests passed.
- Strict Helm/schema validation passed for cloud/lab application environments,
  the existing-kind laptop dev profile, monitoring and auxiliary charts.
  Custom-resource skips remain explicit in the validator.
- A fresh isolated Jenkins 2.580.1 loaded all 74 verified pinned plugins; JCasC
  had zero warnings; actual Job DSL generated ten release jobs, with main-only service discovery with
  bootstrap automatic-build suppression. Jenkins accepted the shared service
  pipeline, seed, promote, rollback, manifest-validation, verify and infrastructure
  Declarative files.
- Isolated Jenkins execution demonstrated successful downstream propagation and
  an intentional downstream failure producing parent FAILURE.
- The new Slack-only Alertmanager configuration passed native amtool validation.
- 92 documentation shell examples passed Bash syntax checks; local file links
  and current deployment-guide anchors were checked.
- Protected manifest validation also passed against a candidate tree whose
  scripts were deliberately replaced with failing code: candidate scripts were
  not executed. Packaged Helm inputs are inspected before rendering.

These are configuration/component checks. The simplified full Jenkins → GHCR →
GitOps PR → Argo → live smoke flow has not been executed on the Debian laptop
from this cloud workspace. Live GitHub protection/status reporting, registry rights,
notifications, AWS and measured recovery remain target-host acceptance work.
The laptop agent was reported connected by the user before these code changes.

## Historical checks before simplification

The following records include tests of signing/evidence machinery now removed;
they document prior work and are not requirements for the current workflow.


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
| GitHub source publication | Eight repositories pushed through the platform integration; each remote `main` commit verified against its local branch |
| Data TLS | Disposable PostgreSQL/Redis connections accept the correct CA/hostname and reject the wrong CA, wrong hostname and plaintext PostgreSQL |
| Incident delivery | Unit/mock lifecycle checks, real shared PostgreSQL queue integration and two running adapter replicas exercising deduplication, resolution and late-firing suppression |
| Observability | Prometheus targets/rules, Alertmanager/Alloy configs, provisioned Grafana dashboard/data sources, real Alloy-to-Loki logs and mock Slack/ServiceNow delivery |

The local application smoke suite uses explicit failures rather than Python assertions, and emits machine-readable completion reports. Signed deployment evidence also checks native Kubernetes/Argo snapshots; tests of those snapshot guards use synthetic reports and are not substitutes for a live cluster run.

## Acceptance work on the target host

The cloud runner cannot validate the full Kubernetes path: Docker uses VFS with insufficient free storage for the lab, and cgroups are read-only. Earlier nested kind control-plane health failed; the new preflight blocks creation before expensive pulls. Argo reconciliation, Kubernetes rollouts, live network-policy enforcement, Kubernetes restore drills and real Jenkins-to-cluster execution remain unverified here. Run the [production lab](production-lab.md) on a supported Docker host and retain the signed outputs of each environment's verification.

All eight repositories have been pushed under `subhankar12-spec`; their remote `main` commits match the local branches. The owner created the empty repositories and granted the platform integration access. Repository creation from this runner still returns `403 Resource not accessible by integration`, but publishing to those existing repositories works without the dedicated publication token. Real repository protection, SCM webhooks/indexing, GHCR publication, approved PR merge and the end-to-end delivery chain have not run against GitHub. The isolated Jenkins tests use temporary local jobs and do not inherit GitHub/cloud credentials.

AWS account roles, backend settings, domain/DNS, platform controller bootstrap and cost inputs require target configuration. No AWS plan/apply or billable resource provisioning was performed. Terraform validation does not prove IAM permissions, quotas, infrastructure readiness or private endpoint connectivity.

Slack and ServiceNow integrations are prepared and tested against internal mocks. No real messages or incidents were sent. ServiceNow's scripted upsert resource and unique-index/table requirements must be installed and checked in the intended instance. A sleeping developer instance does not provide a production on-call service.

The affordable kind profile has one control plane per cluster and single-replica data services. Its two incident workers share a durable queue, but that does not make the local queue database HA. The separate Prometheus Operator HA reference is not an exercised deployment. Full monitoring/HA acceptance belongs to the selected runtime and includes failure/recovery drills.

Grafana was started and checked separately because VFS copies exhausted this runner's disk; its container/image were removed while preserving its volume and credentials. Existing application/data containers were preserved. Run simultaneous application, monitoring and Jenkins stacks on a host with sufficient resources.

Source-only secret scans and image gates cover the tested repository/runtime contents. They do not prove the absence of secrets in remote history or eliminate future vulnerabilities. Review the expiring exception and dependency updates before each release.

Reusable onboarding configuration is saved as an environment draft. Review/save and publish it in environment settings to activate it; that action still needs a fresh-task check before claiming cloud environment restoration.

Machine-readable summaries are retained in [summary.json](validation-artifacts/summary.json) and the [actual Jenkins runtime report](validation-artifacts/jenkins-runtime.json). The complete agent image remains unbuilt and unscanned here: its signed Debian snapshot endpoint returned HTTP 403. Nine checksum-locked tool distributions were independently installed and executed.


## Helm and AWS audit enhancement

The application migration renders all nine cloud/lab/local environment profiles to the same Kubernetes objects as their previous manifests. Helm lint, strict Kubernetes schemas and image-selection policy pass. Delivery tests use real packaged charts, Git histories and Ed25519 signatures, including package tampering and chart changes with unchanged images. The running Jenkins controller validated the revised shared service pipeline, five delivery jobs and infrastructure job; JCasC/seed jobs and isolated downstream lock tests passed. This is pipeline/configuration validation, not actual registry publication or cluster delivery.

All AWS platform roots validate with the locked provider. The new once-per-account audit root passes four native Terraform mock tests: secure management-event collection/storage/policies, explicit data-event opt-in, recursive log-bucket rejection and short-retention rejection. These are offline simulated plans, not real AWS plans or applies. CloudWatch delivery, the optional reviewed-version addon, CloudTrail events, SNS subscription confirmation and audit validation still require AWS acceptance. See the [AWS runbook](../../boutique-infrastructure/docs/aws-observability.md).


## Monitoring and auxiliary Helm migration

The remaining monitoring, lab fixtures, local data and monitoring External Secrets collections now use Helm. All eleven previous manifest collections were compared with their Helm equivalents and preserve resource identities and contents. Cloud/lab Prometheus targets, read-only RBAC, literal alert templates, dashboard content, incident queue persistence and immutable image overrides are covered by real Helm render tests. The configuration suite passes 76 tests; production-lab safety checks pass 12. The fixed Jenkins pipeline again passes real Declarative validation, JCasC/seed checks and isolated downstream execution.

Argo projects now admit the actual application namespaces required by monitoring discovery and the production worker disruption budget. Monitoring requires no cluster-wide RBAC grant. External Secrets resources pass the cached official v1 CRD schemas. Built-in Kubernetes schemas pass; certificate resources are excluded from that built-in-only check and retain the previously compared certificate content. These checks do not establish live reconciliation or notification delivery on a cluster.

## Documented reliability and recovery policy

[SLOs](slo.md) specify initial 30-day response/latency objectives and metric/coverage limitations; current seven-day retention and missing continuous external probes prevent a complete monthly availability claim. [Recovery targets](recovery-targets.md) distinguish local and AWS objectives and current backup controls. The [DR runbook](runbooks/disaster-recovery.md) and exercise template define manual replacement recovery and acceptance. Documentation does not enable backup scheduling, extend retention, create cross-region infrastructure or establish achieved RTO/RPO. Only isolated local orders restoration has been exercised; full environment/controller/cloud DR remains unverified.
