# Cloud runner validation notes

The runner supports Docker Compose but uses the VFS storage driver and exposes read-only cgroups to this process. Nested kind previously failed kubelet/control-plane health. The production-lab doctor now stops cluster creation when its host prerequisites are unmet; it does not pull node images or alter the existing application. Full two-cluster Kubernetes delivery must be exercised on the documented laptop Docker host or Linux VM.

Allow at least 30 GiB free Docker storage on a supported overlay2 host, or 60 GiB with VFS, plus 16 GiB RAM (24–32 recommended). Separate production-learning clusters do not require paid AWS resources. The AWS Terraform remains a configurable reference and was not applied.

## Build adaptations used here

Build-container networking could not resolve all Maven/pip dependencies through the available route. Equivalent test/build stages used official checksum-verified tools and local dependency caches:

- Maven and a JDK from its official image, with Maven's supported proxy configuration and the machine's trusted Java CA store.
- Hash-locked Python dependencies installed from a verified local wheelhouse.
- Official Go tooling and pinned runtime images, with the same application tests and build outputs.

TLS verification remained enabled. The adaptations do not embed runner credentials or proxy configuration in application sources/images. Docker build caches created by this work were cleaned when VFS copies exhausted available storage.

The application and monitoring checks used real Compose networking, PostgreSQL and Redis. Grafana was exercised separately, then its container/image was removed to preserve disk; its data volume and credentials were retained. The ServiceNow and Slack tests target local mocks only.

## Jenkins and truststore checks

Official Jenkins archive access allowed a complete checksum-locked plugin installation and a real Jenkins 2.580.1 runtime. Plugin-backed Declarative validation, Job DSL generation, JCasC and isolated child-job/lock behavior were exercised. Earlier update-center redirect failures no longer describe the validated archive installation path. No real source indexing, GHCR publication or Jenkins-to-cluster deployment was performed by that isolated runtime test.

The official AWS RDS CA bundle was fetched and validated, then committed as public trust material in the orders repository with its checksum. PostgreSQL and Redis client TLS tests verify both successful connections and rejection of invalid trust/hostnames. No TLS bypass was added.

## External configuration

Reusable startup instructions, repository revisions and required network domains are saved in the environment draft. Saving a draft does not apply or publish its settings or prove restoration in a new task. Review/save and publish through environment settings to activate them.

GitHub repository publication is blocked by the current integration's API permissions (`403 Resource not accessible by integration`). Local commits, source archives and Git bundles remain reviewable; they do not count as remote publication. Supply appropriate repository access through the supported integration before retrying the publisher. Keep tokens and secret values out of source, logs and chat.
