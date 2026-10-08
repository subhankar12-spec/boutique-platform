# Local development and integration

Run `./scripts/local-up.sh` for Compose and the functional smoke test. Run `./scripts/homelab-up.sh dev` for local Kubernetes after installing kind and kubectl; staging and production are optional arguments. This helper explicitly selects `kind-boutique` so it cannot accidentally target a cloud context.

Use `scripts/install-tools.sh` for checksum-verified Linux amd64 CLI installation. PyYAML is required for manifest/promotion checks. `python3 -m unittest discover -s tests/config -v` checks promotion ordering and immutable image enforcement. The actual smoke test uses only Python's standard library and tests all services through the public frontend boundary.

Local namespace deployments are direct bootstrap exercises. Once separate repositories exist, install Argo CD and use its Applications for GitOps reconciliation. Do not leave two deployment mechanisms managing the same resources.

See docs for Jenkins, AWS, runtime limitations and runbooks.

## Observability and incident delivery

See [monitoring setup and runbooks](docs/monitoring.md). Includes Prometheus, Grafana dashboards, Alertmanager Slack routing, a durable ServiceNow ITSM adapter, Loki/Alloy logs, local mock delivery tests, and separate Kubernetes scrape profiles. The trusted release job also builds the incident adapter from this repository. HA monitoring is a separate reference, not a property of the affordable single-replica stack.
