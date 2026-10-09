# Shipyard Boutique: a beginner's complete architecture and deployment guide

This is the starting point for understanding and operating this project. You do
not need to understand every file before starting. Work through the checkpoints,
and return to the repository maps when a command or pipeline mentions a file.

The project is a small ecommerce application surrounded by a substantial DevOps
delivery system. The application gives you something real to deploy: browse
products, maintain a cart and create orders. The DevOps system teaches builds,
tests, security checks, image registries, Helm, GitOps, Kubernetes, monitoring,
secrets, promotion, rollback and recovery.

This guide describes the source published under the GitHub owner
**subhankar12-spec**. The eight repositories are public. The Kubernetes/AWS
configuration is not an already-running hosted service. In particular, the full
two-cluster delivery chain still needs acceptance on your laptop or another
supported host. A successful command in one phase does not establish completion
of the later phases.

## Contents

- [1. Choose a learning path](#1-choose-a-learning-path)
- [2. Understand the whole system](#2-understand-the-whole-system)
- [3. Understand the application request flow](#3-understand-the-application-request-flow)
- [4. Understand the eight repositories](#4-understand-the-eight-repositories)
- [5. Understand the recurring file types](#5-understand-the-recurring-file-types)
- [6. Prepare your Debian laptop](#6-prepare-your-debian-laptop)
- [7. Clone the workspace](#7-clone-the-workspace)
- [8. Run the application with Docker Compose](#8-run-the-application-with-docker-compose)
- [9. Deploy the application in your kind cluster](#9-deploy-the-application-in-your-kind-cluster)
- [10. Inspect and understand the Kubernetes deployment](#10-inspect-and-understand-the-kubernetes-deployment)
- [11. Understand Helm and the environment profiles](#11-understand-helm-and-the-environment-profiles)
- [12. Understand the Jenkins delivery architecture](#12-understand-the-jenkins-delivery-architecture)
- [13. Configure Jenkins controllers and agents](#13-configure-jenkins-controllers-and-agents)
- [14. Configure delivery credentials and GitHub protection](#14-configure-delivery-credentials-and-github-protection)
- [15. Bootstrap the two-cluster production learning lab](#15-bootstrap-the-two-cluster-production-learning-lab)
- [16. Build releases and install dev staging and production](#16-build-releases-and-install-dev-staging-and-production)
- [17. Perform a routine release and rollback](#17-perform-a-routine-release-and-rollback)
- [18. Install and understand monitoring](#18-install-and-understand-monitoring)
- [19. Understand the AWS reference](#19-understand-the-aws-reference)
- [20. Practice failures backup and recovery](#20-practice-failures-backup-and-recovery)
- [21. Troubleshoot by following the dependency chain](#21-troubleshoot-by-following-the-dependency-chain)
- [22. Stop safely and resume later](#22-stop-safely-and-resume-later)
- [23. Know what is implemented and what remains](#23-know-what-is-implemented-and-what-remains)
- [24. Follow a practical learning sequence](#24-follow-a-practical-learning-sequence)
- [25. Glossary and command reference](#25-glossary-and-command-reference)

## 1. Choose a learning path

There are three deployment tracks, with a useful intermediate kind exercise:

| Path | Purpose | What it starts | What it does not demonstrate |
| --- | --- | --- | --- |
| Docker Compose | Understand the app and debug services | Four apps, PostgreSQL and Redis on your laptop | Kubernetes, GitOps or signed promotion |
| Single kind exercise | Learn Pods, Services, storage and Helm rendering | The same app in one chosen kind cluster | The complete protected delivery chain or cluster separation |
| Two-cluster production learning lab | Practice the intended delivery and operational boundaries | Nonprod and production kind clusters, controllers, signed releases, optional monitoring | Independent host failure domains or managed database HA |
| AWS reference | Study/configure managed infrastructure | Terraform definitions for EKS, VPCs, managed data, audit and observability | Automatic installation of every Kubernetes controller or a free deployment |

Start with sections 6–10. You can get the app running without first creating
Jenkins credentials, Slack webhooks, ServiceNow instances or an AWS account.

Then study sections 11–14 and build the full lab in sections 15–18. The full
delivery track is intentionally more involved: identities, keys, branch
protection, agents and registry access are operator configuration.

Do not mix the single-kind local image profile with the production learning
profile. The first uses local tags for an introductory exercise. The second
requires tested registry images selected by immutable digest and signed release
records.

### Hardware expectations

| Exercise | Practical planning guidance |
| --- | --- |
| Compose only | Approximately 4 GiB available RAM, plus build/download storage |
| One kind cluster | More capacity than Compose; an 8–12 GiB machine is a starting point, not a performance guarantee |
| Two-cluster lab | The doctor requires at least 16 GiB RAM and 30 GiB free Docker storage; 24–32 GiB RAM is recommended |
| Clusters plus controllers and isolated build VMs | Budget additional memory/storage for Jenkins, Java builds and both agent VMs; 32 GiB or more is much more comfortable |

The two-cluster lab has six Kubernetes node containers: one control plane and
two workers per cluster. A laptop can run out of memory even though a manifest's
syntax is valid. Check the actual host before pulling several large stacks.

## 2. Understand the whole system

Think of five connected layers:

1. **Application:** the storefront, product API, cart API and orders API.
2. **Data:** Redis for carts and PostgreSQL for durable orders.
3. **Runtime:** Docker Compose, or Kubernetes with networking, TLS and storage.
4. **Delivery:** Jenkins builds artifacts; GitOps records the selected release;
   Argo CD reconciles that release into Kubernetes.
5. **Operations:** metrics, logs, alerts, incidents, verification and recovery.

~~~mermaid
flowchart LR
    Browser["Your browser"] --> Frontend["Frontend / API gateway"]
    Frontend --> Catalogue["Catalogue: Go"]
    Frontend --> Cart["Cart: Python"]
    Frontend --> Orders["Orders: Java"]
    Cart --> Redis["Redis"]
    Orders --> Postgres["PostgreSQL"]
    Orders --> Catalogue
    Orders --> Cart
    Apps["Application metrics"] --> Prometheus["Prometheus"]
    Prometheus --> Grafana["Grafana"]
    Prometheus --> Alertmanager["Alertmanager"]
    Alertmanager --> Slack["Slack or local mock"]
    Alertmanager --> Bridge["Incident adapter"]
    Bridge --> Queue["Dedicated incident queue"]
    Bridge --> SN["ServiceNow or local mock"]
    Logs["Container logs"] --> Alloy["Grafana Alloy"]
    Alloy --> Loki["Loki"]
    Loki --> Grafana
~~~

The catalogue, cart and orders services are backend services. They do not need
public browser ports. The frontend is the browser entry point and forwards
requests to the appropriate internal service.

Jenkins and Argo CD are management tools. A customer request does not travel
through Jenkins, Terraform or Argo CD. Those tools decide and maintain which
application release is running.

### Who changes what?

| Actor | Responsibility |
| --- | --- |
| You, as a developer | Change application source and service-owned Helm templates through review |
| Jenkins build job | Test/build/scan; publish the image and chart; sign release information |
| Jenkins delivery job | Validate releases and prepare a GitOps pull request |
| GitHub checks/review | Enforce policy and approval before the configuration merges |
| Argo CD | Read merged GitOps configuration and reconcile Kubernetes resources |
| Kubernetes | Schedule Pods, restart failed containers and route traffic through Services |
| Trusted verifier | Check the actual deployment and HTTP behavior, then sign evidence |
| You, as an operator | Configure identities, bootstrap foundations, investigate alerts and exercise recovery |

This division explains why there are many files. A Dockerfile answers “how is
the app packaged?” A Helm template answers “how should Kubernetes run it?”
A pipeline answers “when is a release allowed?” A runbook answers “what do I do
when it fails?” They serve different purposes.

## 3. Understand the application request flow

### 3.1 Browse products

1. Your browser loads the frontend page.
2. Its JavaScript requests the frontend endpoint **GET /api/products**.
3. The frontend calls the internal catalogue endpoint **GET /products**.
4. The catalogue returns the sample product list.

The catalogue is intentionally simple and has no separate catalogue database.
You can concentrate on deployment rather than implementing inventory management.

### 3.2 Add an item to the cart

1. The frontend issues a signed anonymous-session cookie.
2. The browser sends **PUT /api/cart/items/mug** with a quantity.
3. The frontend verifies the session and the mutation request's Origin.
4. It calls the cart service using the session identity it derived itself.
5. The cart service stores the session's cart in Redis.

The frontend does not trust an arbitrary session header supplied by a browser.
The cookie is HttpOnly and SameSite=Strict. HTTPS profiles enable Secure.
Changing the session signing key invalidates existing sessions; this is why
secret preservation and backup matter.

### 3.3 Checkout

1. The browser sends **POST /api/orders** with an idempotency key.
2. The frontend forwards the request with the verified session identity.
3. Orders reads the cart and catalogue data.
4. It computes the amount on the server, using integer minor currency units.
5. PostgreSQL stores the order and its line-item snapshot in a transaction.

An **idempotency key** identifies one checkout attempt. Repeating that attempt,
including concurrent retries, returns the same order instead of creating
several orders. The implementation combines PostgreSQL advisory locks with a
unique session/key constraint.

Checkout retains the cart. A different checkout key can create another order.
The app has no actual payment processor, stock reservation, account login or
email service. Orders belong to anonymous sessions, so it is a learning
application rather than a finished commercial storefront.

### 3.4 Ports and dependencies

| Component | Container/service port | Main dependency |
| --- | --- | --- |
| Frontend | 8080 | Catalogue, cart, orders and a session signing secret |
| Catalogue | 8081 | Its packaged product data |
| Cart | 8082 | Redis credentials/connectivity |
| Orders | 8083 | PostgreSQL, catalogue and cart |
| Incident adapter | 8084 | SQLite or its separate PostgreSQL queue and receiver credentials |
| PostgreSQL | 5432 | Persistent storage and matching database credentials |
| Redis | 6379 | Persistent storage and matching Redis credentials |

Application endpoints include **/health/live**, **/health/ready** and metrics
endpoints. Liveness asks whether the process should be restarted. Readiness asks
whether it can currently serve traffic. A running Java process with a broken
database connection is not necessarily ready.

## 4. Understand the eight repositories

Your local folder contains eight independent Git repositories. Each has its own
history, main branch, origin and access rules. A parent workspace folder or VS
Code workspace does not turn them into a monorepo.

| Repository | Main question it answers | Read this first |
| --- | --- | --- |
| [boutique-frontend](https://github.com/subhankar12-spec/boutique-frontend) | How does the browser reach the app safely? | src/server.js, src/session.js, Dockerfile |
| [boutique-catalogue](https://github.com/subhankar12-spec/boutique-catalogue) | Where do products and prices come from? | main.go, metrics.go, Dockerfile |
| [boutique-cart](https://github.com/subhankar12-spec/boutique-cart) | How are per-session carts stored? | app.py, Dockerfile |
| [boutique-orders](https://github.com/subhankar12-spec/boutique-orders) | How does checkout create durable orders? | OrdersController.java and the Flyway migration |
| [boutique-ci](https://github.com/subhankar12-spec/boutique-ci) | How do we test, publish and authorize delivery? | vars/servicePipeline.groovy and pipelines/ |
| [boutique-infrastructure](https://github.com/subhankar12-spec/boutique-infrastructure) | What AWS resources would support this system? | README.md, environments/ and modules/platform/ |
| [boutique-gitops](https://github.com/subhankar12-spec/boutique-gitops) | What release/configuration should each environment run? | environments/dev/ and docs/helm-delivery.md |
| [boutique-platform](https://github.com/subhankar12-spec/boutique-platform) | How do we assemble, verify and operate everything? | This guide, scripts/ and local/ |

### 4.1 Frontend repository

~~~text
boutique-frontend/
  src/server.js          HTTP entry point and internal API forwarding
  src/session.js         Signed anonymous-session handling
  src/metrics.js         HTTP/process metrics
  public/                HTML, CSS and browser JavaScript
  tests/                 Session and metrics tests
  package.json           Node commands and project metadata
  package-lock.json      Resolved dependency lock
  Dockerfile             Test stage and non-root runtime image
  Jenkinsfile            Calls the common service pipeline
  helm/                  Kubernetes chart owned by this service
~~~

The frontend uses Node.js 22 in its image. The browser assets are ordinary
HTML/CSS/JavaScript; this project does not require learning a large frontend
framework.

Read the frontend URL settings when diagnosing a failure: internal service
URLs are Kubernetes/Compose addresses, while **PUBLIC_ORIGIN** is the address
the browser uses. A wrong public origin can reject a cart mutation even when
every Pod is healthy.

### 4.2 Catalogue repository

~~~text
boutique-catalogue/
  main.go                Product HTTP API and health behavior
  metrics.go             Request metrics
  main_test.go           Go tests
  go.mod                 Go module metadata
  Dockerfile             Run tests, compile, then package a small runtime
  Jenkinsfile            Common pipeline with service=catalogue
  helm/                  Deployment, Service, account and optional PDB
~~~

Go compiles the service into a binary. A multistage Docker build leaves the
compiler and test tooling out of the final runtime. The catalogue is useful for
studying a relatively stateless microservice.

### 4.3 Cart repository

~~~text
boutique-cart/
  app.py                 FastAPI routes, validation and Redis client
  tests/test_validation.py
  requirements.in        Human-maintained runtime dependency input
  requirements.txt       Hash-locked runtime dependencies
  requirements-dev.in    Test dependency input
  requirements-dev.txt   Hash-locked test dependencies
  Dockerfile             Dependency/test/runtime stages
  Jenkinsfile
  helm/
~~~

The service uses Python/FastAPI and Redis. The hash-locked requirement files are
important: installing different dependency versions in two environments can
change behavior even if your application source is unchanged.

The Dockerfile connects its test stage to the final build, so the normal image
build executes the tests. You do not need to install FastAPI into Debian's system
Python simply to deploy the image.

### 4.4 Orders repository

~~~text
boutique-orders/
  pom.xml                Maven dependencies and build
  src/main/java/dev/boutique/orders/
    Application.java     Spring Boot entry point
    OrdersController.java
  src/main/resources/
    application.properties
    db/migration/V1__orders.sql
  src/test/              Java validation tests
  certs/                 Public AWS RDS CA bundle and checksum
  scripts/fetch-rds-ca.sh
  docs/security-exceptions.md
  Dockerfile             Maven verification and Java 21 runtime
  Jenkinsfile
  helm/
~~~

Flyway applies versioned database migrations. The first migration creates the
order schema. Schema changes and image changes must be coordinated: rolling back
an image does not automatically reverse a database migration.

The CA bundle is public trust material, not an AWS credential. It lets the cloud
orders client verify its RDS server. Lab database TLS uses the separately
generated lab CA.

The security exception document describes a scoped, expiring image-scan
exception. An exception is an item to review; it is not a reason to ignore all
scanner findings.

### 4.5 CI repository

~~~text
boutique-ci/
  vars/
    servicePipeline.groovy    Shared app/incident-adapter build pipeline
    releaseArtifact.groovy    Retrieve and verify a trusted release
    gitopsPullRequest.groovy  Protection checks, PR and merge orchestration
  pipelines/
    bootstrap.Jenkinsfile    First complete four-service installation
    promote.Jenkinsfile      Normal environment promotion
    verify.Jenkinsfile       Read-only runtime/HTTP verification
    rollback.Jenkinsfile     Restore a previously verified release
    gitops-check.Jenkinsfile  Fixed trusted candidate-policy check
  jenkins/
    compose.yaml             Separate validation/release controllers
    casc/jenkins.yaml         Jenkins Configuration as Code
    jobs/                    Job DSL seed definitions
    controller/              Controller image and plugin locks
    agents/                  Common agent image and connection guide
    scripts/                 Init, signing keys, tools and runtime checks
~~~

An application Jenkinsfile is small because it calls the common shared library.
The shared library is selected using a reviewed full CI commit, with version
overrides disabled. That keeps pipeline logic consistent across services.

The delivery job definitions are loaded from protected CI configuration.
The GitOps policy job reads candidate PR files as data; it must not execute a
candidate's replacement policy script.

There is currently no Jenkinsfile in the GitOps repository itself. The
validation seed also declares a GitOps multibranch item, but that item does not
provide the working policy gate. Use the separately seeded
**boutique-gitops-check** job from this CI repository.

### 4.6 Infrastructure repository

~~~text
boutique-infrastructure/
  bootstrap/                Protected AWS Terraform state storage
  environments/
    nonprod/                Nonprod VPC/EKS; dev and staging data
    production/             Separate production VPC/EKS/data
    audit/                  Once-per-account CloudTrail/security logging
  modules/platform/
    main.tf                 Shared AZ selection and tags
    networking.tf           VPC, subnet/NAT settings and data access rules
    eks.tf                  Private cluster, nodes, access and core addons
    iam.tf                  Cluster/node/OIDC/External Secrets identities
    encryption.tf           Platform KMS key
    databases.tf            RDS and Redis
    secrets.tf              Application credential creation/delivery
    budgets.tf              Monthly cost notification
    monitoring.tf           Dedicated queue DB and integration identities
    observability.tf        CloudWatch logs, alarms and optional telemetry
    operator.tf             Private SSM-only administrative host
    variables.tf            Input contract
    outputs.tf              Output contract
    versions.tf             Terraform/provider requirements
  scripts/                  Preflight, database setup, sparse plan summary
  Jenkinsfile               Trusted Terraform plan/approval/apply job
~~~

Every .tf file in modules/platform belongs to the same module. Separate files
improve navigation. Separate environment roots and state keys provide the
nonprod/production state boundaries.

You do not apply this repository to deploy on kind. Kind provides local
Kubernetes nodes using Docker, not AWS VPCs or EKS.

### 4.7 GitOps repository

~~~text
boutique-gitops/
  environments/dev/
    Chart.yaml              Umbrella chart and exact app chart versions
    charts/*.tgz            Verified, committed service chart packages
    values.yaml             Environment configuration
    releases.yaml           Selected image identities
    templates/              Namespace, quotas and network policy
  environments/staging/     Same structure with staging settings
  environments/production/  Same structure with production settings
  homelab/<env>/values.yaml  Local-image, introductory kind profile
  lab-profiles/<env>/        TLS/local-data production-learning additions
  applications/             Cloud/default Argo Application examples
  monitoring/               Shared monitoring Helm chart and profiles
  platform/                 Ingress, issuers and AWS secret integration
  dependencies/homelab/      Optional separate local-data chart
  promotionrecords/         Created by actual signed delivery changes
  schemas/                  Release, chart and evidence data contracts
  scripts/                  Render, validate, promote and recovery tools
~~~

Some directories, such as promotionrecords, appear when real delivery records
are created. Do not conclude that a release happened because a schema or example
file exists.

This repository answers “which image and which chart should dev run?” It does
not contain the app's normal business logic. A catalogue source change belongs
in the catalogue repository; a change to the production replica count belongs
in GitOps configuration.

### 4.8 Platform repository

~~~text
boutique-platform/
  local/compose.yaml        Fast six-component application runtime
  local/kind.yaml           Small introductory cluster configuration
  local/production-lab/
    kind-nonprod.yaml       Three-node nonprod cluster
    kind-production.yaml    Three-node production cluster
    versions.lock.json     Verified CLI/controllers/node-image pins
    .state/                Generated private state; ignored
    .cache/                Verified downloaded artifacts; ignored
  scripts/
    init-local.sh          Preserve/generate local app credentials
    local-up.sh            Build/start Compose and run smoke checks
    homelab-up.sh          Older fixed-name single-kind convenience helper
    k8s-secrets.py         Generate/preserve introductory Kubernetes Secrets
    production-lab.py     Full lab foundation, secrets, delivery and drills
    wait-for-deployment.py Trusted verification helper
    backup-local.sh       Local PostgreSQL backup
    restore-drill.sh      Restore into a disposable database
  tests/smoke/             Real HTTP application checks
  tests/config/            Delivery/rendering/policy tests
  monitoring/              Compose monitoring, rules, dashboard, adapter
  docs/                    Architecture, operations and recovery guides
  workspace/               Eight-repository inventory and editor template
  Jenkinsfile              Builds the incident adapter as a deployable service
~~~

The incident adapter is the fifth custom deployable workload. Redis,
PostgreSQL, Grafana and Argo are additional software components, but they are not
custom business services with their own application repositories.

The old homelab-up.sh assumes a cluster named boutique and changes the active
kubectl context. This guide uses explicit cluster selection and an isolated
operator kubeconfig for the introductory path instead.

## 5. Understand the recurring file types

| File/type | What to understand | Typical edit |
| --- | --- | --- |
| Dockerfile | Build stages, tests, final runtime, user and entry point | Update an app runtime/dependency through review |
| .dockerignore | What is excluded from Docker build context | Prevent secrets/Git/cache files entering the build |
| Jenkinsfile | Which job/library runs for this repository | Keep service entrypoints thin |
| helm/Chart.yaml | Chart name and version metadata | Versioned service chart packaging |
| helm/templates/ | Kubernetes object definitions | Change a service's runtime resources |
| values.yaml | Inputs to templates | Set environment behavior and resources |
| values.schema.json | Allowed value shapes/types | Reject invalid configuration early |
| releases.yaml | Selected release images | Delivery jobs update immutable digests |
| charts/*.tgz | Packaged chart templates and defaults | Verified release packages committed by delivery |
| .terraform.lock.hcl | Provider selections/checksums | Reviewed dependency upgrade |
| CODEOWNERS | Which paths require owner review | Protect policy/pipeline/production changes |
| .gitignore | Generated/private/cache exclusions | Keep local state out of commits |
| README/runbook | Intent, setup and response procedure | Record how operators actually use the system |

Generated files are important but are not all source code. For example, deleting
an ignored session-key file can break session continuity even though Git reports
a clean working tree. An ignored Terraform state can contain sensitive values.
Treat Git status as a source-control check, not a full backup inventory.

## 6. Prepare your Debian laptop

### 6.1 Confirm the host

Use a normal Debian host or supported Linux VM. The pinned CLI installers are
for Linux amd64. Check:

~~~bash
cat /etc/os-release
uname -m
free -h
df -h
~~~

The expected architecture is x86_64. An ARM laptop requires separately reviewed
tool/image compatibility; the production lab rejects unsupported CLI
architecture rather than downloading an arbitrary binary.

Do not run the two-cluster lab inside an ordinary unprivileged application
container. Kind nodes need the host's container/kernel/cgroup capabilities.

### 6.2 Install basic tools

~~~bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates curl gnupg git openssl unzip jq make \
  python3 python3-venv python3-yaml python3-jsonschema
~~~

Debian supplies Python/YAML tools for the platform scripts. The app's Node,
Go, Python and Java runtime dependencies come from its Docker builds.
Avoid using sudo pip to modify Debian's system Python.

### 6.3 Install Docker Engine and Compose

If Docker and the Compose plugin already work, keep that installation and skip
the installation block. Check:

~~~bash
docker version
docker compose version
docker info
~~~

For a fresh Debian installation, use Docker's official Debian repository.
The commands below configure Docker's signed apt source:

~~~bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

(
  . /etc/os-release
  printf 'Types: deb\nURIs: https://download.docker.com/linux/debian\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' \
    "$VERSION_CODENAME" "$(dpkg --print-architecture)"
) | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null

sudo apt-get update
sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
~~~

Check Docker's [current Debian installation instructions](https://docs.docker.com/engine/install/debian/)
if your distribution codename is unsupported or conflicting older Docker
packages are installed. Do not purge your existing installation/data to make
these examples run.

If your normal operator account needs access to the laptop Docker daemon:

~~~bash
sudo usermod -aG docker "$USER"
~~~

Log out and log back in before continuing. Docker-group membership grants
powerful control over this host. It is suitable for your trusted local operator,
but it does not isolate an untrusted PR build. Build-agent isolation comes later.

~~~bash
docker run --rm hello-world
docker info --format '{{.Driver}}'
docker compose version
~~~

The hello-world container only checks Docker. It does not verify the app or
Kubernetes. The production-lab doctor performs additional capacity checks.

### 6.4 Install the project CLIs

Do this after cloning the workspace in section 7:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
./scripts/install-tools.sh "$PWD/.tools"
export PATH="$BOUTIQUE_ROOT/boutique-platform/.tools:$PATH"
kubectl version --client=true
kind version
helm version --short
terraform version
kubeconform -v
~~~

The installer verifies published/reviewed checksums. It installs kubectl 1.34.0,
Helm 3.22.0, Terraform 1.11.4, kubeconform 0.6.7 and kind 0.30.0.
The full lab separately downloads its locked kind 0.33.0 binary. Its helper
prefers that cached binary; seeing kind 0.30.0 on your shell PATH does not mean
the full lab uses it.

These are project pins, not a promise that every pin is the newest or remains
secure indefinitely. Update versions as a reviewed dependency change.

### Checkpoint A

You can run Docker as the intended operator, Compose is available, the host
architecture is supported, and Python can import its manifest dependencies:

~~~bash
python3 -c 'import yaml, jsonschema; print("Python prerequisites ready")'
~~~

## 7. Clone the workspace

Choose one parent directory. The Compose file and scripts expect sibling
repositories at these exact directory names:

~~~text
$HOME/devops-boutique/
  boutique-frontend/
  boutique-catalogue/
  boutique-cart/
  boutique-orders/
  boutique-ci/
  boutique-infrastructure/
  boutique-gitops/
  boutique-platform/
~~~

Run:

~~~bash
export BOUTIQUE_ROOT="$HOME/devops-boutique"
mkdir -p "$BOUTIQUE_ROOT"
cd "$BOUTIQUE_ROOT"

for repo in frontend catalogue cart orders ci infrastructure gitops platform; do
  if [ -e "boutique-$repo" ]; then
    printf 'Preserving existing directory: boutique-%s\n' "$repo"
  else
    git clone "https://github.com/subhankar12-spec/boutique-$repo.git"
  fi
done
~~~

If an existing directory is not the intended checkout, inspect it rather than
overwriting it. Verify all eight:

~~~bash
for repo in frontend catalogue cart orders ci infrastructure gitops platform; do
  git -C "$BOUTIQUE_ROOT/boutique-$repo" status --short
  git -C "$BOUTIQUE_ROOT/boutique-$repo" remote get-url origin
done
~~~

A new terminal will not remember your exported variables automatically.
Re-enter BOUTIQUE_ROOT and PATH when opening another terminal for this guide.
Keep credentials out of shell startup files.

You can open workspace/boutique.code-workspace from the platform repository in
VS Code after verifying its relative folders resolve in your chosen layout.

Do not run init-repositories.sh or publish-repositories.py just to clone the
published project. Those scripts initialize/publish repositories; Git clone is
the normal consumer workflow.

### Checkpoint B

All eight checkouts exist beside one another. You understand that changing the
frontend and GitOps creates changes in two separate Git repositories.

## 8. Run the application with Docker Compose

### 8.1 Start it

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
./scripts/local-up.sh
~~~

The script:

1. Preserves existing local/.env credentials or generates missing values.
2. Builds the four application images.
3. Starts six components from local/compose.yaml.
4. Runs the real HTTP smoke suite.

Docker pulls dependencies/runtime images and builds images. The first Java and
Python builds can take time. Follow the build output; do not assume a long
dependency download means the system is broken.

### 8.2 Open and inspect

Open **http://localhost:8080** in your laptop browser.

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
docker compose --env-file local/.env -f local/compose.yaml ps
docker compose --env-file local/.env -f local/compose.yaml logs --tail=100 frontend
docker compose --env-file local/.env -f local/compose.yaml logs --tail=100 orders
curl -fsS http://localhost:8080/health/ready
curl -fsS http://localhost:8080/api/products | python3 -m json.tool
~~~

Only the frontend is bound to a laptop application port. Internal names such as
catalogue and postgres are Docker network DNS names.

The Compose project is named boutique. Its generated app images are
boutique-frontend:latest, boutique-catalogue:latest, boutique-cart:latest and
boutique-orders:latest. These local names are not the registry release identities
used by the full delivery track.

### 8.3 Understand the smoke test

~~~bash
python3 tests/smoke/smoke.py \
  --environment dev \
  --report /tmp/boutique-compose-smoke.json
~~~

The suite checks browsing, cart behavior, invalid input, Origin enforcement,
session isolation, server pricing, checkout, repeat/concurrent idempotency,
order ownership, empty checkout and item deletion.

This is stronger than “the container started.” It exercises HTTP behavior
across the application and databases. It also creates synthetic orders, so run
it against this project's learning data rather than unrelated customer data.

### 8.4 Understand persistence and credentials

Redis and PostgreSQL use named Docker volumes. Restarting their containers does
not erase those volumes. local/.env contains the matching generated credentials.

Do not delete local/.env while retaining initialized database volumes. A new
password in an environment file does not update a database's existing password.
Changing credentials is a coordinated rotation operation.

### Checkpoint C

You can use the storefront, the smoke report succeeds, and you can explain which
service talks to which database. Continue to kind only after this works.

## 9. Deploy the application in your kind cluster

This is the beginner exercise. It deliberately uses locally built images and
directly applied Helm-rendered manifests. It does not create signed production
release evidence, Argo Applications, TLS ingress or the two-cluster boundary.

### 9.1 Select an existing cluster or create a dedicated one

List existing clusters:

~~~bash
kind get clusters
kubectl config get-contexts
~~~

If you already have a suitable kind cluster, set its actual kind name:

~~~bash
export BOUTIQUE_KIND_CLUSTER="YOUR_EXISTING_KIND_NAME"
export BOUTIQUE_KIND_CONTEXT="kind-$BOUTIQUE_KIND_CLUSTER"
~~~

Replace YOUR_EXISTING_KIND_NAME; do not copy it literally. Verify the intended
cluster has enough capacity and a working dynamic StorageClass:

~~~bash
kubectl --context "$BOUTIQUE_KIND_CONTEXT" get nodes -o wide
kubectl --context "$BOUTIQUE_KIND_CONTEXT" get storageclass
~~~

The manifests and kubectl pin target Kubernetes 1.34. Check version compatibility
before using an older/newer cluster. An existing namespace called boutique-dev
must belong to this exercise; do not overwrite someone else's workload.

If you want a fresh dedicated introductory cluster instead:

~~~bash
export BOUTIQUE_KIND_CLUSTER="boutique-learning"
export BOUTIQUE_KIND_CONTEXT="kind-$BOUTIQUE_KIND_CLUSTER"
kind create cluster \
  --name "$BOUTIQUE_KIND_CLUSTER" \
  --config "$BOUTIQUE_ROOT/boutique-platform/local/kind.yaml" \
  --image kindest/node:v1.34.0
~~~

Run the create command only when that cluster name does not exist. This small
configuration has one control plane and one worker. The stricter two-cluster
lab later uses a reviewed node-image digest and different controller networking.

### 9.2 Isolate the operator kubeconfig

The introductory secret helper invokes kubectl without a context flag. Give this
terminal an operator kubeconfig that contains only your chosen kind cluster:

~~~bash
export BOUTIQUE_OPERATOR_DIR="$HOME/.local/share/boutique-learning"
install -d -m 0700 "$BOUTIQUE_OPERATOR_DIR"
umask 077
kind get kubeconfig --name "$BOUTIQUE_KIND_CLUSTER" \
  > "$BOUTIQUE_OPERATOR_DIR/kind-operator.yaml"
chmod 0600 "$BOUTIQUE_OPERATOR_DIR/kind-operator.yaml"
export KUBECONFIG="$BOUTIQUE_OPERATOR_DIR/kind-operator.yaml"
kubectl config current-context
kubectl get nodes
~~~

Confirm the printed context is the cluster you selected. This file grants
operator access and stays outside Git. It is not a Jenkins verifier credential.

### 9.3 Build and load the images

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
./scripts/init-local.sh
docker compose --env-file local/.env -f local/compose.yaml build

for service in frontend catalogue cart orders; do
  docker tag "boutique-$service:latest" "boutique-$service:local"
  kind load docker-image "boutique-$service:local" \
    --name "$BOUTIQUE_KIND_CLUSTER"
done
~~~

Loading images copies them into the kind nodes' container runtime. An image
existing in the laptop Docker daemon is not automatically available to
Kubernetes nodes.

### 9.4 Create the local Kubernetes credentials

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/k8s-secrets.py dev
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get secrets
~~~

The helper creates/preserves redis-auth, cart-redis, frontend-session and
orders-database. It refuses a partial Redis credential pair. This introductory
profile uses local data services without the full lab's database TLS.

Listing Secret names is useful. Dumping their values into a screenshot, commit
or chat is not needed to verify creation.

### 9.5 Render, inspect, then apply

~~~bash
python3 "$BOUTIQUE_ROOT/boutique-gitops/scripts/render.py" dev \
  --profile local > /tmp/boutique-dev-local.yaml

kubeconform -strict -summary \
  -kubernetes-version 1.34.0 /tmp/boutique-dev-local.yaml

kubectl --context "$BOUTIQUE_KIND_CONTEXT" \
  apply -f /tmp/boutique-dev-local.yaml
~~~

The render command combines the environment umbrella chart and its committed
service packages with the local values profile. It includes the local databases.
Do not also install dependencies/homelab into this namespace: that optional
chart can duplicate the data resources.

The temporary YAML contains references to Kubernetes Secrets; it does not need
their generated values. You can inspect its Deployments, Services, StatefulSets,
quota and NetworkPolicy objects before applying it.

### 9.6 Wait for the app

~~~bash
for service in frontend catalogue cart orders; do
  kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev \
    rollout status "deployment/$service" --timeout=300s
done

kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get pods -o wide
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get services
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get pvc
~~~

PostgreSQL/Redis must start and bind their storage before dependent applications
become ready. A rollout timeout means inspect the failing Pod/events rather than
repeatedly applying the same file.

### 9.7 Open the app through port-forward

The local profile expects the browser Origin **http://localhost:8080**.
If the Compose app is still using port 8080, stop that app stack first:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
docker compose --env-file local/.env -f local/compose.yaml down
~~~

This preserves volumes. If you started the combined Compose monitoring stack,
use its combined-file stop command in section 22 instead.

In terminal A:

~~~bash
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev \
  port-forward --address 127.0.0.1 service/frontend 8080:8080
~~~

Keep that terminal open. Open **http://localhost:8080** in your browser.
In terminal B, restore BOUTIQUE_ROOT and run:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
BASE_URL=http://localhost:8080 python3 tests/smoke/smoke.py \
  --environment dev --report /tmp/boutique-kind-smoke.json
~~~

Do not change the exposed port/origin independently of PUBLIC_ORIGIN. For
example, a different browser port can make mutations fail their Origin check.

### 9.8 Know this exercise's boundaries

The default kind network does not demonstrate the Calico policy enforcement used
in the full lab. Having a NetworkPolicy object is insufficient; your CNI must
implement it. An existing cluster with a policy-capable CNI can enforce policy,
but you still need an executable connectivity test.

Direct kubectl apply is a useful introductory exercise. Once Argo owns the full
lab, use the reviewed GitOps delivery workflow instead.

### Checkpoint D

All four application Deployments are ready, database PVCs are Bound, and the
HTTP smoke suite succeeds through the port-forward. You can locate the rendered
image selection and understand why loading images into kind was necessary.

## 10. Inspect and understand the Kubernetes deployment

### 10.1 Deployment, Pod and container

A Deployment specifies the desired app replicas and Pod template. A ReplicaSet
maintains those replicas. A Pod contains the app container, its environment
configuration and mounts. The container image contains the executable code.

~~~bash
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get deployments
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get replicasets
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get pods
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev \
  describe deployment/frontend
~~~

Read the image, resources, probes and Secret references. These are different
from the application source files that produced the image.

### 10.2 Service and DNS

A Service gives changing Pods a stable name/address. In this namespace, the
frontend can call http://catalogue:8081 even after a catalogue Pod is replaced.
Services select Pods by labels, so a label mismatch can leave a Service with no
ready endpoints.

~~~bash
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get endpointslices
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev describe service/cart
~~~

### 10.3 StatefulSet and PVC

A StatefulSet suits a local data workload that needs stable identity/storage.
A PersistentVolumeClaim requests storage from the cluster's provisioner.
A Bound PVC does not establish that the data has an off-host backup.

~~~bash
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev get statefulsets
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev describe pvc
kubectl --context "$BOUTIQUE_KIND_CONTEXT" get storageclass
~~~

Kind's local storage remains on its Docker-node disks. Deleting the cluster can
lose those disks and the databases. Do not confuse a persistent Pod volume with
surviving laptop/cluster deletion.

### 10.4 Resources and security settings

Requests influence scheduling. Limits constrain resource use. Java's memory
settings and Pod memory limit must agree; an OOMKilled event is a memory problem,
not necessarily an application exception.

Non-root users, dropped capabilities, read-only root filesystems and restricted
Pod settings reduce avoidable runtime privileges. A writable /tmp mount permits
necessary temporary data while retaining the read-only application filesystem.

### 10.5 Events and logs

~~~bash
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev \
  get events --sort-by=.lastTimestamp
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev \
  logs deployment/orders --tail=100
~~~

For a repeatedly crashing Pod, copy its actual name from get pods:

~~~bash
kubectl --context "$BOUTIQUE_KIND_CONTEXT" -n boutique-dev \
  logs YOUR_POD_NAME --previous --tail=100
~~~

The previous flag retrieves the last terminated container's logs when available.
Replace YOUR_POD_NAME; it is not a resource included in the project.

## 11. Understand Helm and the environment profiles

Helm is a template/package tool for Kubernetes configuration. A chart combines
templates, defaults and metadata. Values customize its rendering.

In this project, a service owns its chart in its application repository.
The GitOps environment uses an umbrella chart with four service dependencies.
The service packages are committed under charts/ after verification.

~~~mermaid
flowchart LR
    Source["Service repo: code + helm"] --> Jenkins["Tested release build"]
    Jenkins --> Image["GHCR image digest"]
    Jenkins --> Chart["Signed chart package identity"]
    Chart --> Git["GitOps: charts/*.tgz"]
    Image --> Values["GitOps: releases.yaml"]
    Git --> Render["Helm rendering"]
    Values --> Render
    Config["Environment/profile values"] --> Render
    Render --> Argo["Argo CD reconciliation"]
~~~

### Values merge order

| Profile | Value files added to the environment chart | Intended runtime |
| --- | --- | --- |
| cloud | values.yaml, releases.yaml | Managed cloud services |
| lab | values.yaml, releases.yaml, lab-profiles/<env>/values.yaml | Two-cluster TLS kind lab |
| local | values.yaml, releases.yaml, homelab/<env>/values.yaml | Introductory locally loaded images/data |

Later values override earlier values where Helm's merge rules permit.
Lists can be replaced, so inspect the rendered YAML rather than assuming every
list is appended.

The checked-in baseline charts use **0.1.0-bootstrap** and deliberately unavailable
bootstrap images. The local profile overrides those image names for the beginner
exercise. The full lab refuses bootstrap/local tags; it needs real releases.

Changing service helm/templates changes the next packaged chart release.
Changing a local application checkout does not change a previously vendored
chart package in GitOps. Build/publish/promote the new chart through the pipeline.

Argo uses Helm to render manifests and then manages them itself. You will not
necessarily see these applications as ordinary helm list releases. Use GitOps
history and Argo status for the full delivery track; helm rollback is not this
project's application recovery workflow.

Read [Helm delivery](https://github.com/subhankar12-spec/boutique-gitops/blob/main/docs/helm-delivery.md)
when you are ready to understand chart checksums and promotion records.

## 12. Understand the Jenkins delivery architecture

### 12.1 Why there are two Jenkins controllers

A **controller** is the Jenkins server that stores job configuration, credentials,
build history and the queue. An **agent** is the machine that runs a job's commands.
The controllers have zero executors: they organize work; agents execute it.

There are two separate trust boundaries:

| Controller | Local UI | What it handles | What it must never receive |
| --- | --- | --- | --- |
| Validation | http://127.0.0.1:8090 | Candidate branches and origin PR tests | Release signing keys, package publication, GitOps writes, AWS or cluster access |
| Release | http://127.0.0.1:8091 | Protected main builds and reviewed delivery | Arbitrary unreviewed PR execution |

A PR can change a Jenkinsfile or a test script. Running that script is running
the author's code. A label alone does not stop a malicious Jenkinsfile from
requesting another label or credential. Separate controllers, agents and Docker
daemons make the separation meaningful.

Two controllers are a deliberate security choice in this project, not a claim
that every company uses exactly two. Companies implement the same trust
separation with different products and isolation models.

### 12.2 Follow a release from source to production

~~~mermaid
flowchart TD
  PR[Application pull request] --> V[Validation controller]
  V --> T[Isolated tests, build and scans]
  T --> R[Review and merge protected main]
  R --> B[Release controller: trusted build]
  B --> G[Publish image and Helm chart to GHCR]
  B --> S[Sign release record and archive evidence]
  S --> D[Prepare dev GitOps pull request]
  D --> P[Fixed trusted GitOps policy check]
  P --> M[Merge allowed reviewed change]
  M --> A[Argo CD reconciles desired state]
  A --> E[Read-only rollout and HTTPS verification]
  E --> F[Sign dev verification evidence]
  F --> ST[Promote same image and chart to staging]
  ST --> SE[Verify and sign staging evidence]
  SE --> PA[Production approval and GitHub review]
  PA --> PROD[Promote same image and chart to production]
  PROD --> PE[Verify and sign production evidence]
~~~

**Build once, promote the same artifact** means production does not rebuild the
source using production-specific settings. Dev, staging and production select
the same image digest and chart package; their configuration and credentials
are different.

### 12.3 Exact shared service pipeline stages

The application's small Jenkinsfiles call **vars/servicePipeline.groovy** in
boutique-ci. The shared library is pinned to a reviewed full CI commit.
The platform Jenkinsfile uses the same pipeline for the incident bridge.

The outer stage is **Validate, build and publish**. Its nested stages are:

| Stage | What happens | When |
| --- | --- | --- |
| Checkout | Clean agent workspace, checkout source, record full commit | Validation and release |
| Validate protected source | Confirm source belongs to protected origin main | Release |
| Source secret scan | Trivy filesystem scan, failing on configured high/critical findings | Both |
| Monitoring configuration | Validate alert/routing/dashboard configuration | Incident bridge only |
| AWS trust bundle | Verify the reviewed public RDS CA bundle | Orders release |
| Helm validation and packaging | Lint service chart, render Kubernetes resources, schema-check, package chart | Four application services |
| Test and build | Build image through Dockerfile test/build stages | Both |
| Durable queue integration | Run the incident adapter's real PostgreSQL queue tests | Incident bridge only |
| Security and SBOM | Scan image with Trivy and generate CycloneDX inventory with Syft | Both |
| Publish tested artifact | Publish immutable image/chart, produce signed release record and archive evidence | Release only |

After that outer stage releases its build executor, **Deliver to dev** can run
for application releases. It is conditional: the controller must be the release
controller, the source must be main, DELIVER_TO_DEV must be enabled, and dev must
already have a complete baseline. Incident bridge publication does not
automatically promote the four-service application.

The Dockerfiles run meaningful language-specific tests: frontend Node tests,
catalogue Go tests, cart Python tests and orders Maven verification. The final
cart build depends on the test stage, so tests are part of producing its image.

The image scan uses **--ignore-unfixed**. That means high/critical findings with
available fixes are gated according to the scanner configuration; it does not
prove there are zero vulnerabilities. Reviewed exceptions live in .trivyignore.
Inspect scan evidence and expiry/review of exceptions rather than treating a
green pipeline as a security guarantee. The actual configured ignore filename
is .trivyignore.yaml.

### 12.4 Understand the four identifiers you see everywhere

| Identifier | Example shape | Meaning |
| --- | --- | --- |
| Source commit | 40 hexadecimal characters | Exact application source revision |
| Image digest | ghcr.io/owner/boutique-cart@sha256:64-hex-characters | Exact registry content |
| Chart version | 0.1.0 followed by the full source commit as its prerelease suffix | Exact packaged Kubernetes templates |
| GitOps commit | A different 40-character commit | Exact reviewed environment selection/configuration |

The release initially publishes a source-commit tag, but deployment selects a
digest. A tag is a movable label in a registry; a digest identifies content.
Publication refuses to overwrite an existing source tag/chart version.

The version-2 signed release record binds source, image digest, chart version,
chart archive checksum, OCI chart manifest digest and scan/SBOM checksums.
Version-1 records do not satisfy the current policy.

There are **two Ed25519 key pairs**. The artifact key signs what the trusted
build produced. The evidence key signs what the trusted verifier observed.
Keeping these separate prevents a build signature from being mistaken for a
successful deployment.

A successful GitOps merge only says desired state changed. Deployment success
also requires Argo reconciliation, matching running images/chart provenance,
rollout health and a real HTTPS smoke test.

### 12.5 How many pipelines are there per service?

Each application service has a repository Jenkinsfile and two job contexts:
validation branches/PRs on the validation controller and protected main on the
release controller. They share implementation rather than duplicating a long
Jenkinsfile in every repository.

Delivery is shared across services:

| Shared job | Job definition in boutique-ci | Purpose |
| --- | --- | --- |
| boutique-bootstrap | pipelines/bootstrap.Jenkinsfile | Select first complete four-service baseline |
| boutique-promote | pipelines/promote.Jenkinsfile | Promote one released service |
| boutique-verify | pipelines/verify.Jenkinsfile | Verify actual target state and sign evidence |
| boutique-rollback | pipelines/rollback.Jenkinsfile | Select a previously verified release |
| boutique-gitops-check | pipelines/gitops-check.Jenkinsfile | Evaluate candidate changes with protected policy |
| boutique-infrastructure | Infrastructure pipeline definition | Optional reviewed AWS plan/apply |

The GitOps repository itself currently has **no Jenkinsfile**. Its validation
seed entry can discover a multibranch item, but that is not a functioning
GitOps pipeline. The supported required policy result comes from
**boutique-gitops-check**, defined in the protected CI repository.

## 13. Configure Jenkins controllers and agents

Do this chapter after the introductory app deployment works. Agents and
credentials are manual setup steps; starting Compose does not provision them.

### 13.1 Start and inspect the controllers

~~~bash
cd "$BOUTIQUE_ROOT/boutique-ci/jenkins"
./scripts/init-local.sh
python3 scripts/init-signing-keys.py
docker compose up -d --build
docker compose ps
python3 scripts/doctor.py
~~~

Open validation at port 8090 and release at 8091. The generated passwords are
in the ignored **boutique-ci/jenkins/.env** file. Open it in a local private
editor to find the admin, release-manager and platform-admin account settings.
Do not paste its contents into an issue, chat or build log.

Keep .env and both controller volumes. Rerunning init preserves existing values.
The initializer sets BOUTIQUE_CI_LIBRARY_REF to the current CI commit only if
the setting is missing. Review that full commit; a later git pull does not
silently approve a shared-library upgrade.

The controller image pins Jenkins and checksum-locked plugins. Its
Configuration as Code file configures the realm, controller role and library.
For shared use, local bootstrap accounts need replacement with organizational
identity, TLS and deliberate access policies.

### 13.2 Allocate agents by role

In **Manage Jenkins → Nodes → New Node**, create permanent inbound nodes,
choose one executor, assign the label below and use the WebSocket launch
instructions displayed by Jenkins.

| Controller | Suggested node name / label | Placement |
| --- | --- | --- |
| Validation | boutique-isolated-builder / isolated-builder | Disposable Debian VM, dedicated rootless Docker |
| Release | boutique-trusted-release / trusted-release | Separate trusted Debian VM, dedicated rootless Docker |
| Release | boutique-trusted-deploy / trusted-deploy | Trusted operator host/container with cluster and app routing |
| Release | boutique-policy-check / policy-check | Separate protected executor, no Docker socket or cluster credential |
| Release | boutique-terraform / terraform-trusted | Optional trusted AWS-connected agent |

Node names are identifiers; **labels** are what the pipelines request.
Do not assign every label to one machine. Do not connect the validation agent
to the release controller.

The fixed policy job needs its own executor because the deploy parent waits
for it while keeping its workspace. With one shared executor, the child can
wait indefinitely for the parent to release the resource it needs.

The environment delivery lock stays held through downstream verification.
The verifier must not reacquire the parent's same lock. The checked-in jobs
already implement this relationship; do not casually add another identical lock.

### 13.3 Prepare a native build agent on a dedicated Debian VM

A native agent is often easier to understand first than an agent container:
the agent process and its rootless Docker daemon see the same filesystem paths.
Use a fresh Debian 13 VM for each build trust boundary. Debian 12 does not
normally provide openjdk-21-jdk from its standard package repositories; use a
reviewed Java 21 distribution there instead of blindly copying that apt line.

On each **agent VM**, install Git, Python/PyYAML, curl, OpenSSL, jq, unzip,
Java 21 and the Docker packages using the official signed Debian Docker
repository procedure from chapter 6.

~~~bash
sudo apt-get update
sudo apt-get install -y \
  git python3 python3-yaml curl ca-certificates openssl jq unzip \
  openjdk-21-jdk uidmap dbus-user-session slirp4netns \
  docker-ce-rootless-extras
java -version
~~~

Use a dedicated, non-root agent user with a real login session. On a fresh
agent VM where you have chosen rootless Docker, stop the rootful daemon:

~~~bash
# Agent VM only. Do not run this on the laptop hosting your kind clusters.
sudo systemctl disable --now docker.service docker.socket
~~~

Log in as the agent user over SSH. As that user:

~~~bash
dockerd-rootless-setuptool.sh install
systemctl --user enable --now docker
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
docker info
~~~

An administrator can enable user lingering so the user's daemon survives
logout, substituting the actual agent account:

~~~bash
sudo loginctl enable-linger ciagent
~~~

Rootless setup requires working user namespaces and subordinate UID/GID ranges.
Use the official rootless troubleshooting guide if setup fails; do not solve
it by attaching an untrusted agent to the laptop's rootful socket.

Clone the reviewed CI repository on this VM and install its verified tools:

~~~bash
git clone https://github.com/subhankar12-spec/boutique-ci.git "$HOME/boutique-ci"
python3 "$HOME/boutique-ci/jenkins/scripts/install-agent-tools.py" \
  --destination "$HOME/boutique-agent-tools"
export PATH="$HOME/boutique-agent-tools/bin:$PATH"
python3 "$HOME/boutique-ci/jenkins/scripts/install-agent-tools.py" \
  --destination "$HOME/boutique-agent-tools" --verify-only
~~~

Review the checked-out CI commit before using its installer. Set PATH and
DOCKER_HOST in the agent's service/session environment as well; exporting them
in an unrelated terminal does not change a running Java process.

### 13.4 Make the controller reachable without exposing it publicly

The Compose controller ports bind to the laptop's loopback interface.
An agent VM cannot connect to LAPTOP_IP:8090 merely because it can ping the
laptop. The listener is not bound to that network interface.

For an initial private lab, open an SSH tunnel **from the validation VM**
to your laptop, using your real SSH user and address:

~~~bash
ssh -N \
  -L 127.0.0.1:18090:127.0.0.1:8090 \
  operator@LAPTOP_IP
~~~

On the trusted release VM, use a different tunnel:

~~~bash
ssh -N \
  -L 127.0.0.1:18091:127.0.0.1:8091 \
  operator@LAPTOP_IP
~~~

Keep each tunnel terminal open. Validation's VM-local controller URL is
http://127.0.0.1:18090/; release's is http://127.0.0.1:18091/.
These local HTTP connections travel inside the authenticated SSH tunnel.
For continuous operation, provision managed tunnels or reviewed HTTPS
controller endpoints with proper CA trust.

Save the node's Jenkins-generated agent secret in a private mode-0600 file.
It is a Jenkins remoting secret, not a GitHub token.
Download agent.jar from the appropriate reachable controller.

Example on the trusted VM after exporting the private secret-file path:

~~~bash
umask 077
mkdir -p "$HOME/.local/share/boutique-agent"
curl -fsS http://127.0.0.1:18091/jnlpJars/agent.jar \
  -o "$HOME/.local/share/boutique-agent/agent.jar"

# BOUTIQUE_AGENT_SECRET_FILE must name your private node-secret file.
test -f "$BOUTIQUE_AGENT_SECRET_FILE"
java -jar "$HOME/.local/share/boutique-agent/agent.jar" \
  -url http://127.0.0.1:18091/ \
  -name boutique-trusted-release \
  -secret "@$BOUTIQUE_AGENT_SECRET_FILE" \
  -webSocket \
  -workDir "$HOME/.local/share/boutique-agent/work"
~~~

The secret-file syntax keeps the value out of command-line arguments.
For validation, change URL and node name to its own registered node.
Confirm the node appears online before trying a build.

### 13.5 Container agents for trusted deploy and policy work

From the CI repository root:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-ci"
docker build --pull --platform linux/amd64 \
  -f jenkins/agents/Dockerfile -t boutique-agent:local .
~~~

The common image uses a fixed signed Debian snapshot and verified upstream
tools. Its complete image build/scan has not been validated in this cloud
runner: snapshot access returned HTTP 403 and Docker capacity was limited.
Build and scan it on your supported host. A failure is a real prerequisite
to resolve; do not turn off repository signatures/checksums.

Create a private secret file and a writable private workspace for the deploy
node outside the source repositories. Export their paths as
BOUTIQUE_AGENT_SECRET_FILE and BOUTIQUE_AGENT_WORKSPACE.

~~~bash
test -f "$BOUTIQUE_AGENT_SECRET_FILE"
test -d "$BOUTIQUE_AGENT_WORKSPACE"
docker run --rm --name boutique-trusted-deploy --network host \
  --user "$(id -u):$(id -g)" \
  --add-host dev.boutique.test:127.0.0.1 \
  --add-host staging.boutique.test:127.0.0.1 \
  --add-host production.boutique.test:127.0.0.1 \
  -e JENKINS_URL=http://127.0.0.1:8091/ \
  -e JENKINS_AGENT_NAME=boutique-trusted-deploy \
  -e JENKINS_WEB_SOCKET=true \
  -e JENKINS_SECRET_FILE=/run/secrets/agent-secret \
  -e JENKINS_AGENT_WORKDIR=/workspace \
  -v "$BOUTIQUE_AGENT_SECRET_FILE:/run/secrets/agent-secret:ro" \
  -v "$BOUTIQUE_AGENT_WORKSPACE:/workspace" \
  boutique-agent:local
~~~

Linux host networking lets this trusted container reach loopback controller,
kind API and ingress ports. It does not inherit the host's /etc/hosts;
the three --add-host entries supply the application names.
There is deliberately no Docker socket mount.

For policy-check, register a separate node, use a different private secret and
workspace, and change the container/node name. It needs the release controller,
protected tools and its narrow GitHub checks credential. It needs neither a
Docker socket nor cluster/signing credentials.

For Docker-using container build agents, a workspace must appear at the same
absolute path in the agent and daemon host because tests bind-mount fixtures.
Follow the [agent guide](https://github.com/subhankar12-spec/boutique-ci/blob/main/jenkins/agents/README.md)
for that optional layout. Native agents on dedicated VMs avoid this mismatch.

### 13.6 Create the seed jobs

The seed is a job that creates the other Jenkins jobs from reviewed Groovy DSL.

For each controller:

1. Add its read-only github-read credential, described in chapter 14.
2. Create a seed Freestyle job through the Jenkins UI.
3. Restrict it to an appropriate trusted node. The validation seed definition
   must also be operator-reviewed; arbitrary PRs must not rewrite the seed.
4. Configure Git SCM to boutique-ci, branch main, using github-read.
5. Add **Process Job DSLs**, loading jenkins/jobs/validation.groovy on validation
   or jenkins/jobs/release.groovy on release.
6. Review the definition and any necessary script approvals before running it.
   Do not approve arbitrary signatures from an untrusted job.
7. Run the seed, inspect created jobs and manually scan the multibranch projects.

For a localhost-only lab, GitHub cannot reach your controller webhook.
Start with **Scan Multibranch Pipeline Now** and explicit job runs.
The jobs also configure periodic discovery. Later use an authenticated
HTTPS webhook/dispatcher with signature validation rather than exposing the
bootstrap HTTP controller to the internet.

Read [Jenkins setup](jenkins-setup.md) for the narrower operator reference.

## 14. Configure delivery credentials and GitHub protection

### 14.1 Different credentials solve different problems

These credentials do not already exist merely because repositories are public:

| Jenkins credential ID | Type | Consumer and permission |
| --- | --- | --- |
| github-read | Username/password | SCM reads; independently scoped on each controller |
| ghcr-publish | Username/password | Release controller package publication |
| gitops-pr | Username/password | Trusted delivery bot: GitOps contents/PR writes and branch-protection metadata read |
| gitops-checks | Secret text | Fixed policy job: repository reads and commit-status writes |
| release-artifact-signing-key | Secret file | Artifact private Ed25519 key |
| release-artifact-public-key | Secret file | Independently trusted artifact public key |
| release-evidence-signing-key | Secret file | Deployment-evidence private Ed25519 key |
| release-evidence-public-key | Secret file | Independently trusted evidence public key |
| kubeconfig-dev | Secret file | Expiring dev rollout reads and Argo Application reads |
| kubeconfig-staging | Secret file | Equivalent staging reads |
| kubeconfig-production | Secret file | Equivalent production reads |
| boutique-ca-dev | Secret file | Nonprod public TLS root certificate |
| boutique-ca-staging | Secret file | Same nonprod public TLS root certificate |
| boutique-ca-production | Secret file | Production public TLS root certificate |

Use Jenkins credential settings, with the exact IDs expected by the code.
Grant the smallest practical scope and restrict trusted credential use to
trusted jobs. A masked log is not a permission boundary.

GitHub Apps are preferable for supported short-lived SCM/API access, but an
installation ID is not a usable credential. Select an authentication method
compatible with the job's bindings. GHCR package publication/pulls may require
a supported classic token with the appropriate package scopes; do not assume
an SCM GitHub App token automatically supports every registry operation.

The gitops-pr identity must be able to inspect branch protection as well as
write a PR. GitHub App permission models include administration read for that
metadata. Test the actual scoped identity without granting unnecessary
administration write or protection-bypass privileges.

### 14.2 Upload signing keys without committing them

After init-signing-keys.py, the private directory is:

~~~text
boutique-ci/jenkins/.delivery-secrets/
  release-artifact-signing-key.pem
  release-artifact-public-key.pem
  release-evidence-signing-key.pem
  release-evidence-public-key.pem
~~~

Upload each file to the matching Jenkins file credential.
Directory mode is 0700 and files are 0600. Keep an encrypted independent backup.
Losing keys is different from losing source code.

A public key is not secret, but its **integrity** matters: replacing it with
an attacker's key changes what signatures the system trusts.
Never trust a key supplied inside the release record it is meant to verify.
Key rotation must account for retained release/evidence signatures.

### 14.3 Configure the GitOps main branch

In boutique-gitops on GitHub, configure protection for main:

| Required setting | Why |
| --- | --- |
| Required status boutique/gitops-policy | Fixed trusted job checks the actual candidate |
| Require branch up to date / strict status checks | Policy must evaluate against current base |
| Include/enforce protection for administrators | Delivery identities must not bypass review |
| Require CODEOWNER approval | Owned policy and staging/production paths require review |
| Dismiss stale approvals after new commits | Approval of old content cannot authorize new content |
| Enable repository auto-merge | Allows guarded dev automation |
| Restrict force pushes/deletion and trusted-definition writes | Protects the source of delivery authority |

The implementation checks these requirements, including administrator
enforcement; it will reject missing protection rather than quietly deliver.
GitHub's UI/plan features can differ, so verify the effective protection
returned for main.

For automated dev delivery, set the general required review count to **zero**
while keeping CODEOWNER review required. Dev release selections/packages/records
are intentionally unowned; owned paths still require their CODEOWNER.
If you prefer a review for every dev change, require it and disable dev
auto-merge. The bot must still wait for the policy check.

Use a separate bot/App identity to create delivery PRs and your human identity
to approve owned paths. GitHub does not allow an author to approve their own PR.
Using only your own token for both creates a practical production/staging
review dead end.

Protect main in application, CI, infrastructure and platform repositories too.
The precise application test status names come from your actual Jenkins/GitHub
integration; observe a real validation run before making a nonexistent context
mandatory. Protect changes to shared-library/policy code especially carefully.

### 14.4 Configure origins and verify the checklist

The release controller's configured lab origins are:

~~~text
BOUTIQUE_DEV_ORIGIN=https://dev.boutique.test:8443
BOUTIQUE_STAGING_ORIGIN=https://staging.boutique.test:8443
BOUTIQUE_PRODUCTION_ORIGIN=https://production.boutique.test:9443
~~~

They must match frontend PUBLIC_ORIGIN, DNS/hosts entries and actual certificates.
The verifier's CA files must trust the correct cluster's root.

Before your first release, confirm:

- Both controllers are reachable and have zero executors.
- Validation can execute tests but has no publication/delivery credentials.
- Trusted release, deploy and policy nodes are online with different workspaces.
- Rootless Docker works on both isolated build VMs.
- The shared library points at the reviewed CI commit.
- GHCR publication and separate read/pull authentication are configured.
- Artifact and evidence keys exist under the exact credential IDs.
- GitOps protection and the separate reviewer identity are ready.

Cluster verifier credentials are added after the foundation in the next chapter.
AWS backend/tfvars/role credentials are unnecessary for kind.

## 15. Bootstrap the two-cluster production learning lab

This is a separate path from your existing single kind cluster. It creates
**boutique-nonprod** and **boutique-production**, with dedicated local state.
Keep your first learning cluster unless you intentionally decide to remove it.

### 15.1 Understand what bootstrap installs

| Component | Purpose |
| --- | --- |
| kind with pinned Kubernetes node image | Two separate Kubernetes APIs |
| One control-plane plus two workers per cluster | Practice rolling updates and scheduling |
| Calico | Enforce Kubernetes network policies |
| Argo CD | Reconcile reviewed GitOps desired state |
| cert-manager | Issue and renew application/data leaf certificates |
| Traefik | Route HTTPS requests into frontend Services |
| Independent root CA per cluster | Establish private lab TLS trust |

The production-lab versions.lock.json controls kind, node images, controller
manifests and image digests. The full lab uses its own locked kind version,
not simply whichever kind binary you happen to have globally.

Single control planes and local single-replica databases remain availability
limits. Two clusters on one laptop share the laptop's failure domain.

### 15.2 Preflight before creating anything

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
export PATH="$BOUTIQUE_ROOT/boutique-platform/.tools:$PATH"
python3 scripts/production-lab.py fetch-tools
python3 scripts/production-lab.py fetch-manifests
python3 scripts/production-lab.py doctor
~~~

The doctor checks host/platform/tooling/storage prerequisites. The host needs
working privileged containers, writable cgroups and kernel networking support.
The 16 GiB RAM and 30 GiB free Docker disk checks are minimums, not a promise
that both clusters, controllers and build VMs will fit comfortably.
VFS requires much more disk; 60 GiB free is the documented minimum there.

Check your host/VPN routes before bootstrap:

~~~bash
ip route
cat local/production-lab/kind-nonprod.yaml
cat local/production-lab/kind-production.yaml
~~~

The configured pod CIDRs include 192.168.0.0/16 and 172.20.0.0/16.
Home LANs and Docker/VPN networks can overlap these ranges.
If they overlap your environment, review the kind and Calico networking
configuration together before bootstrap; changing only one side is not a
complete network change. Use a suitable isolated VM/network if necessary.

If this preflight fails in a nested cloud runner, use a supported Linux host
instead of disabling safety checks. A writable source checkout is not proof
that nested kubelet/networking will work.

### 15.3 Create the foundations

~~~bash
python3 scripts/production-lab.py bootstrap --cluster nonprod
python3 scripts/production-lab.py bootstrap --cluster production
~~~

Bootstrap is not application deployment. At this stage you should have
clusters/controllers and trust, but no complete signed application baseline.

Private operator state lives here:

~~~text
boutique-platform/local/production-lab/
  .cache/                         # Downloaded verified tools/manifests
  .state/
    nonprod/
      kubeconfig                 # Administrative operator access
      ca/ca.crt                  # Public root certificate
      ca/ca.key                  # Private signing key: protect and back up
    production/
      kubeconfig
      ca/ca.crt
      ca/ca.key
~~~

These directories are ignored by Git. Preserve them on reruns; missing or
inconsistent trust/credential state should be investigated, not overwritten.

The helper uses its own kubeconfig files. Make them available explicitly
in your operator terminal:

~~~bash
export BOUTIQUE_NONPROD_KUBECONFIG="$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/nonprod/kubeconfig"
export BOUTIQUE_PRODUCTION_KUBECONFIG="$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/production/kubeconfig"
export KUBECONFIG="$BOUTIQUE_NONPROD_KUBECONFIG:$BOUTIQUE_PRODUCTION_KUBECONFIG"

kubectl --context kind-boutique-nonprod get nodes
kubectl --context kind-boutique-production get nodes
kubectl --context kind-boutique-nonprod -n argocd get pods
kubectl --context kind-boutique-production -n cert-manager get pods
~~~

Do not expect these contexts to appear in your old single-cluster kubeconfig.
Keep specifying context in every manual Kubernetes command.

### 15.4 Configure hostnames and TLS trust

Open your laptop hosts file:

~~~bash
sudoedit /etc/hosts
~~~

Add this line if it is not already present:

~~~text
127.0.0.1 dev.boutique.test staging.boutique.test production.boutique.test
~~~

Check name resolution:

~~~bash
getent hosts dev.boutique.test
getent hosts staging.boutique.test
getent hosts production.boutique.test
~~~

All three lab names must resolve to loopback on the operator host.
The nonprod cluster exposes HTTPS on 8443; production uses 9443.

The smoke suite uses the explicit matching CA file and verifies the hostname.
For browser access, import the appropriate public ca.crt into the browser's
trusted authorities. Some browsers use a separate trust store.

Optionally, on your own lab laptop, add these reviewed public roots to Debian's
system trust store:

~~~bash
sudo install -m 0644 \
  "$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/nonprod/ca/ca.crt" \
  /usr/local/share/ca-certificates/boutique-nonprod.crt
sudo install -m 0644 \
  "$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/production/ca/ca.crt" \
  /usr/local/share/ca-certificates/boutique-production.crt
sudo update-ca-certificates
~~~

Import **ca.crt**, never ca.key. Trusting a root authorizes certificates it
signs; protect its private key. Leaf renewal is automated by cert-manager, but
the generated one-year local root needs a planned rotation.

### 15.5 Create registry and runtime secrets

The lab secrets command currently requires a registry token file even if
you later make the application packages public.
Use a read-only GHCR pull identity, separate from the publisher.

Create a private directory outside Git and enter the token locally without
putting it in command history:

~~~bash
umask 077
mkdir -p "$HOME/.config/boutique-secrets"
chmod 700 "$HOME/.config/boutique-secrets"
read -r -s -p "GHCR read-packages token: " BOUTIQUE_PULL_TOKEN
printf '\n'
printf '%s' "$BOUTIQUE_PULL_TOKEN" > "$HOME/.config/boutique-secrets/ghcr-read-token"
unset BOUTIQUE_PULL_TOKEN
chmod 600 "$HOME/.config/boutique-secrets/ghcr-read-token"
~~~

Use the username belonging to that token. The following assumes your
subhankar12-spec identity. The GitOps repository is public, so the optional
--repo-token-file is omitted:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py secrets --cluster nonprod \
  --registry-token-file "$HOME/.config/boutique-secrets/ghcr-read-token" \
  --registry-user subhankar12-spec
python3 scripts/production-lab.py secrets --cluster production \
  --registry-token-file "$HOME/.config/boutique-secrets/ghcr-read-token" \
  --registry-user subhankar12-spec
~~~

For a private GitOps repository, also supply a private read-only repo-token
file. The helper configures Argo repository access separately from image pulls.

It generates independent application session, Redis, PostgreSQL, Grafana and
fixture-integration credentials. Production's incident queue has its own
database/user; it does not reuse the orders database.

Existing secrets are preserved. Changing a Kubernetes Secret containing a
database password does not change the password inside an initialized database.
Rotation requires updating the data store and clients consistently.

### 15.6 Export Jenkins's restricted verifier identities

~~~bash
python3 scripts/production-lab.py export-verifier --environment dev --duration 24h
python3 scripts/production-lab.py export-verifier --environment staging --duration 24h
python3 scripts/production-lab.py export-verifier --environment production --duration 24h
~~~

Upload these private files:

| Generated file beneath .state | Jenkins credential |
| --- | --- |
| nonprod/jenkins-verifier-dev.json | kubeconfig-dev |
| nonprod/jenkins-verifier-staging.json | kubeconfig-staging |
| production/jenkins-verifier-production.json | kubeconfig-production |

The JSON files are valid kubeconfig documents despite their filename extension.
These accounts can read their application rollout resources and Argo
Applications. They cannot read Secrets, mutate Deployments or administer
the cluster. Argo Application reads are scoped to the argocd namespace.

Verify the restriction with the dev identity:

~~~bash
export BOUTIQUE_DEV_VERIFIER="$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/nonprod/jenkins-verifier-dev.json"
kubectl --kubeconfig "$BOUTIQUE_DEV_VERIFIER" auth can-i get pods -n boutique-dev
kubectl --kubeconfig "$BOUTIQUE_DEV_VERIFIER" auth can-i get secrets -n boutique-dev
kubectl --kubeconfig "$BOUTIQUE_DEV_VERIFIER" auth can-i update deployments -n boutique-dev
~~~

Expected answers are yes, no, no. A denied auth can-i command may return
nonzero; that is the expected restriction.

Upload nonprod/ca/ca.crt to boutique-ca-dev and boutique-ca-staging, and
production/ca/ca.crt to boutique-ca-production.
Never upload either administrative kubeconfig or a CA private key to these
credentials. Renew and re-upload expiring verifier identities before a build
session; continuous operation needs automated short-lived identity.

## 16. Build releases and install dev, staging and production

### 16.1 Publish the first four releases

On the **release controller**, run:

~~~text
boutique-frontend/main
boutique-catalogue/main
boutique-cart/main
boutique-orders/main
~~~

For each first build, set **DELIVER_TO_DEV=false**.
You are publishing artifacts first, before asking Jenkins to verify a complete
application. If initial discovery already published a successful release,
reuse its build number instead of rebuilding the same immutable source tag.

For each job, record:

| Service | Successful release build number | Image digest | Chart version |
| --- | --- | --- | --- |
| frontend | Fill from Jenkins | Fill from release.json | Fill from release.json |
| catalogue | Fill from Jenkins | Fill from release.json | Fill from release.json |
| cart | Fill from Jenkins | Fill from release.json | Fill from release.json |
| orders | Fill from Jenkins | Fill from release.json | Fill from release.json |

The numbers are per-job Jenkins numbers, not commit hashes.
Inspect the archived release record, signature, chart, SBOM and scan.
Do not invent a digest, edit a signature or use a placeholder chart version.

### 16.2 Bootstrap dev as a complete application

Open **boutique-bootstrap → Build with Parameters**:

~~~text
TARGET=dev
FRONTEND_BUILD=<actual frontend release build number>
CATALOGUE_BUILD=<actual catalogue release build number>
CART_BUILD=<actual cart release build number>
ORDERS_BUILD=<actual orders release build number>
AUTO_MERGE_DEV=true
PAUSE_FOR_INITIAL_SYNC=true
~~~

Leave the four *_EVIDENCE_BUILD fields empty for dev.
Disable AUTO_MERGE_DEV if you chose manual dev review.

The job collects four signed releases, plans one aggregate GitOps change,
validates it with the trusted policy job and waits for its guarded merge.
Inspect the PR's desired images, chart packages and promotion records.

After merge it pauses at **Initialize the first Argo CD synchronization**.
This pause resolves the first-install ordering problem: the initial Application
must not synchronize unusable bootstrap values before valid releases exist.

At that pause, on your operator laptop:

~~~bash
git -C "$BOUTIQUE_ROOT/boutique-gitops" status --short
# Continue only if the checkout is clean; preserve any local edits first.
git -C "$BOUTIQUE_ROOT/boutique-gitops" pull --ff-only origin main
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py deploy --cluster nonprod --environment dev
kubectl --context kind-boutique-nonprod -n argocd get applications
~~~

Argo reads the **published main branch**, not your filesystem.
Wait until boutique-dev is Synced/Healthy. If needed, watch:

~~~bash
kubectl --context kind-boutique-nonprod -n argocd \
  get application boutique-dev --watch
~~~

Use Ctrl-C to stop watching; it does not stop Argo.
Then:

~~~bash
python3 scripts/production-lab.py readiness --cluster nonprod --environment dev
python3 scripts/production-lab.py verify --environment dev
~~~

The readiness helper requires Synced/Healthy when invoked; it can fail if
called while the first synchronization is still running. Inspect status and
rerun after the actual issue or wait is resolved.

Open https://dev.boutique.test:8443 and place a test order.
The automated smoke suite also creates synthetic orders.

Resume the bootstrap input as release-manager.
It runs four boutique-verify jobs, one for each selected service, and archives
four signed dev verification records. Record their separate build numbers.
The operator verify command is useful smoke validation but does not replace
Jenkins's signed verification evidence.

Do not deploy both nonprod environments at once while staging still has
bootstrap values. Use the explicit --environment dev selection.

### 16.3 Bootstrap staging from the same releases

Run boutique-bootstrap again:

~~~text
TARGET=staging
FRONTEND_BUILD=<same original frontend release build>
CATALOGUE_BUILD=<same original catalogue release build>
CART_BUILD=<same original cart release build>
ORDERS_BUILD=<same original orders release build>
FRONTEND_EVIDENCE_BUILD=<frontend dev boutique-verify build>
CATALOGUE_EVIDENCE_BUILD=<catalogue dev boutique-verify build>
CART_EVIDENCE_BUILD=<cart dev boutique-verify build>
ORDERS_EVIDENCE_BUILD=<orders dev boutique-verify build>
AUTO_MERGE_DEV=false
PAUSE_FOR_INITIAL_SYNC=true
~~~

Preceding-environment evidence must identify the same image/chart and be no
older than 24 hours. Reverify if it expires; do not edit timestamps.

Review and merge the staging PR with the separate human CODEOWNER identity.
At the initial-sync pause:

~~~bash
git -C "$BOUTIQUE_ROOT/boutique-gitops" pull --ff-only origin main
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py deploy --cluster nonprod --environment staging
~~~

Wait for boutique-staging to become Synced/Healthy, then:

~~~bash
python3 scripts/production-lab.py readiness --cluster nonprod --environment staging
python3 scripts/production-lab.py verify --environment staging
~~~

Resume Jenkins and retain the four staging verification build numbers.
Visit https://staging.boutique.test:8443.
Dev and staging share the nonprod cluster but have different namespaces,
data, secrets, hostnames and release selections.

### 16.4 Bootstrap production from verified staging

Repeat bootstrap with TARGET=production, the same release build numbers and
the four **staging** evidence build numbers. Keep AUTO_MERGE_DEV=false and
PAUSE_FOR_INITIAL_SYNC=true.

Production requires a release-manager input reviewing the planned change,
evidence and database compatibility, followed by the GitHub CODEOWNER review.
These are two separate controls.

At the initial-sync pause:

~~~bash
git -C "$BOUTIQUE_ROOT/boutique-gitops" pull --ff-only origin main
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py deploy --cluster production --environment production
~~~

Wait for boutique-production to become Synced/Healthy, then:

~~~bash
python3 scripts/production-lab.py readiness --cluster production --environment production
python3 scripts/production-lab.py verify --environment production
~~~

Resume Jenkins and retain the production evidence.
Visit https://production.boutique.test:9443.

You have now exercised three environment selections, two clusters, immutable
releases, reviews, policy checks, reconciliation and functional verification.
You have not demonstrated regional DR, database HA or sustained user load.

### 16.5 Inspect Argo without exposing its administration

Use a loopback port-forward in its own terminal:

~~~bash
kubectl --context kind-boutique-nonprod -n argocd \
  port-forward --address 127.0.0.1 service/argocd-server 18081:443
~~~

Open https://127.0.0.1:18081 for the Argo admin UI. The upstream Argo server
has its own initial certificate; this is separate from the storefront's
lab-issued certificate. Handle its trust deliberately; do not disable TLS
verification in automated release tests.

Retrieve the initial admin credential locally using your operator access and
the argocd-initial-admin-secret, without recording it in build logs.
For shared operation, configure SSO/RBAC and remove reliance on bootstrap admin.

In the UI inspect application source revision, rendered resources, sync status,
health and resource events. The application resource tree is a useful way to
connect Helm templates with the live Deployments, Services and certificates.

## 17. Perform a routine release and rollback

### 17.1 Choose the repository by the change

| Change | Edit here | Delivery consequence |
| --- | --- | --- |
| Cart behavior | boutique-cart application/tests | New cart image and chart release |
| Cart Pod resources/probes | boutique-cart/helm | New cart chart release through service build |
| Staging replica/config selection | boutique-gitops/environments/staging | Reviewed environment change |
| Lab-only PostgreSQL TLS settings | boutique-gitops/lab-profiles | Reviewed lab platform change |
| Common pipeline rule | boutique-ci | Reviewed library/pipeline update and pin upgrade |
| AWS subnet/cluster/database setting | boutique-infrastructure | Reviewed Terraform plan/apply |
| Alert rule/dashboard | Platform source and its GitOps monitoring copy as applicable | Keep rendered runtime configuration consistent |

Do not patch a live Deployment to make a permanent release. Argo's self-heal
can restore Git's desired state. Use the correct source and review workflow.

### 17.2 Example: release a small cart improvement

1. Create an application branch, make the small change and update meaningful
   tests where the behavior requires them.
2. Open a cart PR. Let validation run tests/build/scans on the isolated agent.
3. Review and merge into protected main.
4. Release main runs the trusted pipeline with DELIVER_TO_DEV=true.
5. Inspect the published artifact and dev delivery PR.
6. The fixed policy check passes and eligible dev change auto-merges.
7. Argo rolls out the digest; boutique-verify signs fresh dev evidence.
8. Record the cart release build and dev verification build.

A failed downstream delivery can leave a correctly published release.
Inspect where it failed; do not assume the immutable image should be rebuilt.

### 17.3 Promote the cart release to staging

Run boutique-promote with the actual values from that release:

~~~text
TARGET=staging
SERVICE=cart
IMAGE=ghcr.io/subhankar12-spec/boutique-cart@sha256:<actual digest>
RELEASE_BUILD=<original successful cart main release build>
EVIDENCE_BUILD=<successful dev verification build for this cart release>
AUTO_MERGE_DEV=false
~~~

Review/merge its GitOps PR. The job waits for reconciliation, verifies staging
and produces fresh signed evidence.
For production, repeat with TARGET=production and the **staging** evidence
build, including production approval and CODEOWNER review.

Only cart changes here. Frontend, catalogue and orders keep their selected
releases. Services do not need synchronized version numbers.

### 17.4 Roll back an application release

Use boutique-rollback with the previous known-good release:

~~~text
TARGET=production
SERVICE=cart
IMAGE=<previous fully qualified cart digest>
RELEASE_BUILD=<original release build that published that previous digest>
EVIDENCE_BUILD=<previous successful production verification of that digest>
~~~

Rollback evidence must be from the **same target environment**, match that
release and satisfy the 30-day age limit. The pipeline prepares a reviewed
GitOps selection and signs new verification after reconciliation.

Application rollback does not reverse a PostgreSQL migration or restore lost
data. Review backward compatibility before approval. Use expand/contract
schema changes if old and new applications must coexist.

Do not use kubectl rollout undo or helm rollback as the normal Argo-managed
application rollback. A manual change can be overwritten by desired state and
does not provide the signed review/evidence chain.

### 17.5 Retain recovery evidence

Keep known-good release/chart/evidence artifacts in access-controlled storage
for at least 35 days, and refresh verification before the 30-day limit.
Jenkins's current count-based build/artifact retention does not guarantee this
duration. A busy job can discard an old build sooner.

Archive exact versions, not just a screenshot saying green.
Read [deployment](runbooks/deployment.md) and [rollback](runbooks/rollback.md)
for the focused operator procedures.

## 18. Install and understand monitoring

### 18.1 Understand the signal flow

~~~mermaid
flowchart LR
  App[Application metrics endpoints] --> P[Prometheus]
  P --> G[Grafana dashboards]
  P --> R[Prometheus alert rules]
  R --> A[Alertmanager: group, inhibit, silence, route]
  A --> S[Slack receiver]
  A --> B[Authenticated incident bridge]
  B --> Q[Durable queue]
  Q --> W[Delivery workers]
  W --> SN[ServiceNow incident lifecycle]
  Logs[Container log files] --> Alloy[Grafana Alloy]
  Alloy --> Loki[Loki]
  Loki --> G
~~~

**Metrics** are numbers over time: requests, latency, errors and queue depth.
**Logs** are individual events: a request failed with a particular request ID.
**Alerts** are evaluated conditions requiring attention.
**Incidents** are response records with an owner, investigation and resolution.
Grafana displays signals; it does not replace Prometheus or durable storage.

### 18.2 Start the Compose monitoring exercise

Use this with the **Compose app**, not as a substitute for scraping kind Pods.
If you previously stopped Compose to use the single-kind app, restart the
Compose path first and stop its conflicting 8080 port-forward.

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
./scripts/local-up.sh
python3 monitoring/init-local.py
docker compose --env-file local/.env \
  -f local/compose.yaml -f monitoring/compose.yaml up -d --build
docker compose --env-file local/.env \
  -f local/compose.yaml -f monitoring/compose.yaml ps
~~~

In a second terminal, run:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
bash monitoring/capture-local-logs.sh
~~~

This foreground process follows application logs and writes local files for
Alloy. Keep it running during the exercise; Ctrl-C stops capture.
Alloy does not need the Docker socket.

| Local address | What to inspect |
| --- | --- |
| http://127.0.0.1:8085 | Grafana Boutique dashboard |
| http://127.0.0.1:9090 | Prometheus targets, queries and rules |
| http://127.0.0.1:9093 | Alertmanager alerts, routing and silences |
| http://127.0.0.1:18080 | Local Slack/ServiceNow receiver fixture |

Grafana username is admin. Read its generated password privately from
monitoring/.secrets/grafana_password. The initializer preserves it.
Changing that file after Grafana's database is initialized does not by itself
reset Grafana's stored admin password.

Run the notification fixture exercise:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 monitoring/test_delivery.py
bash monitoring/validate.sh
~~~

The fixture is an unauthenticated, ephemeral test receiver, bound to loopback.
These commands exercise local delivery; they do not create real external
Slack messages or ServiceNow incidents.

### 18.3 Read the dashboard panel by panel

The provisioned dashboard has thirteen panels:

| Panel | How to interpret it |
| --- | --- |
| Service availability | Whether Prometheus can scrape expected service targets |
| Requests per second | Traffic rate; a quiet lab can legitimately have zero |
| HTTP error ratio | Fraction of observed requests returning errors |
| HTTP p95 seconds | Latency below which 95% of observations fall |
| Firing alerts | Current evaluated alert conditions |
| Pending incidents | Durable delivery backlog |
| Oldest incident seconds | How long the oldest pending delivery has waited |
| JVM heap bytes | Orders JVM memory usage |
| Frontend heap bytes | Frontend process heap usage |
| Application logs | Loki log view for investigation |
| Incident dead letters | Deliveries that exhausted retry attempts |
| Incident worker heartbeat age seconds | Detects a stuck worker even if its HTTP endpoint exists |
| Incident bridge scrape availability | Visibility of individual adapter replicas |

Select the intended cluster/environment. Do not combine dev load with
production measurements and then call the result production availability.

In Prometheus, try:

~~~promql
up
~~~

Then:

~~~promql
sum by (service) (rate(boutique_http_requests_total[5m]))
~~~

No result can mean missing telemetry or no applicable series, not necessarily
healthy zero traffic. Inspect the Targets page first.

For the Kubernetes log configuration, the Loki labels include cluster,
environment, service and container. For example:

~~~logql
{cluster="nonprod", environment="dev", service="cart"}
~~~

Request IDs are log fields, not metric labels. Unbounded labels such as order
IDs and session IDs would create excessive metric series.

### 18.4 Understand the alert rules

| Rule | Operational meaning |
| --- | --- |
| BoutiqueServiceDown | Expected application service cannot be scraped |
| BoutiqueHighErrorRate | Sustained request error ratio above the rule threshold |
| BoutiqueHighLatency | Sustained response latency above the rule threshold |
| AlertmanagerDeliveryFailures | The notification system cannot deliver successfully |
| PrometheusRuleFailures | Rule evaluation itself is failing |
| IncidentDeliveryBacklog | Queue items have waited too long |
| IncidentDeliveryDeadLetters | At least one durable delivery needs operator recovery |
| IncidentWorkerStalled | A worker heartbeat is stale |
| IncidentBridgeUnavailable | Discovered bridge replica cannot be scraped |
| IncidentBridgeMissing | Expected bridge targets are absent entirely |

Read monitoring/rules.yml for exact expressions, traffic floors and durations.
A threshold alert is different from an SLO error-budget burn alert.

Alertmanager groups related signals and inhibits matching warning alerts when
a critical one is firing. Normal Kubernetes repeat notifications are limited
to four hours; local fixtures use much shorter timings to make exercises quick.
An expiring silence needs an owner and reason. A silence suppresses notification,
not the underlying failure.

All configured alerts route to Slack. Critical **production application**
alerts additionally route to ServiceNow. Alerts about the incident-delivery
path carry incident_delivery=disabled and remain Slack-only, avoiding a
recursive queue of incidents about the queue being broken.

### 18.5 How the incident adapter survives failures

The adapter first authenticates an Alertmanager batch and durably commits
it, then acknowledges it. Delivery to ServiceNow happens separately.

| Profile | Queue | Workers | Receiver mode |
| --- | --- | --- | --- |
| Affordable local/homelab | SQLite WAL volume | Exactly one replica | Table API |
| Production learning profile | Dedicated TLS PostgreSQL | Two replicas | Scripted lifecycle endpoint |

Production workers use transactional locked-row claims, 60-second leases,
revision-safe acknowledgements and capped backoff. A crashed worker's lease
can expire so another worker retries the item.
After twelve failed attempts, an item becomes a durable dead letter; fixing
the receiver and using the authenticated requeue workflow is the recovery path.

Delivery is **at least once**: a remote write can succeed while its response is
lost, so the caller retries. The receiver's lifecycle identity and tombstones
handle duplicates and a resolved event arriving before a delayed firing event.
Do not delete the queue or completed tombstones to make an alert disappear.

Two adapter replicas do not make the queue database HA. The local production
queue PostgreSQL is still single replica.

### 18.6 Deploy monitoring in the full kind lab

Complete the relevant application baselines first. Nonprod monitoring expects
dev and staging; production monitoring expects production.

1. Run boutique-platform/main on the release controller. Its shared service
   pipeline builds **incident-bridge**, including real PostgreSQL integration.
2. Inspect the successful signed release and capture the image digest.
3. Open a reviewed GitOps PR changing the adapter image values in
   monitoring/profiles/nonprod/values.yaml and
   monitoring/profiles/production/values.yaml.
4. Add/update the image object under incidentBridge without removing the
   existing production spec/replica configuration:

~~~yaml
incidentBridge:
  image:
    repository: ghcr.io/subhankar12-spec/boutique-incident-bridge
    digest: sha256:REPLACE_WITH_THE_ACTUAL_64_HEX_DIGEST
    tag: ""
~~~

The string above is explanatory and must be replaced with the measured release
digest. The default replace-with-tested-digest tag deliberately fails the
full-lab immutable-image check.

The lab monitoring values supplement these cloud profile values with internal
receiver fixtures and local data/TLS settings. Changing the image is a reviewed
monitoring GitOps change; the application promote job accepts only the four
application services.

After the policy check, CODEOWNER review and merge:

~~~bash
git -C "$BOUTIQUE_ROOT/boutique-gitops" pull --ff-only origin main
cd "$BOUTIQUE_ROOT/boutique-platform"

python3 ../boutique-gitops/scripts/render-monitoring.py nonprod --lab \
  > /tmp/boutique-monitoring-nonprod.yaml
python3 ../boutique-gitops/scripts/render-monitoring.py production --lab \
  > /tmp/boutique-monitoring-production.yaml

python3 scripts/production-lab.py deploy --cluster nonprod --monitoring
python3 scripts/production-lab.py deploy --cluster production --monitoring
~~~

Wait for **lab-monitoring-nonprod** and **lab-monitoring-production** to be
Synced/Healthy, then:

~~~bash
python3 scripts/production-lab.py readiness --cluster nonprod --monitoring
python3 scripts/production-lab.py readiness --cluster production --monitoring
~~~

The lab's earlier secrets command prepares fixture integration/Grafana secrets,
and production queue credentials/trust. Cloud deployment needs independently
prepared real receiver/database secrets.

Expose nonprod admin interfaces locally, each in its own terminal:

~~~bash
kubectl --context kind-boutique-nonprod -n monitoring \
  port-forward --address 127.0.0.1 service/grafana 18085:3000
~~~

~~~bash
kubectl --context kind-boutique-nonprod -n monitoring \
  port-forward --address 127.0.0.1 service/prometheus 19090:9090
~~~

~~~bash
kubectl --context kind-boutique-nonprod -n monitoring \
  port-forward --address 127.0.0.1 service/alertmanager 19093:9093
~~~

Use the production context and different local ports if forwarding both
clusters simultaneously. Obtain Grafana's password from the corresponding
monitoring-integrations Secret using operator access privately.

Alloy runs in a separate monitoring-logs namespace with a reviewed exception
for read-only host log files and root file reading. It drops capabilities and
cannot escalate privileges. This exception must not be copied to app Pods.
Log position state can replay duplicates after node restart.

### 18.7 Prepare real Slack and ServiceNow separately

The default lab uses mocks. For live activation:

- Create an approved Slack incoming webhook for a dedicated alert channel.
  Store its URL as the slack_webhook secret, never in tracked YAML.
- Create a ServiceNow developer instance using ITSM Incident Management.
  It teaches lifecycle/correlation without requiring ITOM licensing, but can
  sleep/reset and is not a production service.
- Create a dedicated integration user with the necessary incident/lifecycle
  ACLs; do not use an administrator account.
- Review and install monitoring/servicenow/scripted-rest-resource.js,
  its lifecycle table, correlation field and required unique indexes.
- Configure the real HTTPS instance URL, username, password secret and your
  instance's valid close-code/required-field choices.
- Validate the endpoint in that instance before replacing mock receivers.
  Changing only the URL does not install its server-side lifecycle logic.
- Run an intentional firing/resolution/retry exercise in the approved channel
  and instance, recording the incident identity and resolution.

The supplied Table API mode uses Basic authentication over verified HTTPS;
organizations may require OAuth and additional ACL/business-rule changes.
No real remote notification has been activated by this guide.

### 18.8 What this monitoring stack does not yet prove

The handwritten Prometheus, Alertmanager, Grafana and Loki stack is single
replica. A production-reference kube-prometheus-stack values file is a separate
reference, not an automatically installed second stack.

Continuous external journey probes, automated SLO burn alerts, on-call paging,
external dead-man detection, long-term object storage, SSO and backup automation
still need deployment and validation.
Read [monitoring](monitoring.md) for receiver and queue recovery details.

## 19. Understand the AWS reference

You do not need an AWS account for the kind learning path.
The AWS code is a realistic managed-infrastructure reference and has not been
applied. It can create substantial ongoing charges.

### 19.1 Read the infrastructure in dependency order

~~~mermaid
flowchart TD
  State[Restricted versioned Terraform state backend] --> Roots[Separate nonprod / production roots]
  Roots --> VPC[Three-AZ VPC and subnet routing]
  VPC --> EKS[Private EKS API and workers]
  VPC --> DB[Managed PostgreSQL and Redis]
  Roots --> KMS[Encryption keys and Secrets Manager]
  EKS --> IAM[OIDC / IRSA identities]
  IAM --> ESO[External Secrets controller: operator installs]
  ESO --> Sec[Kubernetes Secrets]
  Sec --> Apps[Application Pods]
  EKS --> Boot[Argo, ingress, TLS: operator bootstrap]
  Boot --> Apps
  Audit[Separate once-per-account audit root] --> Trail[CloudTrail and audit destinations]
~~~

Terraform state records which resources it manages and their current attributes.
A plan compares desired configuration to state and AWS; apply performs the
approved changes. State can contain generated secrets even when CLI output
marks them sensitive.

The top-level roots select independent environment settings/state. Both call
the same modules/platform directory. Terraform combines all .tf files in a
directory into one module; filenames organize code, not execution order.

| Platform module file | What to read there |
| --- | --- |
| main.tf | Availability-zone selection and tags |
| networking.tf | VPC module, subnets, NAT and database security rules |
| eks.tf | Private cluster, workers, access entries and core addons |
| iam.tf | IAM/OIDC and External Secrets roles |
| encryption.tf | Platform data key/alias |
| databases.tf | PostgreSQL and Redis settings |
| secrets.tf | App credentials and Secrets Manager values |
| monitoring.tf | Dedicated queue DB and monitoring secret roles |
| observability.tf | Logs, alarms, dashboard, SNS and optional insights |
| operator.tf | Private SSM-only operator host |
| budgets.tf | Tagged monthly budget notifications |
| variables.tf / outputs.tf / versions.tf | Input/output/provider contracts |

The VPC is a version-pinned terraform-aws-modules/vpc/aws child module.
Its underlying subnet/route/NAT resources are downloaded on init, so you will
not see every raw aws_subnet resource in your local networking.tf.
Read the [module map](https://github.com/subhankar12-spec/boutique-infrastructure/blob/main/modules/platform/README.md).

### 19.2 Networking and managed data

| Concern | Nonprod | Production |
| --- | --- | --- |
| Separate VPC | 10.10.0.0/16 | 10.20.0.0/16 |
| Availability zones | Three | Three |
| Subnet classes | Public, private workers, private data | Same separation |
| NAT gateways | One, cost-saving availability compromise | One per AZ |
| EKS API | Private | Private |
| Orders RDS | Per application environment, shorter backup retention | Multi-AZ, 14-day backups |
| Redis | TLS/authenticated, smaller availability profile | TLS/authenticated, Multi-AZ failover/replicas |
| Optional incident queue RDS | Separate DB, 7-day retention | Enabled by default, separate Multi-AZ DB, 35-day retention |

A private EKS API cannot be administered directly from arbitrary laptop
internet access. You need a reviewed private network path and authorized role.
The operator host uses SSM with no inbound SSH; its basic instance role does
not itself make it Kubernetes cluster-admin.

Orders and queue databases are distinct. Their admin credentials and
least-privilege application roles are distinct too.
The app owns its schema and runs Flyway migrations; a separate migration
identity is a further hardening step.

### 19.3 IRSA, ESO and CSI: different layers

**IRSA** answers: “Which AWS role may this Kubernetes service account assume?”
The EKS OIDC issuer plus IAM trust conditions bind the role to the intended
namespace/service-account subject.

**External Secrets Operator, ESO** answers: “How does an external secret become
a Kubernetes Secret?” It reads Secrets Manager using the configured role and
reconciles Kubernetes Secrets that applications reference.

**Secrets Store CSI Driver** is another delivery approach: it can mount external
secrets into a Pod filesystem, with optional synchronization depending on setup.
This project uses ESO for AWS secret delivery; it does not configure that
secrets CSI driver.

IRSA and CSI are not alternatives at the same layer. A CSI provider could also
need an AWS workload identity. Here the chosen combination is **IRSA + ESO**.

The EKS Pod Identity agent addon appears in the reference, but no workload
associations are configured to replace the current IRSA roles.

Storage CSI is a separate topic again. An EBS CSI provisioner is needed if
you choose EBS-backed Kubernetes PVCs. Do not assume installing a secrets
controller provisions persistent disks; review the cloud storage driver and
StorageClasses before applying monitoring PVCs.

### 19.4 CloudWatch versus CloudTrail

| Service | Question it helps answer | This project's configuration |
| --- | --- | --- |
| CloudWatch | Is infrastructure/application infrastructure healthy? | EKS control-plane logs, VPC flow logs, DB/cache logs, alarms, dashboard and SNS |
| CloudTrail | Who performed which AWS API action? | Separate account-audit root with multi-region management-event trail |
| Prometheus/Grafana | How are application requests and incident delivery behaving? | App/runtime monitoring deployed separately |
| Loki/Alloy | What did application containers log? | Separate app log collection |

The CloudWatch reference includes encrypted EKS control-plane log groups,
network flow logs, PostgreSQL/upgrade logs and Redis slow/engine logs.
Service log retention differs by environment, with longer production retention.
RDS CPU/free-storage and Redis CPU/memory alarms notify through encrypted SNS.
The email subscription must be confirmed; a Terraform resource alone does not
prove someone receives an alarm.

Optional Container Insights is disabled by default and requires reviewed addon
compatibility/identity/cost configuration. Automatic language instrumentation
is not enabled by the reference.

The separate audit root configures management events across regions,
global service events, trail log validation, KMS, a private versioned S3
destination, CloudWatch logs and security/configuration alarms.
Default S3 audit retention is 365 days with a 90-day archival transition;
the log group has its own retention.
S3 data events are an optional scoped choice, not blanket default collection.
This is not an organization-wide trail or a deployed cross-region DR system.

Read [AWS observability](https://github.com/subhankar12-spec/boutique-infrastructure/blob/main/docs/aws-observability.md).

### 19.5 Validate Terraform without provisioning

These checks do not require applying resources or entering AWS keys:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-infrastructure"
terraform fmt -check -recursive
terraform -chdir=environments/nonprod init -backend=false -lockfile=readonly
terraform -chdir=environments/nonprod validate
terraform -chdir=environments/production init -backend=false -lockfile=readonly
terraform -chdir=environments/production validate
~~~

Init downloads providers/modules. It still needs network/disk and compatible
provider locks. If restored .terraform cache paths are invalid, use a fresh
TF_DATA_DIR outside Git instead of editing/removing provider locks.

~~~bash
mkdir -p "$HOME/.cache/boutique/terraform-nonprod"
TF_DATA_DIR="$HOME/.cache/boutique/terraform-nonprod" \
  terraform -chdir=environments/nonprod init -backend=false -lockfile=readonly
TF_DATA_DIR="$HOME/.cache/boutique/terraform-nonprod" \
  terraform -chdir=environments/nonprod validate
~~~

Use a different data directory for production/audit. This validates configuration
structure, not AWS quotas, IAM access, regional version availability or runtime.

### 19.6 Understand the eventual apply sequence

Before any AWS apply:

1. Select account/region, compatible versions, private access and a reviewed cost
   estimate. Budget alerts notify; they do not stop spending.
2. Bootstrap the encrypted/versioned state bucket, preserve initial bootstrap
   state and migrate it to its own remote key.
3. Prepare backend/tfvars from each root's examples, replacing example account,
   email, bucket and role values. Never place AWS keys there.
4. Configure short-lived agent identity and scoped state/resource permissions.
5. Run protected Terraform planning on terraform-trusted.
6. Review the redacted resource-action summary and approve the exact saved plan
   as platform-admin.
7. Initialize application/queue data roles over the private network using
   verified CA trust.
8. Install/configure Argo, ESO, ingress/TLS controllers and storage drivers.
9. Configure real DNS, certificates, secret roles and approved releases.
10. Measure actual deployment, notification, backup and recovery behavior.

The saved binary plan stays in a private directory and is not archived because
it can contain secrets. Approval applies that same plan; it is not permission
to generate an unrelated plan later.

The current backend uses versioned private S3, TLS enforcement and native S3
lock files. Nonprod, production and audit have distinct state keys.
Backend encryption does not remove the need to restrict state access/backups.

Terraform does not provision every platform controller/agent automatically.
The [infrastructure README](https://github.com/subhankar12-spec/boutique-infrastructure/blob/main/README.md)
is the starting point for that separate, paid deployment.

## 20. Practice failures, backup and recovery

### 20.1 Understand SLO, RTO and RPO with this app

| Term | Plain meaning | Example here |
| --- | --- | --- |
| SLI | Measured reliability indicator | Fraction of eligible frontend responses that succeed |
| SLO | Target for that indicator | 99.9% API response availability over 30 days |
| Error budget | Allowed bad events within the objective | At one million eligible requests, 0.1% allows 1,000 failed responses |
| RTO | Time from user-impacting failure until verified recovery | Intended 30-minute compatible app rollback |
| RPO | Accepted loss of committed data | Intended zero lost committed DB writes for app-only rollback |

The documented objectives include 99.9% API/checkout response availability
and 99% of successful eligible API responses within one second.
The window is rolling 30 days.

Current Prometheus retention is seven days. You cannot truthfully report a
complete 30-day SLO from seven days of history. Extend reviewed retention/
storage to at least 35 days or add equivalent durable aggregation first.
Missing telemetry or zero traffic is unknown, not 100% success.

Frontend response metrics cannot observe every DNS/TLS failure or a request
that never reaches/completes at the server. A release smoke test is not a
continuous external availability probe.
Read [SLO definitions and queries](slo.md).

### 20.2 Recovery targets are plans to prove

| Scope | Intended RTO | Intended RPO | Important condition |
| --- | --- | --- | --- |
| Compatible application rollback | 30 minutes | Zero committed DB writes | Retained signed prior artifacts/evidence |
| Laptop/VM local data loss | 4 hours | 24 hours | Daily consistent encrypted off-host backups |
| AWS orders or dedicated queue PITR | 60 minutes | 15 minutes | Actual latest-restorable-time and verified restore/cutover |
| Redis carts | 60 minutes | 24 hours | Valid snapshot/persistence restore and matching credentials |
| Jenkins config/history | 4 hours | 24 hours | Separate controller backups and accepted release retention |
| Rebuild cluster around recoverable managed data | 4 hours | Data-store objectives | Reproducible config, access, trust, registry and backups |

These are not achieved measurements. A 14-day backup-retention setting does
not guarantee a 15-minute RPO. Measure the actual data recovery point.
Multi-AZ availability reduces some failures; it is not regional disaster recovery.

### 20.3 Back up and restore the Compose orders database

Start the Compose app for this exercise. Do not point these Compose helpers
at a kind Pod.

~~~bash
umask 077
mkdir -p "$HOME/boutique-backups"
chmod 700 "$HOME/boutique-backups"
cd "$BOUTIQUE_ROOT/boutique-platform"
./scripts/backup-local.sh "$HOME/boutique-backups/orders.dump"
./scripts/restore-drill.sh "$HOME/boutique-backups/orders.dump"
~~~

The backup is PostgreSQL's consistent custom-format logical dump.
The first helper checks archive readability, not complete data recovery.
The second drops/recreates **boutique_restore_drill**, a disposable database,
and restores into it; it does not overwrite the live boutique database.
Do not run concurrent drills using that same disposable name.

Before backup, record representative order IDs/counts and UTC times.
After restore, compare recovered data with those records.
A row count alone does not prove the latest acknowledged write survived.

The destination above is on your laptop. It is useful for the exercise but does
not survive loss of that laptop. Implement encrypted independent storage,
scheduling, failure/age alerts and periodic restore validation to meet the
off-host objective.

### 20.4 Practice the kind lab's recovery and policy drills

Use dev first:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
python3 scripts/production-lab.py policy-drill --environment dev
python3 scripts/production-lab.py restore-drill --environment dev
~~~

The policy drill tests permitted ingress and denied unrelated access on the
enforcing CNI. It proves more than merely finding a NetworkPolicy YAML file.

The restore drill uses an isolated restore target and checks orders plus
migration history. Its measured database restore step is only part of end-to-end
RTO. Detection, provisioning, access, TLS, cutover and functional acceptance
also count.

To observe self-healing in dev, inspect Pods and choose one application Pod:

~~~bash
kubectl --context kind-boutique-nonprod -n boutique-dev get pods
~~~

Then delete only the chosen **dev** application Pod:

~~~bash
# Replace this name with one actual application Pod, not a database Pod.
kubectl --context kind-boutique-nonprod -n boutique-dev delete pod ACTUAL_APP_POD_NAME
kubectl --context kind-boutique-nonprod -n boutique-dev get pods --watch
~~~

The Deployment recreates it. Inspect readiness, request failures and metrics.
This can cause brief dev downtime; it is not a production disaster drill.

Node drain, database loss and host-loss exercises need reviewed scope, verified
backups and an isolated target. Local-volume database Pods cannot simply move
with their data to another worker. Do not begin by deleting PVCs/namespaces.

### 20.5 What to preserve besides PostgreSQL

| State | Why Git alone cannot restore it |
| --- | --- |
| Orders and incident queue, including lifecycle tombstones | Runtime committed data |
| Redis persistence | Existing anonymous carts |
| Session signing keys | Access to users' existing sessions/order history |
| CA private keys and matching trust | Continuity of verified lab certificates |
| Jenkins home volumes | Credentials encryption material, history and job state |
| Artifact/evidence signing keys | Future signatures and trust continuity |
| Accepted release/chart/evidence artifacts | Reconstruct and prove a known-good release |
| Terraform state and access | Managed-resource ownership and generated sensitive values |
| Grafana storage / Alertmanager silences | Runtime admin state and maintenance context |

A source ZIP/Git bundle is a source backup, not a database/credential backup.
The whole incident queue matters; copying only pending rows loses deduplication
and resolution history.

Document each exercise with actual UTC start/end, data-loss comparison,
source/artifact versions, backup checksum/location and follow-up work.
Use [recovery exercise template](runbooks/recovery-exercise.md),
[recovery targets](recovery-targets.md) and
[disaster recovery](runbooks/disaster-recovery.md).
There is no deployed secondary region/account or automatic regional failover.

## 21. Troubleshoot by following the dependency chain

Start at the layer producing the error. Rebuilding everything hides the cause.
Preserve logs/state and inspect the exact environment.

### 21.1 Quick symptom-to-layer map

| Symptom | First checks |
| --- | --- |
| Browser cannot reach app | Port-forward/ingress, correct port, hosts entry, TLS trust |
| Frontend loads but API fails | Frontend logs, backend Service/endpoints, dependency readiness |
| Pod Pending | Events, capacity, requests, PVC and node placement |
| PVC Pending | StorageClass/provisioner, node/storage events |
| ImagePullBackOff | Actual image, GHCR pull credentials/package scope, architecture |
| CrashLoopBackOff | Current and previous logs, config/secret consistency, data TLS |
| Jenkins waiting for executor | Correct label online, distinct policy executor |
| GitOps PR will not merge | Protection, exact status context, current-head check, reviewer |
| Argo OutOfSync/Degraded | Source revision, conditions, rendered resources, repo access |
| Smoke rejects origin | PUBLIC_ORIGIN and exact URL/proxy configuration |
| TLS verification fails | Hostname, correct cluster CA, issuance and expiry |
| ServiceNow queue grows | Receiver credentials/ACLs/network, DB health, workers/dead letters |

### 21.2 Inspect a Kubernetes workload in order

For dev in the full lab:

~~~bash
kubectl --context kind-boutique-nonprod -n boutique-dev get deployments,pods,services
kubectl --context kind-boutique-nonprod -n boutique-dev get pvc
kubectl --context kind-boutique-nonprod -n boutique-dev get events \
  --sort-by=.metadata.creationTimestamp
kubectl --context kind-boutique-nonprod -n boutique-dev describe deployment/cart
kubectl --context kind-boutique-nonprod -n boutique-dev logs deployment/cart --tail=100
kubectl --context kind-boutique-nonprod -n boutique-dev \
  get endpointslices -l kubernetes.io/service-name=cart
~~~

For a crashing Pod, substitute its real name:

~~~bash
kubectl --context kind-boutique-nonprod -n boutique-dev \
  logs ACTUAL_POD_NAME --previous --tail=100
~~~

For the single-kind exercise, replace the context with your chosen
BOUTIQUE_KIND_CONTEXT. The full-lab helper is not the troubleshooting entry
point for an unrelated existing cluster.

Do not dump all Secrets or environment variables into a public bug report.
Report object names, status/events and redacted errors.

### 21.3 Image and bootstrap problems

- An image containing bootstrap or local in the full lab means the signed
  release selection was not completed or you chose the wrong profile.
- Locally built images must be loaded into the **chosen** kind cluster for
  the single-cluster exercise. Loading a different cluster has no effect.
- Public source repositories do not make GHCR packages public automatically.
  Check package visibility and namespace ghcr-pull credentials.
- The runtime is Linux amd64. An incompatible platform image can produce
  exec-format errors.
- The signed verifier currently expects the supported single-platform digest
  flow. OCI multi-platform index digests and running platform digests need a
  reviewed verifier change before using a different publication model.

The full lab intentionally rejects fake/mutable images before creating Argo
Applications. Fix release publication/promotion; do not remove that check.

### 21.4 Database and TLS problems

Check whether the failing dependency is orders PostgreSQL, Redis or the
separate incident queue. They have different credentials and trust.

An initialized database still has its original password even if a Secret was
changed. Restore matching credentials or perform deliberate coordinated rotation.
Do not delete its volume as a password-reset shortcut.

For the full lab, inspect certificate state:

~~~bash
kubectl --context kind-boutique-nonprod -n boutique-dev get certificates
kubectl --context kind-boutique-nonprod -n boutique-dev get certificaterequests
kubectl --context kind-boutique-nonprod -n boutique-dev get ingress
~~~

Check readiness/events before an application stack trace. A leaf certificate
may not yet be issued, or its hostname/CA may be wrong.
PostgreSQL connections require verified trust and hostname, not just encryption.

Do not disable origin checks, probes, network policy or certificate verification
to make an acceptance test pass.

### 21.5 Jenkins problems

| Failure | Likely cause and next action |
| --- | --- |
| There are no nodes with label ... | Create/connect the expected label on the correct controller |
| Docker daemon unavailable | Agent process did not inherit correct rootless DOCKER_HOST |
| Bind-mounted fixture missing | Container agent and daemon do not share the same absolute workspace path |
| Child policy job never starts | Parent occupies the only matching executor |
| Signature verification fails | Wrong key pair, changed record, unsupported schema or expired evidence |
| Release tag already exists | Source was already published; reuse its original successful build |
| GitHub protection check fails | Missing required setting or bot lacks metadata read permission |
| Staging/prod review impossible | PR author and reviewer are the same identity |
| Cluster authentication expired | Renew/re-upload scoped verifier kubeconfig |
| Storefront unreachable from agent | VM/container loopback or missing hosts/private routing |

A release controller's private credentials must not be “temporarily” copied to
validation as a workaround. Fix the trust/routing/job configuration.

If source/main changes while a policy check is running, its stale evaluation
must fail. Run a fresh check for the current PR head/base.

### 21.6 Argo problems

~~~bash
kubectl --context kind-boutique-nonprod -n argocd get application boutique-dev
kubectl --context kind-boutique-nonprod -n argocd describe application boutique-dev
kubectl --context kind-boutique-nonprod -n argocd get pods
~~~

Inspect the configured repository/path/valueFiles/revision. For the full lab
they must include the lab values, not only cloud defaults.
Argo fetches remote main; an unpushed local commit is invisible.
The application charts are vendored in GitOps, so Argo does not need to
rebuild service code or fetch a mutable development checkout.

Network-policy discovery Roles need the correct namespaces; the lab monitoring
AppProject permits its reviewed application discovery namespaces.
Do not grant blanket cluster-admin to get around a missing scoped permission.

### 21.7 Monitoring and incident problems

Start with Prometheus Targets. A down scrape can be a network failure even when
the application is serving. A missing scrape series requires a missing-target
rule, not just an up == 0 comparison.

For a growing queue, inspect DB connectivity, queue age, dead letters,
per-worker heartbeat/scrape, receiver HTTP failures and ServiceNow instance
availability. Developer instances can sleep.

Fix credentials/ACLs/dependency first; pending retries resume automatically.
Dead letters need the adapter's authenticated recovery workflow documented in
its README. Removing the queue erases data and hides the failure.

## 22. Stop safely and resume later

### 22.1 Stop port-forwards, watches and log capture

Ctrl-C stops the foreground kubectl port-forward/watch or log-follow process.
It does not delete Pods, clusters or stored data.

### 22.2 Stop Compose while keeping data

For the Compose app plus monitoring:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-platform"
docker compose --env-file local/.env \
  -f local/compose.yaml -f monitoring/compose.yaml down
~~~

For Jenkins:

~~~bash
cd "$BOUTIQUE_ROOT/boutique-ci/jenkins"
docker compose down
~~~

**Do not add -v** if you want to preserve named volumes.
Keep generated .env files, secrets and signing keys as well.
Restart using the same startup commands and matching files.

Keep native build-agent daemons/VMs and tunnels under your chosen lifecycle
management; stopping a controller does not automatically stop its remote VMs.
Dispose of untrusted validation agents after their builds.

### 22.3 Preserve kind state

Kind does not provide a complete durable “pause the production environment”
operation. Rebooting Docker/your laptop can interrupt clusters and exposes
real restart/recovery behavior. After restart, check nodes, controller health,
PVCs, certificates and functional verification.

**Deleting a kind cluster deletes its node containers and their local data.**
For an intentionally disposable introductory cluster only:

~~~bash
# Destructive: use only after deciding this named cluster and data are disposable.
kind delete cluster --name boutique-learning
~~~

Do not copy that name if your chosen cluster has a different purpose.
For the full lab, use the [teardown runbook](runbooks/teardown.md) after backing
up state and deciding which data/trust must survive.

Do not run global Docker volume pruning as a routine cleanup step.
Do not delete namespaces/PVCs to fix a bad application release.
Argo pruning can delete resources removed from desired state, so review
resource deletion in GitOps PRs as carefully as image changes.

### 22.4 Restore your terminal context deliberately

A new shell does not remember BOUTIQUE_ROOT, PATH or KUBECONFIG exports.
For the full lab:

~~~bash
export BOUTIQUE_ROOT="$HOME/devops-boutique"
export PATH="$BOUTIQUE_ROOT/boutique-platform/.tools:$PATH"
export BOUTIQUE_NONPROD_KUBECONFIG="$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/nonprod/kubeconfig"
export BOUTIQUE_PRODUCTION_KUBECONFIG="$BOUTIQUE_ROOT/boutique-platform/local/production-lab/.state/production/kubeconfig"
export KUBECONFIG="$BOUTIQUE_NONPROD_KUBECONFIG:$BOUTIQUE_PRODUCTION_KUBECONFIG"
kubectl config get-contexts
~~~

For the introductory cluster, export its dedicated operator kubeconfig from
chapter 9 instead. Store a reviewed non-secret shell helper privately if useful;
do not include tokens/passwords in shell startup files.

## 23. Know what is implemented and what remains

The project is substantial source/configuration, not a certificate that it is
ready to serve paying customers.

| Capability | Present in source | What you must still configure/prove |
| --- | --- | --- |
| Four-language application | Frontend, catalogue, cart, orders and data flow | Actual host startup and intended load |
| Introductory runtime | Compose/local kind scripts and Helm profiles | Your Docker/kind/storage compatibility |
| Shared Jenkins build | Tests, scans, SBOM, chart publication, signed release | Agents, scoped credentials, actual protected-main run |
| Environment delivery | Bootstrap/promote/verify/rollback and locks | Protection, reviewer, controller origins and live chain |
| GitOps policy | Fixed trusted evaluation and chart/image provenance | Required status wiring for manual/automated PRs |
| Full kind foundations | Locked two-cluster controllers, TLS, Calico | Supported host and successful complete bootstrap |
| Runtime acceptance | Functional smoke, TLS/readiness, scoped verifier | Live results on your clusters |
| Monitoring | Dashboard, rules, logs, routing, durable incident adapter | Published bridge digest and live component health |
| Slack/ServiceNow | Secret-driven receiver preparation and lifecycle reference | Real webhook/instance/server-side endpoint and approved delivery test |
| SLOs | Definitions, queries and error-budget policy | Complete retention, continuous probes/reporting and measured objective |
| Local recovery | Logical backup and isolated restore helpers/runbooks | Scheduling, off-host encrypted storage and measured full recovery |
| AWS infrastructure | VPC/EKS/data/identity/logging/audit/reference modules | Account inputs, approved paid apply and controller bootstrap |
| Regional disaster recovery | Limitations and recovery planning | Independent backups/region/account, access and measured failover |

Important remaining gaps include backup automation, independent state/secret
protection, controller/monitoring HA, external paging/dead-man detection,
organizational SSO, verified storage drivers and full live recovery acceptance.
The unused GitOps multibranch entry is not a replacement for its fixed policy
job.

Source publication, code tests, Helm rendering, schema checks and isolated
runtime exercises establish specific properties. They do not prove the full
Jenkins → GHCR → GitOps → Argo → HTTPS sequence has run on your laptop.
Read [validation and limitations](validation.md) when assessing evidence.

## 24. Follow a practical learning sequence

Treat these as learning sessions with exit checks rather than a deadline:

| Session | Do | You can move on when... |
| --- | --- | --- |
| 1: Application | Compose, browse, cart, order, inspect service logs | You can explain which service/data store handles each action |
| 2: Kubernetes | Existing kind deployment, inspect Pods/Services/PVCs | You can explain image load, DNS, readiness and persistence |
| 3: Helm | Compare values with rendered YAML | You can locate the source of an environment setting |
| 4: Foundations | Two-cluster bootstrap, CA, Calico and Argo | You can distinguish cluster, namespace, trust and controller responsibilities |
| 5: Jenkins isolation | Controllers, native agents, seed jobs | Validation cannot publish/deploy and required agents are online |
| 6: Release | First four signed releases | You can trace commit → image digest → chart → signed record |
| 7: Delivery | Bootstrap dev, staging and production | Each environment has live successful signed verification |
| 8: Change/recover | Small service release, promotion, rollback | You can explain build-once promotion and schema constraints |
| 9: Observe/respond | Dashboard, alerts, fixtures, queue recovery | You can diagnose app failure versus notification failure |
| 10: Recovery | Backup, isolated restore, measured exercise | You have evidence of what was recovered and what remains unproven |
| 11: AWS | Read modules, validate roots, review architecture/cost | You can explain private access, state, IRSA/ESO and audit |

Keep a short lab journal: what changed, exact versions, what failed, how you
proved the fix and what you still do not know. Explaining a failed rollout
accurately teaches more than repeatedly deploying an unchanged green stack.

Before calling your deployed lab complete, check:

- App browse/cart/checkout and ownership/idempotency tests pass.
- Chosen profiles match the runtime; full lab uses only approved digests.
- Production has its own cluster/context and credentials.
- Validation cannot access release/deploy identities.
- Protected main and CODEOWNER/status requirements actually block an invalid PR.
- One approved service release completes dev → staging → production.
- A compatible rollback completes with fresh signed verification.
- Prometheus sees each replica; Grafana/logs show the correct environment.
- Mock alert firing/resolution and durable retries are demonstrated.
- An isolated restore matches known data and records observed RTO/RPO.
- Runtime secrets, keys and data have independent recoverable protection.
- Remaining gaps are recorded rather than described as already solved.

## 25. Glossary and command reference

### 25.1 Glossary

| Word | Meaning in this project |
| --- | --- |
| Repository | Independently versioned source/configuration project |
| Monorepo | Multiple components in one Git repository; this project instead uses eight repositories |
| Workspace | The parent folder holding those eight sibling checkouts |
| Microservice | Small independently built/deployed application component |
| API gateway | Frontend server routing browser API requests to backend services |
| Image | Packaged runtime filesystem/process definition |
| Container | Running instance of an image |
| Registry | Storage/distribution service for images and OCI chart packages |
| GHCR | GitHub Container Registry |
| Digest | Content-addressed identifier, used to select immutable artifacts |
| SBOM | Software bill of materials: inventory of package components |
| Attestation | Signed record binding claims to a particular artifact |
| Pod | Kubernetes's smallest scheduled runtime unit |
| Deployment | Controller managing application replicas and rolling updates |
| StatefulSet | Controller with stable identity/storage for stateful processes |
| Service | Stable network endpoint selecting matching Pods |
| Ingress | Rules routing external HTTP/HTTPS to Services |
| CNI | Cluster networking implementation; Calico enforces the full lab's policies |
| NetworkPolicy | Rules restricting Pod ingress/egress when the CNI enforces them |
| PVC | Request for persistent storage |
| StorageClass | Provisioning/storage policy for PVCs |
| ConfigMap | Non-secret Kubernetes configuration |
| Secret | Kubernetes secret-data object; base64 encoding alone is not encryption |
| Service account | Kubernetes workload identity |
| RBAC | Rules deciding which API resources an identity can access |
| Kubeconfig | Cluster connection/trust/identity/context document |
| Helm chart | Templates plus values/schema used to generate Kubernetes resources |
| GitOps | Reviewed Git desired state reconciled into the runtime |
| Argo Application | Object telling Argo which repository/path/revision to reconcile |
| Reconcile | Continuously bring actual state toward desired state |
| Drift | Actual state differs from desired configuration |
| Promotion | Select the already-built release for another environment |
| Rollback | Select a known-good earlier release, accounting for data compatibility |
| Probe | Health check controlling readiness/restart behavior |
| PDB | PodDisruptionBudget limiting voluntary disruption; not protection from all failures |
| TLS / CA | Encrypted authenticated connection / certificate authority establishing trust |
| Terraform root/module | Applied configuration boundary / reusable directory of Terraform configuration |
| State lock | Prevents concurrent conflicting Terraform state writes |
| Availability zone | AWS isolation boundary inside one region |
| Multi-AZ | Availability design across zones, distinct from cross-region DR |
| IRSA | AWS workload-role authentication using EKS service-account identity |
| ESO | Controller synchronizing external secrets into Kubernetes Secrets |
| CSI | Driver interface for storage/mount integration; specify which driver you mean |
| Dead letter | Durable item that exhausted retry attempts and needs recovery |
| Tombstone | Retained lifecycle record preventing replay from reopening completed work |
| SLI/SLO | Measured reliability indicator / target for it |
| RTO/RPO | Time-to-recover objective / accepted committed-data-loss objective |

### 25.2 Read-only command reference

Commands below inspect the **full lab dev** environment. Export its kubeconfig
as in chapter 15 first. Adapt contexts deliberately for another deployment.

~~~bash
# What contexts are available?
kubectl config get-contexts

# Are the nonprod nodes ready?
kubectl --context kind-boutique-nonprod get nodes

# What runs in dev?
kubectl --context kind-boutique-nonprod -n boutique-dev get deployments,pods,services,pvc

# What images are selected in Deployments?
kubectl --context kind-boutique-nonprod -n boutique-dev get deployments \
  -o 'jsonpath={range .items[*]}{.metadata.name}{"\t"}{.spec.template.spec.containers[*].image}{"\n"}{end}'

# Is Argo healthy and synchronized?
kubectl --context kind-boutique-nonprod -n argocd get applications

# What happened most recently?
kubectl --context kind-boutique-nonprod -n boutique-dev get events \
  --sort-by=.metadata.creationTimestamp

# What is this application's desired configuration?
python3 "$BOUTIQUE_ROOT/boutique-gitops/scripts/render.py" dev --profile lab \
  > /tmp/boutique-dev-inspection.yaml

# Is my checkout clean and which commit am I reading?
git -C "$BOUTIQUE_ROOT/boutique-platform" status --short
git -C "$BOUTIQUE_ROOT/boutique-platform" log -1 --oneline
~~~

### 25.3 Where to read next

| Question | Focused document |
| --- | --- |
| How do all components fit together? | [Architecture](architecture.md) |
| How does the full kind runtime work? | [Production lab](production-lab.md) |
| How do I operate Jenkins? | [Jenkins setup](jenkins-setup.md) |
| How do charts and digests reach GitOps? | [Helm delivery](https://github.com/subhankar12-spec/boutique-gitops/blob/main/docs/helm-delivery.md) |
| How do I handle an incident? | [Incident response](runbooks/incident-response.md) |
| How do I recover data/controllers? | [Backup/restore](runbooks/backup-restore.md), [Jenkins recovery](runbooks/jenkins-recovery.md) |
| What are our intended reliability targets? | [SLOs](slo.md), [recovery targets](recovery-targets.md) |
| Which checks actually ran? | [Validation](validation.md) |
| What paid cloud work is separate? | [Infrastructure](https://github.com/subhankar12-spec/boutique-infrastructure/blob/main/README.md) |

When you are lost among the files, start with the action you want to perform:
application behavior, artifact build, environment selection, infrastructure
change or incident response. Find that repository in chapter 4, follow its
inputs and outputs, and inspect the rendered/live result at the next boundary.
