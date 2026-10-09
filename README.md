# Runtime and operating guides

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

Application delivery uses service-owned Helm charts and separate dev/staging/production values; see [Helm delivery](../boutique-gitops/docs/helm-delivery.md). AWS monitoring and audit are described in [AWS observability](../boutique-infrastructure/docs/aws-observability.md).

Monitoring, alert lab fixtures, optional local data resources and monitoring External Secrets also use Helm charts; Argo CD, Jenkins checks and operational scripts select their reviewed values.
