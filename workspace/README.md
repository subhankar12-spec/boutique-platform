# Shipyard Boutique — production delivery lab

A working four-service ecommerce app with Jenkins, Kubernetes GitOps, monitoring and an AWS reference architecture. The application stays small so the learning focus is delivery and operations. Each directory below is an independent Git repository.

| Repository | Responsibility |
|---|---|
| boutique-frontend | Node.js storefront and API gateway |
| boutique-catalogue | Go product API |
| boutique-cart | Python/FastAPI carts backed by Redis |
| boutique-orders | Java/Spring Boot orders backed by PostgreSQL |
| boutique-ci | Jenkins shared library, shared pipelines, controller and agents |
| boutique-infrastructure | Terraform AWS infrastructure and database bootstrap |
| boutique-gitops | Helm environment charts, Argo CD, policies and monitoring |
| boutique-platform | Local runtime, production lab, integration checks and runbooks |

## Start with the application

Requires Docker with Compose, Python 3 and approximately 4 GB RAM:

```bash
cd boutique-platform
./scripts/local-up.sh
```

Only the frontend is exposed, on local port 8080. Generated secrets in ignored `local/.env` are preserved on reruns. Stop containers with `docker compose down` in `local`; retained database volumes and their passwords must stay together.

## Delivery and deployment

Reviewed service main runs Jenkins tests, scans, builds, SBOM and publication.
Jenkins opens GitOps PRs selecting immutable image digests and exact packaged
Helm charts. Jenkins manifest checks validate manifests; human review/merge is
the approval boundary. Argo CD deploys, then rollout/smoke checks establish
runtime success. Promotion copies the same image/chart; rollback restores a
service from protected Git history. One controller and a private rootless build
agent run reviewed code. Untrusted PRs require isolated workers before enabling.
No custom signing/evidence workflow or aggregate bootstrap job is required.

## Evidence and access limitations

The app's functional smoke checks, real database/client TLS tests, queue integration tests, immutable promotion/rollback tests and actual Jenkins controller/plugin/pipeline checks have been exercised. See [validation](https://github.com/subhankar12-spec/boutique-platform/blob/main/docs/validation.md) for their scope.

Cloud component validation does not prove a complete Jenkins/GHCR/Argo delivery
or the optional two-cluster deployment. Run live acceptance on the target host,
using the current validation guide above. Published Git source and local source
archives do not back up databases, secrets or Jenkins state. Saving cloud
environment configuration does not push source or execute a deployment.

Start with [existing Debian/kind deployment](https://github.com/subhankar12-spec/boutique-platform/blob/main/docs/deploy-cicd-kind.md), [Jenkins setup](https://github.com/subhankar12-spec/boutique-platform/blob/main/docs/jenkins-setup.md), [Helm delivery](https://github.com/subhankar12-spec/boutique-gitops/blob/main/docs/helm-delivery.md), and the [AWS infrastructure guide](https://github.com/subhankar12-spec/boutique-infrastructure/blob/main/README.md).

Application charts and AWS telemetry: see `boutique-gitops/docs/helm-delivery.md` and `boutique-infrastructure/docs/aws-observability.md`.

Monitoring, alert lab fixtures, optional local data resources and monitoring External Secrets also use Helm charts; Argo CD, Jenkins checks and operational scripts select their reviewed values.

Reliability policies: [SLOs](https://github.com/subhankar12-spec/boutique-platform/blob/main/docs/slo.md), [RTO/RPO targets](https://github.com/subhankar12-spec/boutique-platform/blob/main/docs/recovery-targets.md) and the [DR runbook](https://github.com/subhankar12-spec/boutique-platform/blob/main/docs/runbooks/disaster-recovery.md). These define targets and acceptance; full disaster recovery remains untested.
