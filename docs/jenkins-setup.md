# Jenkins setup

## Local controllers

```bash
cd boutique-ci/jenkins
./scripts/init-local.sh
docker compose up -d --build
```

Validation binds to loopback port 8090; release binds to 8091. Both use JCasC, zero controller executors and persistent Jenkins home volumes. Credentials are in ignored `.env`. Treat the single local admin as a bootstrap account; remote deployments require TLS and a configured identity provider and scoped authorization. Input approver groups `release-managers` and `platform-admins` must exist in that identity provider before the approval jobs can be used.

The local baseline deliberately uses two controllers: any PR Jenkinsfile can execute arbitrary code, select labels and attempt credential access. Labels on one controller are not a sufficient isolation boundary. The validation controller gets only scoped read credentials and disposable build agents. Trusted release/deploy agents and all publishing, GitOps and AWS credentials belong exclusively to the release controller.

## Repository wiring

1. Create the eight GitHub repositories with the matching names and push their individual sources to `main`.
2. Configure an untrusted Folder-scoped `boutique-ci` shared library on validation, retrieving this repo through read-only credentials. Pin its default version to a reviewed commit and disallow overrides. Add the service multibranch jobs from `jenkins/jobs/validation.groovy` using a reviewed Job DSL seed.
3. Configure signed GitHub webhooks and branch discovery. Fork PR discovery is disabled by the seed. Never put release credentials on validation even if forks are disabled.
4. On release, create pipeline jobs using `jenkins/jobs/release.groovy`, and an infrastructure SCM pipeline using `boutique-infrastructure/Jenkinsfile`. Keep pipeline definitions on a protected trusted branch.
5. Protect application/library/infrastructure/GitOps `main` branches: reviews, required checks, restricted force pushes, no bot bypass of production reviews.

## Credential IDs (enter values securely in Jenkins)

| ID | Type / use |
|---|---|
| github-read | Scoped HTTPS repository checkout credential |
| ghcr-publish | Username/password binding; GHCR token with package publication permission |
| gitops-pr | Username/password binding; narrow GitOps repository write + PR credential |
| kubeconfig-dev / staging / production | File credentials containing limited rollout-read access, not cluster-admin |

For GitHub Apps, install the integration that refreshes short-lived credentials and configure bindings compatible with these jobs; do not put an installation ID where a token is expected. Registry credentials need actual package write access. Make lab packages public or configure separate pull credentials in each namespace; publication alone does not grant cluster pull access.

AWS Terraform agents obtain short-lived instance/workload role credentials, optionally assuming a reviewed deployment role. IAM permission policies must be scoped to the target account and resources before enabling apply; no all-powerful credential is supplied here. Configure Terraform backend permissions for state objects and `.tflock` creation/deletion. Deployment agents need a route to private EKS endpoints.

## Promotion

Release a main-branch commit. Record its Jenkins artifact digest. Promote that digest to dev; merge the GitOps PR and wait for Argo CD. Run verify for dev. Promote to staging, merge and verify. Production approval reviews that staging build's recorded deployed digests and smoke result; merge production PR, then verify production. Promotion itself is not proof of successful rollout.

Set actual storefront hostnames in verification pipeline and frontend overlays together. Smoke tests send the same origin they target. Back up Jenkins home and test restoration; lock and review plugin versions after bootstrap.
