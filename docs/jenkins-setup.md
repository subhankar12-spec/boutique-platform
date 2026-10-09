# Jenkins setup

This setup keeps service code small while exercising reviewed releases, registry provenance, GitOps promotion, runtime verification and recovery. Use the [two-cluster production lab](production-lab.md) on a suitable laptop Docker host/Linux VM, or configure the separate AWS reference. No AWS deployment is required to start learning the delivery workflow.

## Start the local controllers

```bash
cd boutique-ci/jenkins
./scripts/init-local.sh
python3 scripts/init-signing-keys.py
docker compose up -d --build
```

Validation listens on loopback port 8090; release listens on 8091. Both have zero controller executors, JCasC and independent persistent home volumes. `init-local.sh` preserves existing credentials and generates missing passwords in ignored mode-0600 `.env`. It sets `BOUTIQUE_CI_LIBRARY_REF` to the current CI commit only when the setting is absent: review the full commit SHA, and update it explicitly when approving a library upgrade. The library is configured as untrusted, with version overrides disabled.

The local realm includes the bootstrap `admin` identity and named `release-manager` / `platform-admin` approvers. Their generated passwords stay in `.env`; retrieve them locally without copying values into chat or build logs. Production delivery inputs name `release-manager`; Terraform apply names `platform-admin`. For shared or remote use, configure organizational TLS/SSO/RBAC and deliberately map those approver names in the pipeline configuration. Local bootstrap accounts are not an organizational identity system.

The controller pins Jenkins 2.580.1 and 74 checksum-locked plugins from official archives. `python3 scripts/doctor.py` checks the lock/tool prerequisites. From the repository root, `python3 jenkins/scripts/smoke-controller.py --directory /secure/private-cache` performs an isolated runtime check with Java 21 and a mode-0700 cache outside the checkout. It does not create/index real source jobs or receive GitHub/cloud credentials.

## Keep the trust boundaries separate

Any PR Jenkinsfile can execute code, request labels and attempt credential bindings. The validation controller therefore receives only scoped read credentials and disposable build agents. Release/deploy agents, publishing credentials, GitOps write access, private signing keys and AWS permissions belong to the separate release controller. Do not connect a trusted agent or shared Docker daemon to validation.

Create inbound nodes with one executor each and provision their tools/network routes:

| Controller | Label | Purpose |
|---|---|---|
| Validation | `isolated-builder` | Disposable PR tests/builds/scans; separate rootless Docker daemon |
| Release | `trusted-release` | Protected-main tests/builds/publishing; dedicated rootless Docker daemon |
| Release | `trusted-deploy` | GitOps preparation and read-only cluster/HTTPS verification |
| Release | `policy-check` | Fixed GitOps PR policy and rendering; no private signing key, Docker or cluster credential required |
| Release | `terraform-trusted` | Optional AWS plan/apply using short-lived workload identity |

The policy executor must be distinct from the occupied deploy executor: the parent waits for policy while retaining its deployment workspace. The release and delivery parents free their build/deploy executor before waiting for downstream rollout verification. Promotion and rollback retain their common `boutique-delivery-ENV` lock through the verifier, which must not reacquire it. These choices avoid single-executor child-job deadlocks while preventing competing deliveries to the same environment.

Use [agent setup](../../boutique-ci/jenkins/agents/README.md) for WebSocket connection and rootless Docker requirements. Deploy/policy agents need Python, Git, GitHub CLI, OpenSSL, kubectl, Helm and kubeconform; infrastructure agents also need Terraform. Controllers do not build images. Agent VMs, network routes and remote TLS endpoints are explicit provisioning tasks.

## Repository and job wiring

1. Confirm access to the eight published repositories under `subhankar12-spec`, preserving their `main` branches; their source commits were pushed and verified against GitHub (see [validation](validation.md)). Argo and SCM jobs need their own scoped credentials to read these sources.
2. Configure scoped `github-read` credentials on each controller. The JCasC shared library retrieves `boutique-ci` at the reviewed `BOUTIQUE_CI_LIBRARY_REF`.
3. Run the reviewed `jenkins/jobs/validation.groovy` seed on validation. It generates application/platform/GitOps multibranch jobs with origin PR discovery and no fork PR discovery. Configure signed GitHub webhooks and the service-required checks.
4. Run `jenkins/jobs/release.groovy` on release. It generates main-only service/platform multibranch jobs, `boutique-bootstrap`, `boutique-promote`, `boutique-verify`, `boutique-rollback`, `boutique-gitops-check` and `boutique-infrastructure`.
5. Protect application, CI, infrastructure and GitOps main branches with suitable checks, restricted writes/force pushes and owner review of trusted definitions. A privileged bot must not bypass production review. Use a GitHub App/dedicated bot to create owned-path PRs and a different reviewer identity: GitHub does not permit approving your own PR.

`boutique-gitops-check` loads its definition from protected CI and its tools from protected GitOps main. Candidate PR files are evaluated as data; its required result must not come from the candidate's Jenkinsfile. Manual GitOps PRs also need this fixed job, with their numeric `PR_NUMBER`. Configure a webhook/dispatcher or run it explicitly after the PR changes.

GitOps main must require the exact `boutique/gitops-policy` status, strict up-to-date checks, administrator enforcement, CODEOWNER approval and dismissal of stale reviews. The checked-in CODEOWNERS protects policy/configuration and staging/production changes. Dev image selections/chart versions/packages/records are intentionally unowned so they can auto-merge after the cryptographic policy check. To support that path, set the general required review count to zero while retaining CODEOWNER review for owned paths; alternatively require a review for dev and disable automated dev merge. Restrict who can publish the required status to the trusted integration when the repository protection mechanism supports it. Auto-merge must be enabled at the repository level. A base/head change during policy execution fails and requires a fresh check.

## Credential IDs

Enter values through Jenkins credential settings or an approved secret-management integration. Never store token values in tracked files.

| ID | Type / scope |
|---|---|
| `github-read` | Username/password; repository checkout only, independently scoped per controller |
| `ghcr-publish` | Username/password; release controller package publication |
| `gitops-pr` | Username/password; narrow GitOps contents/PR access and protection metadata read |
| `gitops-checks` | Secret text; fixed policy job repository read and commit-status write |
| `release-artifact-signing-key` | File; private Ed25519 key used by protected-main publication |
| `release-artifact-public-key` | File; independently trusted artifact verification key |
| `release-evidence-signing-key` | File; private Ed25519 key used by trusted deployment verification |
| `release-evidence-public-key` | File; independently trusted deployment verification key |
| `kubeconfig-dev`, `kubeconfig-staging`, `kubeconfig-production` | Files; namespace rollout/pod read plus Argo Application read, without secret access or deployment writes |
| `boutique-ca-dev`, `boutique-ca-staging`, `boutique-ca-production` | Files; trust material for the actual storefront TLS origins |
| `terraform-nonprod-backend`, `terraform-production-backend`, `terraform-audit-backend` | Files; environment-specific backend settings |
| `terraform-nonprod-variables`, `terraform-production-variables`, `terraform-audit-variables` | Files; environment-specific Terraform inputs |
| `rds-global-ca-bundle` | File; verified public RDS trust material for infrastructure/data setup |

The key generator stores separate artifact/evidence pairs under ignored mode-0700 `jenkins/.delivery-secrets/`, with mode-0600 files. Upload them securely, restrict private-key use to the intended trusted jobs and back them up securely. Never trust a public key supplied by a PR, caller parameter or signed envelope. Rotate through reviewed credential replacement and re-verification; replacing a verification key rejects old signatures until a planned retention/rotation strategy is applied.

Prefer short-lived GitHub App credentials with bindings compatible with these jobs; an installation ID alone is not a token. Make runtime packages public or supply separate namespace image-pull credentials. A publisher token does not give the cluster permission to pull private images.

## Configure the target runtime

Set `BOUTIQUE_DEV_ORIGIN`, `BOUTIQUE_STAGING_ORIGIN` and `BOUTIQUE_PRODUCTION_ORIGIN` on the release controller to the actual HTTPS origins, matching frontend `PUBLIC_ORIGIN`. Lab defaults are `https://dev.boutique.test:8443`, `https://staging.boutique.test:8443` and `https://production.boutique.test:9443`. Configure DNS/routing from the deploy agent and supply the relevant CA; loopback inside another container is not the Docker host.

The lab's `export-verifier` command creates expiring namespace-scoped kubeconfigs, without Secret reads or admin access. Renew the requested 24-hour credentials before a build/drill session. Continuous operation should use automated short-lived identity. Do not upload operator/admin kubeconfigs to Jenkins.

AWS Terraform agents use short-lived instance/workload roles, optionally assuming a reviewed deployment role. Scope resource/state permissions, including backend `.tflock` operations, before applying. File inputs contain backend/variables, not AWS access keys. Plans stay private; only a redacted action summary is archived, and approval applies the exact saved plan. Deployment agents also need access to private EKS endpoints. Terraform does not automatically install every platform controller.

## Release, promote and recover

Follow [deployment](runbooks/deployment.md) for the first complete release and routine dev → staging → production flow. A protected-main build archives its signed release and measured scan/SBOM before calling delivery; the artifacts can be consumed while that parent still waits. A parent delivery failure does not erase the already published immutable artifact.

Staging/prod promotions name a specific trusted `boutique-verify` build for the same image in the preceding environment; evidence is limited to 24 hours. Rollback selects a previously verified same-environment digest with retained evidence up to 30 days old. Both open reviewed GitOps changes and sign fresh verification after reconciliation. A merged PR alone is not deployment success. Keep production release/evidence artifacts for recovery and review database compatibility before approving a change.

Application build jobs validate and publish service-owned Helm packages; version-2 signatures bind the chart and image. Argo uses environment Helm values, with a third lab values file when appropriate. See [Helm delivery](../../boutique-gitops/docs/helm-delivery.md). The infrastructure job selects nonprod, production or the once-per-account audit root; audit needs backend/variables credentials, not the RDS CA.

The fixed GitOps policy job renders every cloud and lab monitoring profile using protected `render-monitoring.py`, and lints/renders the optional database and External Secrets charts. Candidate scripts are never executed. Monitoring configuration and chart files remain CODEOWNER-protected.
