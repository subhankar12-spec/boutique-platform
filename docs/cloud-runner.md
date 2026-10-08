# Cloud runner validation notes

This runner provides Docker with the VFS storage driver and restricted outbound connectivity from build containers. The standard multi-stage Maven/pip network steps could not resolve external registries inside build containers. Validation used:

- Official checksum-verified Maven and a JDK copied from its official container image.
- Maven's supported proxy settings and the machine's trusted Java CA store; TLS verification stayed enabled.
- Python dependencies resolved through the machine's supported route, frozen with artifact hashes, then installed from a local verified wheelhouse.
- Equivalent Docker test stages with named local dependency-cache contexts; refreshed Go compiled/tested with the official Go toolchain, then packaged into the pinned runtime image.

The application was exercised through real Docker Compose networking and PostgreSQL/Redis, not mocked dependencies. Container build caches were cleaned when VFS layering exhausted disk. These adjustments are runner-specific and are not embedded into production images or saved with credentials.

Nested kind failed to start kubelet/control-plane health on this host; its failed cluster was cleaned up. Kubernetes render/schema checks passed, but a deployment on Kubernetes is not verified here. Jenkins update-center and AWS RDS truststore domains were denied by the environment network policy. The required domain additions were saved in the environment draft; draft saving does not apply or publish them. Enable them in environment settings before retrying plugin bootstrap or certificate retrieval.
