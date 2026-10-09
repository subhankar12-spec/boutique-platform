# Deployment

Promote one tested immutable image through dev, staging and production. Jenkins prepares reviewed GitOps changes; Argo CD performs deployment; the trusted verifier checks rollout, runtime digests and the storefront through HTTPS. A merged pull request is not evidence of successful rollout.

## Prepare the foundations

Complete [Jenkins setup](../jenkins-setup.md), publish the independent repositories, configure registry pull access, and enforce the fixed `boutique/gitops-policy` check on GitOps main. The release controller needs artifact/evidence keys, named approvers, target origins/CAs, scoped verifier identities and separate release/deploy/policy executors.

Use a GitHub App or dedicated bot for GitOps PR creation and a different reviewer identity for owned paths. GitHub does not let a PR author approve their own PR. Using the owner's personal token to create the PR would prevent that same owner from satisfying mandatory owner review.

For the portable runtime, follow [production lab](../production-lab.md) to bootstrap both clusters and their TLS/network/controller foundations, then configure repository and GHCR pull secrets. These steps do not require AWS. The AWS alternative requires reviewed Terraform input/plan/apply and explicit platform controller/DNS/secret bootstrap; validate those foundations before starting delivery.

## First installation: release all four services together

An empty environment cannot pass the full application smoke test after receiving only one service image. Initialize **each environment** through one aggregate `boutique-bootstrap` change; use individual promotion jobs after that environment's first complete rollout.

1. Run protected-main `boutique-frontend/main`, `boutique-catalogue/main`, `boutique-cart/main` and `boutique-orders/main` with `DELIVER_TO_DEV=false`. Record their build numbers and signed image digests. Tests, scans, SBOM generation, GHCR publication and release signing still run. Release the incident adapter separately if installing monitoring. Automatically indexed first builds also skip individual dev delivery while the complete digest baseline is absent, leaving their signed artifacts available for bootstrap.
2. Run `boutique-bootstrap` with `TARGET=dev`, the four `*_BUILD` numbers and `PAUSE_FOR_INITIAL_SYNC=true`. The job verifies signed artifacts, opens one PR selecting all four digests and runs the fixed policy job. Dev can auto-merge when the documented branch protection permits it.
3. After merge, the bootstrap job pauses before verification. Update the clean local GitOps checkout on `main` to published main without discarding local changes, then create only dev's Argo Application:

   ```bash
   git -C ../boutique-gitops pull --ff-only origin main
   python3 scripts/production-lab.py deploy --cluster nonprod --environment dev
   python3 scripts/production-lab.py readiness --cluster nonprod --environment dev
   ```

   Run these from `boutique-platform` on the lab operator host. Keep the pause until the foundation/application is ready, then continue as `release-manager`. The job runs four trusted verification children; retain the build number for each service's dev evidence.
4. Repeat `boutique-bootstrap` with `TARGET=staging`, the same four release builds and each service's dev `*_EVIDENCE_BUILD`. Supply evidence less than 24 hours old for those exact digests. Review and merge the staging PR. During the initial-sync pause, run `deploy` and `readiness` with `--cluster nonprod --environment staging`, then continue and retain its four staging verification builds.
5. Repeat with `TARGET=production`, the same releases and matching staging evidence. The named `release-manager` approves the planned change; owned paths also require GitHub CODEOWNER review. During the first-sync pause, run `deploy`/`readiness` with `--cluster production --environment production`. Continue only after the intended production foundation is ready and retain its four verification builds.

The AWS equivalent creates/reconciles that environment's reviewed Argo Application during the pause. The preceding-environment evidence and production approval still apply. An aggregate installation does not bypass tests, signatures or promotion ordering.

The bootstrap holds the selected environment's delivery lock through verification. Finish or abort it before another delivery to that environment. An aborted/failed unmerged request is closed; a merge is never automatically reverted. If a merged deployment fails, investigate and use the recovery workflow.

## Routine service delivery

A reviewed protected-main service build normally uses `DELIVER_TO_DEV=true`. It publishes once, archives signed quality artifacts, then invokes `boutique-promote` for dev. The source tag cannot be overwritten; retry deployment with the existing release artifact rather than rebuilding that tag.

Run `boutique-promote` for staging with `SERVICE`, exact `IMAGE`, original `RELEASE_BUILD` and that image's dev `EVIDENCE_BUILD`. Review the planned diff and the GitOps PR. After merge, the job waits for Synced/Healthy Argo and all four service rollouts, measures Pods/runtime digest and runs the functional HTTPS smoke suite. It signs fresh staging evidence only when those checks pass.

For production, use the same digest/release build and its successful staging verification build. Review migration compatibility, impact and rollback candidate before `release-manager` approval and owner review. Promotion evidence expires after 24 hours; re-run trusted verification of the source environment when necessary. Never substitute a different environment or image's evidence.

If the PR head or base changes, rerun the fixed `boutique-gitops-check` against its current contents/base. No candidate Jenkinsfile or caller-supplied public key may satisfy the required check. The delivery job has a bounded merge wait; do not leave it waiting for an unattended long-term release.

## Accept the release

Use Jenkins `verification-evidence.json` and archived native/HTTP reports as the acceptance record. Check the exact service digest, selected environment, Argo synchronized commit and successful smoke checks. A later protected-main Argo revision is accepted only when ancestry and unchanged selected digest are proven. The measured HTTPS origin must match frontend configuration.

Review Grafana metrics, logs and new alerts after rollout. Monitoring installation uses its own tested incident-adapter digest and reviewed profile change; it is not automatically promoted by an application image change. Local receiver drills use mocks, and activating live Slack/ServiceNow requires real secret configuration and an explicitly authorized receiver test.

Retain release, scan/SBOM and successful verification artifacts for recovery. Schedule [backup/restore](backup-restore.md), network-policy and incident-worker failure drills and record their results. Start a [rollback](rollback.md) when a known-good image is needed; use corrective forward migrations if schema compatibility prevents image recovery.
