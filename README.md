# Runtime and operating guides

**Start here:** follow the [main CI/CD-first kind deployment guide](docs/deploy-cicd-kind.md):
clone → prepare clusters/controllers → configure Jenkins → build/publish releases →
GitOps → Argo deployment → verification/promotion → monitoring/recovery.

**Understand the architecture:** the [complete beginner guide](docs/beginner-guide.md) explains all eight repositories, the application request flow, and step-by-step Debian/Compose/existing-kind deployment. It then walks through Jenkins agents and credentials, the two-cluster dev/staging/production lab, signed releases, monitoring, AWS, troubleshooting and recovery.

**Optional manual practice:** the [eight-step local kind exercise](docs/deploy-local-kind.md)
uses locally built images and direct manifest application. It is not a prerequisite
for the main CI/CD flow.

Run `./scripts/local-up.sh` for Docker Compose and functional smoke checks. Secrets and database volumes are preserved on reruns. This is the fastest application development workflow.

For production delivery practice on a suitable laptop or Linux VM, follow [production-lab.md](docs/production-lab.md). It creates separate nonprod and production clusters with pinned controllers, TLS, policy enforcement, read-only deployment verification and recovery drills. It uses the same reviewed image digests and Helm chart and image selections as the AWS reference. The older `homelab-up.sh` helper remains a single-cluster bootstrap exercise; the production lab is the preferred delivery path.

Follow [Jenkins setup](docs/jenkins-setup.md) for the isolated controllers, initial four-service bootstrap, signed artifacts, promotion and rollback. The four application repositories and this repository's incident adapter use the shared build pipeline. GitOps changes are checked by a fixed trusted job before merge; Argo CD owns reconciliation.

[Monitoring](docs/monitoring.md) includes Prometheus/Grafana, Alertmanager, Loki/Alloy, Slack preparation, ServiceNow lifecycle integration, a PostgreSQL queue for two production adapter replicas, and local notification fixtures. Live notification activation requires securely supplied credentials and the documented ServiceNow endpoint.

Use `scripts/install-tools.sh` for verified Linux amd64 CLIs. Python/PyYAML are needed for manifest and delivery checks:

```bash
python3 -m unittest discover -s tests/config -v
python3 scripts/test_production_lab.py -v
python3 tests/smoke/smoke.py
```

See [validation.md](docs/validation.md) for what ran and what remains unverified. Kubernetes deployment needs a supported host; cloud resources and remote notifications have not been provisioned or activated here.

Application delivery uses service-owned Helm charts and separate dev/staging/production values; see [Helm delivery](https://github.com/subhankar12-spec/boutique-gitops/blob/main/docs/helm-delivery.md). AWS monitoring and audit are described in [AWS observability](https://github.com/subhankar12-spec/boutique-infrastructure/blob/main/docs/aws-observability.md).

Monitoring, alert lab fixtures, optional local data resources and monitoring External Secrets also use Helm charts; Argo CD, Jenkins checks and operational scripts select their reviewed values.

[SLOs](docs/slo.md), [RTO/RPO targets](docs/recovery-targets.md) and the [DR runbook](docs/runbooks/disaster-recovery.md) define intended reliability and recovery acceptance. Targets are unproven until exercised; backup automation/off-host storage and regional DR remain pending.
