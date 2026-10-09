# Shipyard Boutique — production delivery lab

A working four-service ecommerce app with Jenkins, Kubernetes GitOps, monitoring and an AWS reference architecture. The application stays small so the learning focus is delivery and operations. Each directory below is an independent Git repository.

| Repository | Responsibility |
|---|---|
| boutique-frontend | Node.js storefront and API gateway |
| boutique-catalogue | Go product API |
| boutique-cart | Python/FastAPI carts backed by Redis |
| boutique-orders | Java/Spring Boot orders backed by PostgreSQL |
| boutique-ci | Jenkins shared library, trusted pipelines, controllers and agents |
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

Service PRs run tests, builds and security scans on an isolated validation controller. Protected-main builds publish a tested image, versioned Helm chart, SBOM, scan report and signed release attestation. Jenkins opens GitOps PRs to promote the same signed chart package and immutable image digest through dev, staging and production. A fixed trusted policy job checks the candidate manifests and signatures. Argo CD reconciles merged changes; a read-only verifier measures rollout, runtime image IDs and HTTP behavior, then signs deployment evidence. Staging and production require matching evidence from the preceding environment. Production has an explicit approval; rollback uses previous verified evidence and a current-image guard.

An initial bootstrap job publishes all four service selections together, avoiding incomplete first deployments. Separate controllers isolate PR code from release credentials. Environment locks serialize promotion and rollback through verification. These are implemented controls; the full GitHub-to-cluster path still needs execution on a supported host.

Choose a deployment track:

- **Laptop or Linux VM lab:** two separate kind clusters, with dev/staging separated from production; Calico policies, Argo CD, TLS ingress, verified PostgreSQL/Redis TLS and recovery drills. Allow 16 GB RAM and 30 GB free Docker storage, preferably 24–32 GB RAM. Local control planes and databases are single replica; their availability limits are documented.
- **AWS reference:** separate VPCs/EKS clusters, private endpoints, managed data services, workload identities, external secrets, encrypted state and backups. Production data services use Multi-AZ configuration. No paid resources were provisioned.

Monitoring includes Prometheus, Grafana dashboards, Alertmanager, Loki/Alloy, prepared Slack integration and a ServiceNow adapter. The production adapter uses a shared PostgreSQL queue with two replicas. Internal fixtures exercise notifications without sending live Slack messages or creating external tickets. Live credentials and ServiceNow configuration remain operator setup steps.

## Evidence and access limitations

The app's functional smoke checks, real database/client TLS tests, queue integration tests, signed-delivery policy tests and actual Jenkins controller/plugin/pipeline checks have been exercised. See [validation](boutique-platform/docs/validation.md) for their scope.

This cloud runner cannot validate the full two-cluster deployment: it has insufficient Docker disk space and restricted cgroups. GitHub repository creation was denied by the installed integration (HTTP 403); publication remains blocked. Local commits and recoverable source/Git archives preserve the work. Saving cloud environment configuration does not publish GitHub repositories or activate the environment draft.

Start with [production lab setup](boutique-platform/docs/production-lab.md), [Jenkins setup](boutique-platform/docs/jenkins-setup.md), [delivery evidence](boutique-gitops/docs/release-evidence.md), and the [AWS infrastructure guide](boutique-infrastructure/README.md).

Application charts and AWS telemetry: see `boutique-gitops/docs/helm-delivery.md` and `boutique-infrastructure/docs/aws-observability.md`.

Monitoring, alert lab fixtures, optional local data resources and monitoring External Secrets also use Helm charts; Argo CD, Jenkins checks and operational scripts select their reviewed values.
