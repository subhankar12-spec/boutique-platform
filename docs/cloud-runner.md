# Cloud runner and target-host validation

Use this workspace for source review, component tests, native Helm/schema checks
and isolated Jenkins configuration validation. The actual Debian laptop is a
separate machine; commands here do not operate its Jenkins agent or kind cluster.

See [validation.md](validation.md) for current results and live acceptance work.
The isolated controller harness has no GitHub/cloud credentials and does not
publish images, deploy applications or send notifications.

The optional two-cluster helper checks host prerequisites before cluster creation.
Run it only on a supported host with adequate Docker storage and at least 16 GiB
RAM (24–32 recommended), writable cgroups and working nested Kubernetes. Earlier
cloud attempts lacked those capabilities; do not treat old failures or a running
Docker daemon as proof that this instance can run a full cluster.

Your existing 8 GiB Debian host follows [deploy-cicd-kind.md](deploy-cicd-kind.md):
one existing mega-local cluster, one Jenkins controller, the connected rootless
build agent and dev first. Do not run the larger-host bootstrap unchanged there.

The eight repositories are published under subhankar12-spec. Use normal reviewed
Git commits/pushes, preserving local changes. Source publication is separate from
cloud environment configuration; saving an environment draft does not push code,
apply infrastructure or prove application functionality. Supply credentials only
through secure settings, never source files or chat.
