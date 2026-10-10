# Platform and CI file map

All active runtime definitions describe the current single-controller, PR-based
delivery flow. Deleted workflows/reports remain recoverable in Git history;
they are not part of the current source tree.

## boutique-ci

| Path | Current purpose |
| --- | --- |
| vars/servicePipeline.groovy | Separate Test/JUnit and Build image stages, quality gates and GHCR publication |
| vars/releaseArtifact.groovy | Retrieve publishing artifacts for dev selection |
| vars/gitopsPullRequest.groovy | Open a deployment PR and queue manifest validation |
| pipelines/seed-release.Jenkinsfile | Pipeline seed invoking current Job DSL |
| pipelines/gitops-validate.Jenkinsfile | Ordinary manifest PR check with protected tools/status reporting |
| pipelines/promote.Jenkinsfile | Copy immutable image/chart selection and open PR |
| pipelines/rollback.Jenkinsfile | Restore one service from protected Git history through PR |
| pipelines/verify.Jenkinsfile | Optional read-only rollout/smoke verification |
| jenkins/jobs/release.groovy | Nine default jobs; only main service branches |
| jenkins/casc and jenkins/compose.yaml | Fresh single-controller configuration; existing installations follow the migration guide |
| jenkins/controller and jenkins/scripts/lock-plugins.py | Locked controller core/plugins and reviewed upgrade tooling |
| jenkins/agents | Existing common inbound build-agent image and rootless setup |
| jenkins/scripts | Tool installers, integrity tests, controller checks and local initialization |

The obsolete validation controller, signing-key generator, signed policy job and
aggregate bootstrap pipeline have been removed. The retired private-key ignore
rule remains to prevent accidentally committing old keys during migration.
Plugin locks retain required transitive dependencies; removing libraries by
name would break the verified Jenkins installation.

## boutique-platform

| Path | Current purpose |
| --- | --- |
| local/compose.yaml, scripts/local-up.sh and init-local.sh | Optional fast application development |
| scripts/k8s-secrets.py | Preserve/generate app secrets directly in the chosen cluster |
| scripts/wait-for-deployment.py | Read-only Argo/revision/image/chart/rollout checks |
| tests/smoke | Functional application acceptance |
| tests/config | Current promotion, rollback, manifest and verifier regression checks |
| scripts/backup-local.sh and restore-drill.sh | Data backup/isolated restore exercises |
| monitoring | Prometheus/Grafana, Alertmanager, Loki/Alloy and integration exercises |
| monitoring/incident-bridge and servicenow | Optional ServiceNow adapter; disabled by default in Kubernetes |
| local/production-lab and production-lab*.py | Optional larger-host two-cluster/TLS/recovery exercise, not the existing-laptop path |
| scripts/test_production_lab.py | Safety tests for that optional helper |
| scripts/install-tools.sh | Verified CLI installation |
| docs | Current architecture, deployment, observability and recovery guides; start at deploy-cicd-kind.md |
| docs/validation-artifacts | Current summary and current Jenkins runtime report only |
| workspace | Eight-repo editor/overview templates |

The fixed-name homelab bootstrap and initial repository creation/publication
helpers were retired. Use the existing-cluster guide and normal Git commands.
Local caches, private credentials, databases and volumes are not tracked source
and are not deleted by this cleanup. Git pull does not remove obsolete Jenkins
jobs/credentials; follow [the migration steps](deploy-cicd-kind.md).

The ServiceNow adapter build is opt-in in the seed with
`ENABLE_INCIDENT_BRIDGE_BUILD=true`. If an earlier seed already created
`boutique-platform`, disable that Jenkins job when the integration is unused;
removedJobAction=IGNORE deliberately preserves existing jobs.

Superseded source/publication notes and the separate roadmap have been removed.
The operating sequence lives in the main deployment guide; cloud test boundaries
live in validation.md. Active local-image, larger-host and AWS guides describe
optional paths and remain available alongside the primary laptop guide.

Each application repository has `ci/test.sh` for its isolated test runner and a
Dockerfile `test` target containing the required tools/dependencies. Tests execute
in Jenkins's Test stage, not as Docker build instructions. The catalogue's small
report converter and the optional adapter's stdlib runner emit JUnit without new
application runtime dependencies. Test code/tools stay out of final images.

The [complete platform audit](file-audit.md) lists each retained file. Kubernetes
monitoring copies were removed from platform; native validation reads the GitOps
Helm chart directly. Compose monitoring remains a separate local runtime.
