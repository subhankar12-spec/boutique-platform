# Production delivery lab

Follow [the main CI/CD-first deployment guide](deploy-cicd-kind.md) for the
ordered setup. Cluster/controller bootstrap prepares the platform; Jenkins
publishes the first signed releases before Argo deploys the app. A prior
Compose or manual Kubernetes application deployment is optional.

Keep one repository per service. This lab uses the same reviewed releases, immutable image digests, Helm chart/image selections and verification gates as the AWS reference. Two independent Kubernetes clusters separate dev/staging from production; it does not create AWS resources or replace the existing Docker Compose installation.

| Boundary | Configuration |
|---|---|
| Nonproduction cluster | `kind-boutique-nonprod`: dev and staging namespaces, two workers |
| Production cluster | `kind-boutique-production`: production namespace, two workers |
| Network enforcement | Checksum-pinned Calico, default-deny application policies, executable allow/deny drill |
| Delivery | Digest-only releases, Argo CD per cluster, restricted AppProjects, existing Helm chart/image selections |
| Ingress and data | Traefik TLS, cert-manager certificates, CA/hostname verification for PostgreSQL and Redis |
| Verification identity | Namespace read-only service account plus Argo Application read access; no Secret read or deployment permission |
| Monitoring exercises | Prometheus/Grafana/Loki/Alloy; internal Slack/ServiceNow mock receivers; dedicated TLS PostgreSQL incident queue in production |

The single control plane and single-replica databases remain explicit availability limits of this affordable runtime. Two workers let you exercise scheduling, rolling updates, PodDisruptionBudgets and worker failure. They do not provide control-plane or database HA. EKS and managed databases are the cloud reference for those concerns. Local CA private keys and kind control-plane disks must be protected; Kubernetes Secrets in this local profile are not a replacement for the AWS Secrets Manager/KMS workflow.

## Host prerequisites

Use a Linux Docker host/VM with working privileged containers, writable host cgroups, kernel networking modules, Docker Compose, Python 3, OpenSSL and kubectl 1.34. Allow at least 16 GiB RAM (24–32 recommended) and 30 GiB free Docker storage. VFS needs substantially more disk; allow at least 60 GiB free or use a supported overlay2 host. Docker runs on the host, not inside an unprivileged application container.

From `boutique-platform`, install the shared CLI prerequisites, then the lab's checksum-locked kind version:

```bash
./scripts/install-tools.sh "$PWD/.tools"
export PATH="$PWD/.tools:$PATH"
python3 scripts/production-lab.py fetch-tools
python3 scripts/production-lab.py fetch-manifests
python3 scripts/production-lab.py doctor
```

The artifact lock contains upstream manifest SHA256 values, immutable upstream Git commit URLs where available, and every controller image digest. Cached bytes are checked again on every use. The Traefik installation is the official rendered chart release; the lab applies a reviewed NodePort/replica patch. Argo's Redis image uses Docker Hub's official Redis mirror, with its own verified digest, to avoid reliance on the ECR mirror. Update locks through a reviewed dependency change, not by changing tags in place.

`doctor` does not pull images, create clusters, stop containers or delete volumes. A failing preflight stops bootstrap. If nested kubelet fails, use a supported Linux VM/host; do not disable probes, network policies or certificate verification to make the result look successful. Failure logs are exported beneath the ignored private state directory when kind can export them.

## Bootstrap both foundations

```bash
python3 scripts/production-lab.py bootstrap --cluster nonprod
python3 scripts/production-lab.py bootstrap --cluster production
```

All kubectl operations specify the intended cluster context. Operator kubeconfigs, distinct per-cluster CA keys, and local restore backups live under `local/production-lab/.state/`, ignored by Git and protected by private directory/file modes. Never use an operator kubeconfig as a Jenkins build credential. Existing CA/credential state is preserved on reruns; partial credential state or changed cluster trust blocks setup rather than silently resetting passwords.

Add these names to the operator machine's hosts file:

```text
127.0.0.1 dev.boutique.test staging.boutique.test production.boutique.test
```

The frontend origins are `https://dev.boutique.test:8443`, `https://staging.boutique.test:8443` and `https://production.boutique.test:9443`. The matching CA files are `.state/nonprod/ca/ca.crt` and `.state/production/ca/ca.crt`. Import the relevant CA into your browser trust store if using the UI; automated smoke tests use that CA directly and retain hostname verification. Only loopback TLS ports are exposed by the kind configuration. A Jenkins verifier on another machine needs private network routing/DNS and trusted TLS endpoints; `127.0.0.1` inside a separate Jenkins container refers to that container, not this host.

## Prepare publication, credentials and releases

Argo CD reads the published GitOps repository; local files alone cannot satisfy delivery. The eight repositories are already published. After preparing cluster foundations, configure trusted Jenkins, identities and protection, then release the four application services through their build/test/scan gates. Release the incident adapter separately when adding monitoring. For the first installation, run the four application `boutique-{service}/main` jobs with `DELIVER_TO_DEV=false` and retain their successful release build numbers. This publishes the quality-checked, signed images without trying to verify an incomplete application. Use the aggregate bootstrap below to select the initial four-service baseline. Subsequent main builds keep automatic dev delivery enabled. `lab-profiles/{environment}/values.yaml` supplements the environment Helm chart with local data/TLS configuration; it does not replace the release digest or rebuild an environment-specific image.

Use private files (`chmod 600`) for a read-only GitOps repository token and a GHCR `read:packages` token. Prefer short-lived GitHub App credentials and rotate them separately from the build/publish identity. Do not put tokens in command arguments, source files or chat.

```bash
python3 scripts/production-lab.py secrets --cluster nonprod \
  --repo-token-file /secure/gitops-read-token \
  --registry-token-file /secure/ghcr-read-token --registry-user YOUR_GITHUB_OWNER
python3 scripts/production-lab.py secrets --cluster production \
  --repo-token-file /secure/gitops-read-token \
  --registry-token-file /secure/ghcr-read-token --registry-user YOUR_GITHUB_OWNER
```

Omit `--repo-token-file` only for a public GitOps repository. Generated Redis, application session, application PostgreSQL, Grafana and integration fixture credentials are independent. Production incident queue credentials belong to a separate database/user in the monitoring namespace. Never reuse the orders database for the incident queue.

Existing secrets are preserved rather than rotated implicitly. To rotate an existing integration token/password, update the corresponding Kubernetes Secret using your secret-management process and reconcile its clients. Changing a PostgreSQL Secret alone does not change the password stored in an initialized database. Keep CA keys backed up securely; changing cluster trust is a coordinated operation. Cert-manager renews the leaf certificates, but the locally created one-year root CA requires a planned rotation.

## Connect Argo and verify delivery

Start `boutique-bootstrap` with `TARGET=dev` and the four signed release build numbers in `FRONTEND_BUILD`, `CATALOGUE_BUILD`, `CART_BUILD` and `ORDERS_BUILD`. Keep `PAUSE_FOR_INITIAL_SYNC=true`. The job validates all four releases, opens and merges the reviewed aggregate GitOps PR, then pauses before initial verification. At that pause, update your clean operator GitOps checkout and activate only dev:

```bash
git -C ../boutique-gitops pull --ff-only
python3 scripts/production-lab.py deploy --cluster nonprod --environment dev
python3 scripts/production-lab.py readiness --cluster nonprod --environment dev
python3 scripts/production-lab.py verify --environment dev
```

Continue the Jenkins pause once Argo synchronization has started. The bootstrap job runs `boutique-verify` for each selected service and produces four signed dev verification records. Do not activate staging while its release values still contain bootstrap tags.

For the first staging release, run `boutique-bootstrap` with `TARGET=staging`, the same four release build numbers, and the corresponding dev verification builds in the four `*_EVIDENCE_BUILD` parameters. After its reviewed aggregate merge, use the initial-sync pause to activate staging:

```bash
git -C ../boutique-gitops pull --ff-only
python3 scripts/production-lab.py deploy --cluster nonprod --environment staging
python3 scripts/production-lab.py readiness --cluster nonprod --environment staging
```

The first production bootstrap similarly selects `TARGET=production`, consumes the four staging verification builds, and requires production approval before merging. Activate that approved production baseline at its initial-sync pause:

```bash
git -C ../boutique-gitops pull --ff-only
python3 scripts/production-lab.py deploy --cluster production --environment production
python3 scripts/production-lab.py readiness --cluster production --environment production
```

These environment selections avoid requiring a staging release before dev verification exists. Cluster foundations and credentials can be prepared ahead of time; Applications begin tracking main only after the selected environment has a complete approved digest baseline.

`deploy` refuses every Boutique `bootstrap`, `local`, mutable tag or malformed digest before creating Applications. Argo must fetch the committed main branch; readiness requires Synced/Healthy applications, ready nodes/Calico, completed service rollouts, issued data/frontend certificates and digest-pinned running deployments. `verify` executes the real functional smoke suite through TLS ingress. Repeat verification for staging and production when their promotion gates select an approved digest. Successful rendering alone does not count as deployment evidence.

Jenkins uses the separate deployment verifier and records evidence for the exact promoted digest/GitOps revision. Configure the trusted origin variables to the TLS URLs above. Supply each environment's CA as a secret file credential and export a namespace-scoped verifier identity:

```bash
python3 scripts/production-lab.py export-verifier --environment dev --duration 24h
python3 scripts/production-lab.py export-verifier --environment staging --duration 24h
python3 scripts/production-lab.py export-verifier --environment production --duration 24h
```

Upload only the generated `jenkins-verifier-{environment}.json` files to the corresponding Jenkins verification credentials. They cannot change deployments, read Secrets or access another application's namespace. Requested tokens expire within 24 hours; renew before a drill/build session. For a continuously operating platform, use automated short-lived workload identity rather than storing a long-lived admin token. The cloud counterpart uses the separate cluster/environment identity and its real private API endpoint.

Argo and Grafana remain ClusterIP services. Access administration through an operator port-forward bound to loopback; obtain initial credentials locally without recording them in logs. Complete SSO/RBAC and remove bootstrap-admin dependence before exposing either service to a shared network. The existing AWS ingress/issuer configuration requires a real domain and ACME account; `.test` names and this local CA are only for the production-learning profile.

## Monitoring delivery exercises

After releasing/promoting the incident adapter image, replace its placeholder with the tested immutable digest in the monitoring manifests and commit that GitOps change. Then:

```bash
python3 scripts/production-lab.py deploy --cluster nonprod --monitoring
python3 scripts/production-lab.py deploy --cluster production --monitoring
python3 scripts/production-lab.py readiness --cluster nonprod --monitoring
python3 scripts/production-lab.py readiness --cluster production --monitoring
```

These profiles intentionally route to the internal mock Slack/ServiceNow receivers. The production profile still uses the scripted ServiceNow upsert lifecycle and the shared PostgreSQL queue for two adapter replicas; it does not create real tickets or send real messages. Mock receiver state is disposable and loses captured events on restart; the delivery queue is persisted separately. Follow `monitoring.md` for live credentials, network rules and an explicitly authorized live notification test. A reachable mock receiver is not proof of live paging.

## Repeatable failure and recovery drills

Run these against dev first, then repeat the workflow through the environment gates:

```bash
python3 scripts/production-lab.py policy-drill --environment dev
python3 scripts/production-lab.py restore-drill --environment dev
python3 scripts/production-lab-tls-test.py
python3 scripts/test_production_lab.py -v
```

The policy drill proves the permitted ingress namespace can reach the same frontend IPv4 Service that an unrelated namespace cannot reach. It uses the IP directly so DNS failures cannot masquerade as policy enforcement. Only its uniquely named temporary Jobs/namespace are removed.

The restore drill produces a private logical backup, restores into a uniquely named disposable database, verifies order count against the backup window and successful Flyway history, records elapsed restore time, and drops only that disposable database. It preserves the live database and PVC. Backups contain application data; encrypt them before exporting and establish retention. This is a database restore test, not a point-in-time recovery or a full disaster-recovery test.

The TLS test uses existing tested container images, isolated Docker networking and disposable data. It validates CA/hostname acceptance and rejection for both clients plus PostgreSQL/Redis TLS key permissions. It does not pull images, touch existing Compose containers/volumes or send external notifications.

Also execute the reviewed GitOps rollback workflow after a deliberately failed candidate, check that promotion is blocked without matching verification evidence, restore Jenkins from its configuration/backup runbook, and restart incident adapter replicas while notifications are pending. Capture evidence and recovery times instead of declaring the platform complete because configuration files exist.

## Validation on the current cloud runner

The new dev/staging/production profiles render. All four controller source checksums and all controller image digest locks validate. The kind 0.33.0 CLI passes its published SHA256 check. Script regression checks pass. Disposable Docker tests prove PostgreSQL `verify-full` and Redis TLS CA/hostname rejection, validate certificate file permissions, and prove server-side rejection of plaintext PostgreSQL connections.

The runner's Docker storage uses VFS, has less than the required 30 GiB free, and exposes read-only cgroups to this process. Earlier nested kind failed kubelet/control-plane health. The doctor therefore blocks cluster creation before pulling node images. Kubernetes controller installation, Argo reconciliation, live network-policy enforcement, Kubernetes restore and real Jenkins-to-cluster execution remain unverified here; run them on the documented supported host. Existing Docker Compose application/data were preserved.

Monitoring also uses Helm: `monitoring/` is the shared chart, `monitoring/profiles/<cluster>/values.yaml` selects discovery and queue behavior, and `lab-profiles/monitoring/<cluster>/values.yaml` enables internal fixtures and the local production TLS queue. The deployment helper and Argo Application select these same value files. Select the adapter digest in the cloud profile values; it applies to the lab too.

## Recovery acceptance

Use [recovery-targets.md](recovery-targets.md) and the [DR runbook](runbooks/disaster-recovery.md) to record end-to-end RTO/RPO. The existing isolated `restore-drill` measures only a database step; it does not prove host/cluster disaster recovery. Recovering on a separate host with off-host backups is the intended quarterly exercise.
