# Main deployment guide: Jenkins → GitOps → Argo CD → kind

This is the recommended deployment flow for your DevOps project.
Follow the numbered phases in order on your Debian laptop or a suitable
Linux Docker host.

**Prepare the Kubernetes environment first. Configure CI/CD next.
Let the delivery system deploy the application.**

You do not need to run the app with Compose or manually apply the app's
Deployments before following this guide. Those are optional exercises.

## The complete flow

~~~text
ONE-TIME SETUP — you prepare the platform:

1. Clone repositories and install tools
2. Create the kind clusters and their platform controllers
3. Configure Jenkins, agents, credentials and GitHub protection

FIRST APPLICATION RELEASE — Jenkins and Argo deploy the app:

4. Jenkins builds/tests/publishes all four service releases
5. Jenkins prepares the first dev GitOps release
   → GitOps PR passes policy and merges
   → Jenkins pauses for initial Argo connection
   → You create the dev Argo Application
   → Argo deploys the app
   → You resume Jenkins
   → Jenkins verifies the running app
6. Promote the same releases to staging, then production

OPERATIONS:

7. Install monitoring and practise rollback/recovery
~~~

The first Argo connection is a one-time operator setup step per environment.
After that, routine delivery updates GitOps and Argo reconciles automatically.

| Action | Who does it? | Does it deploy the storefront? |
| --- | --- | --- |
| Clone repositories | You | No: downloads source/configuration |
| Create clusters and install controllers | You, using the lab helper | No: prepares Kubernetes infrastructure |
| Start/configure Jenkins | You | No: prepares the delivery system |
| Build/publish service releases | Jenkins agents | No: produces registry artifacts |
| Select approved releases in GitOps | Jenkins plus required reviewers | Changes desired state |
| Connect the initial Argo Application | You, during Jenkins's first-install pause | Enables Argo to reconcile that environment |
| Reconcile Deployments, Services and data resources | Argo CD | Yes |
| Check rollout and real HTTPS behavior | Jenkins verifier | Confirms deployment; signs evidence |

## Before phase 1

Use a supported **Linux amd64 Debian host**, working Docker Engine/Compose,
and adequate capacity. The two-cluster doctor requires at least 16 GiB RAM and
30 GiB free Docker storage; 24–32 GiB is recommended for clusters, with
additional capacity for Jenkins and isolated build VMs.

The runtime has:

| Cluster | Application environments | Context |
| --- | --- | --- |
| boutique-nonprod | dev and staging, separate namespaces/data | kind-boutique-nonprod |
| boutique-production | production | kind-boutique-production |

This full lab uses its own clusters. An existing single kind cluster can remain
for other work; it is not automatically converted into these two clusters.
Two clusters on one host still share that host's failure domain.

Complete [Debian prerequisites](beginner-guide.md#6-prepare-your-debian-laptop)
if Docker is not working yet. Install the basic packages before cloning:

~~~bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates curl git openssl unzip jq \
  python3 python3-yaml python3-jsonschema
docker version
docker compose version
~~~

Do not continue until Docker's server and Compose work.

## Phase 1 — Clone the repositories and install tools

In your operator terminal:

~~~bash
export BOUTIQUE_ROOT="$HOME/devops-boutique"
mkdir -p "$BOUTIQUE_ROOT"
cd "$BOUTIQUE_ROOT"

for repo in frontend catalogue cart orders ci infrastructure gitops platform; do
  if [ -e "boutique-$repo" ]; then
    printf 'Keeping existing directory: boutique-%s\n' "$repo"
  else
    git clone "https://github.com/subhankar12-spec/boutique-$repo.git" || break
  fi
done
~~~

Preserve existing checkouts/changes. Verify that all eight directories are
the intended repositories. For a different workspace, export its actual path.

Install the reviewed tools:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
./scripts/install-tools.sh "$PWD/.tools"
export PATH="$BOUTIQUE_ROOT/boutique-platform/.tools:$PATH"
python3 scripts/production-lab.py fetch-tools
python3 scripts/production-lab.py fetch-manifests
python3 scripts/production-lab.py doctor
~~~

The helper downloads its locked kind and controller manifests and verifies
their checksums. The doctor checks capacity and supported host capabilities.
If it fails, fix the host prerequisite before creating clusters.

**Checkpoint:** repositories and tools are ready. No app has been deployed.

## Phase 2 — Prepare Kubernetes, without deploying the app

Check your LAN/VPN/Docker routes against the configured pod CIDRs before
bootstrap. The nonprod pod range includes 192.168.0.0/16 and production uses
172.20.0.0/16. Resolve overlaps through reviewed kind/Calico networking changes.

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py bootstrap --cluster nonprod
python3 scripts/production-lab.py bootstrap --cluster production
~~~

This creates clusters and installs **Calico, Argo CD, cert-manager and Traefik**,
plus per-cluster private TLS trust. These are infrastructure/controllers.
It does not install the complete four-service Boutique application.

Export the private operator kubeconfig paths:

~~~bash
export BOUTIQUE_NONPROD_KUBECONFIG="$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/nonprod/kubeconfig"
export BOUTIQUE_PRODUCTION_KUBECONFIG="$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/production/kubeconfig"
export KUBECONFIG="$BOUTIQUE_NONPROD_KUBECONFIG:$BOUTIQUE_PRODUCTION_KUBECONFIG"

kubectl --context kind-boutique-nonprod get nodes
kubectl --context kind-boutique-production get nodes
kubectl --context kind-boutique-nonprod -n argocd get pods
kubectl --context kind-boutique-production -n argocd get pods
~~~

Keep administrative kubeconfigs and generated CA private keys out of Git and
out of Jenkins verification credentials. Preserve the helper's .state directory.

Add this line to your laptop's /etc/hosts using sudoedit:

~~~text
127.0.0.1 dev.boutique.test staging.boutique.test production.boutique.test
~~~

Follow [hostname and TLS trust setup](beginner-guide.md#154-configure-hostnames-and-tls-trust).
The eventual storefront addresses are:

~~~text
https://dev.boutique.test:8443
https://staging.boutique.test:8443
https://production.boutique.test:9443
~~~

These addresses will not serve the application yet.

**Checkpoint:** nodes/controllers are healthy and trust/routing are prepared.
Do not run the application's local-profile kubectl apply here.

## Phase 3 — Configure the delivery system and its identities

### 3A. Start Jenkins controllers

~~~bash
cd "$BOUTIQUE_ROOT/boutique-ci/jenkins"
./scripts/init-local.sh
python3 scripts/init-signing-keys.py
docker compose up -d --build
docker compose ps
~~~

The validation UI is http://127.0.0.1:8090 and release is
http://127.0.0.1:8091. Retrieve generated account passwords locally from the
ignored .env file. Review the pinned CI library commit.

Starting these containers does not create working build agents.

### 3B. Connect agents before enabling builds

Complete [the agent setup](beginner-guide.md#132-allocate-agents-by-role)
through its native VM/container connection instructions.
You need:

| Controller | Required label | Responsibility |
| --- | --- | --- |
| Validation | isolated-builder | Disposable untrusted validation builds |
| Release | trusted-release | Protected-main tests/builds/publication |
| Release | trusted-deploy | GitOps changes and scoped runtime verification |
| Release | policy-check | Fixed protected GitOps policy evaluation |

Use separate build VMs/rootless daemons for validation and trusted release.
Do not attach either untrusted build work or its Docker daemon to the trusted
deploy boundary. The policy job needs a distinct executor.
The optional terraform-trusted agent is unnecessary for kind.

### 3C. Configure credentials and branch protection

Complete [credential IDs and GitHub protection](beginner-guide.md#14-configure-delivery-credentials-and-github-protection).
This includes:

- Read-only SCM identities.
- GHCR publication identity.
- GitOps PR bot and separate human reviewer.
- Fixed GitOps check credential and required boutique/gitops-policy status.
- Separate artifact and evidence signing key pairs.
- Protected main branches and CODEOWNER review of owned paths.

Do not use the same identity to author and approve a protected PR.
Keep validation free of release/deploy credentials.

### 3D. Prepare runtime secrets and verifier access

Follow [registry/runtime secrets](beginner-guide.md#155-create-registry-and-runtime-secrets)
to create a private GHCR read-token file outside the checkouts.
The GitOps repository is public, so its optional repo-token-file can be omitted.

Using your real token-owner username, provision secrets in both clusters:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py secrets --cluster nonprod \
  --registry-token-file "$HOME/.config/boutique-secrets/ghcr-read-token" \
  --registry-user subhankar12-spec
python3 scripts/production-lab.py secrets --cluster production \
  --registry-token-file "$HOME/.config/boutique-secrets/ghcr-read-token" \
  --registry-user subhankar12-spec
~~~

These commands configure credentials and namespaces; the app still is not
running. Existing initialized data requires its matching credentials.

Export restricted Jenkins verifier identities:

~~~bash
python3 scripts/production-lab.py export-verifier --environment dev --duration 24h
python3 scripts/production-lab.py export-verifier --environment staging --duration 24h
python3 scripts/production-lab.py export-verifier --environment production --duration 24h
~~~

Upload the generated jenkins-verifier-ENV.json files to the matching
kubeconfig-ENV Jenkins credentials and matching public root certificates to
boutique-ca-ENV. See [the exact mapping and access checks](beginner-guide.md#156-export-jenkinss-restricted-verifier-identities).
Do not upload operator/admin kubeconfigs. Renew expiring identities before
the delivery session.

The trusted-deploy agent must reach the cluster APIs and HTTPS storefront names.
For local host-network container agents, use the documented --add-host entries;
host networking does not inherit the laptop's /etc/hosts.

### 3E. Seed jobs

Run reviewed validation/release Job DSL seeds following
[the seed instructions](beginner-guide.md#136-create-the-seed-jobs).
Inspect all created jobs and manually scan projects if webhooks cannot reach
your loopback controllers.

Initial discovery can already build/publish main. If that happens, retain
its valid successful release artifacts instead of rebuilding the same source.
Individual dev delivery is skipped while the complete baseline is absent.

**Checkpoint:** trusted agents are online, credentials/protection are configured,
jobs exist and verifier access is restricted. No prior manual app deployment
is required.

## Phase 4 — Let Jenkins build the first four releases

On the **release controller**, run these protected-main jobs:

~~~text
boutique-frontend/main
boutique-catalogue/main
boutique-cart/main
boutique-orders/main
~~~

For the first release, use **DELIVER_TO_DEV=false**.
Jenkins still tests, builds, scans, generates an SBOM, packages charts,
publishes to GHCR and signs release records.

It does not try to verify an incomplete app after deploying only one service.
The next phase selects all four releases together.

Record each successful release build number:

| Service | Release job | Build number to record |
| --- | --- | --- |
| frontend | boutique-frontend/main | Its successful release build |
| catalogue | boutique-catalogue/main | Its successful release build |
| cart | boutique-cart/main | Its successful release build |
| orders | boutique-orders/main | Its successful release build |

Inspect archived release.json, signed release record, packaged chart and
scan/SBOM. These job-specific build numbers are not commit hashes.
Reuse an already published valid release; immutable source tags/chart versions
cannot be overwritten by rerunning publication.

**Checkpoint:** four tested signed releases exist. Kubernetes still has no
complete application baseline.

## Phase 5 — Deploy the first dev release through GitOps and Argo

### 5A. Start the aggregate bootstrap job

Run **boutique-bootstrap** with:

~~~text
TARGET=dev
FRONTEND_BUILD=<actual frontend release build number>
CATALOGUE_BUILD=<actual catalogue release build number>
CART_BUILD=<actual cart release build number>
ORDERS_BUILD=<actual orders release build number>
AUTO_MERGE_DEV=true
PAUSE_FOR_INITIAL_SYNC=true
~~~

Leave the four evidence-build fields empty for dev.
Use AUTO_MERGE_DEV=false if your chosen protection requires manual dev review.

Jenkins validates four signed artifacts, prepares one GitOps PR, runs the
fixed policy job and waits for the guarded merge.
Review the actual PR/image/chart selections.

### 5B. At the first-install pause, connect Argo

Wait for the job to reach **Initialize the first Argo CD synchronization**.
The approved GitOps change must already be merged before this step.

On the operator laptop:

~~~bash
git -C "$BOUTIQUE_ROOT/boutique-gitops" status --short
git -C "$BOUTIQUE_ROOT/boutique-gitops" branch --show-current
~~~

Continue only if status is empty and the branch command prints main. Preserve existing edits
rather than resetting them. Then:

~~~bash
git -C "$BOUTIQUE_ROOT/boutique-gitops" pull --ff-only origin main
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py deploy --cluster nonprod --environment dev
kubectl --context kind-boutique-nonprod -n argocd get applications
~~~

**What that deploy command does:** creates the reviewed Argo Application and
AppProject. It does not build images or manually apply the app's Deployments.
Argo reads the merged remote GitOps configuration and creates/reconciles the
application resources.

Do not substitute the optional local-profile manifest here.
Do not activate staging while its release selections still contain bootstrap
images.

Wait for boutique-dev to be **Synced and Healthy**, then:

~~~bash
python3 scripts/production-lab.py readiness --cluster nonprod --environment dev
python3 scripts/production-lab.py verify --environment dev
~~~

Readiness checks the current Argo state; if synchronization is still in progress,
inspect/wait and rerun. The verify command exercises the real HTTPS app and
creates synthetic lab orders.

### 5C. Resume Jenkins verification

Resume the pause as release-manager.
Jenkins runs four boutique-verify builds and signs successful runtime evidence.
Retain the four **dev verification build numbers**, separately from the original
four service release build numbers.

Open **https://dev.boutique.test:8443** using the configured nonprod CA trust.

**Checkpoint:** the app was delivered by Argo from approved GitOps selections
and has successful signed Jenkins verification.

## Phase 6 — Promote the same releases to staging and production

For each environment's first installation, run boutique-bootstrap again.
Reuse the same four release build numbers; do not rebuild per environment.

| First target | Evidence input | Required approval | At its initial-sync pause |
| --- | --- | --- | --- |
| staging | Four corresponding dev verification builds | GitHub CODEOWNER review | Connect staging in nonprod |
| production | Four corresponding staging verification builds | release-manager input plus GitHub CODEOWNER review | Connect production in its separate cluster |

Use TARGET=staging or production, AUTO_MERGE_DEV=false,
PAUSE_FOR_INITIAL_SYNC=true, and the four matching *_EVIDENCE_BUILD parameters.
Preceding-environment evidence must match the release and be less than 24 hours
old. Renew evidence/identities if the session takes longer.

After each reviewed PR merges, pull clean GitOps main as in phase 5.
At staging's pause:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py deploy --cluster nonprod --environment staging
~~~

Wait for Synced/Healthy, then:

~~~bash
python3 scripts/production-lab.py readiness --cluster nonprod --environment staging
python3 scripts/production-lab.py verify --environment staging
~~~

Resume Jenkins and record staging evidence before starting production.
At production's approved first-install pause:

~~~bash
python3 scripts/production-lab.py deploy --cluster production --environment production
~~~

Wait for Synced/Healthy, then:

~~~bash
python3 scripts/production-lab.py readiness --cluster production --environment production
python3 scripts/production-lab.py verify --environment production
~~~

Resume Jenkins and retain production verification.
See [the complete parameter walkthrough](beginner-guide.md#163-bootstrap-staging-from-the-same-releases)
for the exact evidence fields.

For **routine releases after initialization**:

~~~text
Service PR → validation → review/merge main
  → trusted release build (DELIVER_TO_DEV=true)
  → GitOps dev selection → Argo rollout → signed dev verification
  → staging promotion with dev evidence
  → production approval/promotion with staging evidence
~~~

There is no repeated first-install pause or manual app apply in normal service
promotion. Use boutique-promote and its existing Argo Application.

## Phase 7 — Add monitoring and recovery practice

Release the incident bridge with **boutique-platform/main**.
Select its tested digest in a reviewed monitoring GitOps change, then install
the monitoring Argo Applications.

Follow [Kubernetes monitoring deployment](beginner-guide.md#186-deploy-monitoring-in-the-full-kind-lab).
That subsection is the monitoring path for these clusters; Compose monitoring
is an optional separate fixture exercise.

Then practise:

- [Routine release and signed rollback](beginner-guide.md#17-perform-a-routine-release-and-rollback).
- [Network-policy and isolated restore drills](beginner-guide.md#204-practice-the-kind-labs-recovery-and-policy-drills).
- [Recovery targets and independent backup requirements](recovery-targets.md).

Real Slack/ServiceNow activation is a separate credential/receiver setup.
The lab starts with internal fixtures and sends no real external notifications.

## Where to go when you are stuck

Use this document as the **order of work**.
Use the [complete beginner guide](beginner-guide.md) for the detailed explanation
of the phase you are currently doing.

| Current phase | Read |
| --- | --- |
| Tools/host | Beginner guide sections 6–7 |
| Cluster foundation | Section 15.1–15.4 |
| Jenkins agents/seeds | Section 13 |
| Keys/GitHub protection | Section 14 |
| Runtime secrets/verifier | Section 15.5–15.6 |
| Initial builds/bootstrap | Section 16 |
| Routine promotion/rollback | Section 17 |
| Monitoring | Section 18.6 onward |
| Failures | Section 21 |

Do not move to the next phase until its checkpoint passes. A waiting
Jenkins executor means agent setup; a missing registry image means publication;
an Argo failure means reconciliation/runtime. They need different fixes.

Commands and ordering describe the implementation; the full end-to-end
deployment still needs acceptance on your actual host. No AWS apply or
paid cloud resource is needed for this flow.
