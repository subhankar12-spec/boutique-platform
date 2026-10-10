# Incident delivery adapter

Alertmanager posts authenticated batches to `/alerts`. The adapter commits the whole group to its queue before returning `202`, then delivers to ServiceNow asynchronously. A queue row represents one fingerprint plus `startsAt` alert cycle. Resolution is terminal for that cycle; a fresh `startsAt` produces a new incident key.

## Deployment profiles

| Profile | Store | Replicas | Purpose |
|---|---|---:|---|
| Affordable Compose/homelab | SQLite WAL on its own persistent volume | 1 | Local delivery and recovery drills |
| Production/production lab | Dedicated PostgreSQL database | 2 | Shared durable queue, concurrent workers and safe rolling updates |

Set `QUEUE_DATABASE_URL` to enable PostgreSQL. Without it, `QUEUE_PATH` defaults to `/data/queue.db`. Do not scale the SQLite profile beyond one replica or share its file across hosts. Production Kubernetes mounts secret `monitoring-incident-queue` with keys `QUEUE_DATABASE_URL` and `postgresql_ca`; its URL uses `sslmode=verify-full&sslrootcert=/run/queue-ca/ca.crt`. Use a least-privileged role owning only the queue schema in a dedicated database. It needs table/index creation rights for startup migrations and normal DML. PostgreSQL startup schema changes are serialized with a transaction advisory lock.

The production lab supplies a separate PostgreSQL StatefulSet with its own CA, certificate, credentials and PVC. AWS uses a dedicated managed database and bootstrap role. Two bridge replicas tolerate one worker loss; actual database availability still depends on the database deployment. A single lab PostgreSQL pod is not database HA.

Production contains a PostgreSQL egress rule using documentation-only CIDR `192.0.2.0/24`. Replace this with the actual database subnet CIDRs before deploying to AWS. Namespace-local lab traffic is allowed by the monitoring namespace policy. Configure credentials through Secret/ExternalSecret resources, not tracked manifests.

## Delivery guarantees and failure recovery

Workers claim rows using `FOR UPDATE SKIP LOCKED`, commit a 60-second lease, and release the database transaction before network delivery. Each request times out after 10 seconds; the Table API flow makes at most three such requests. A crashed worker's row becomes eligible after lease expiry. A stale lease owner cannot acknowledge another owner's work. An acknowledgement covers only the revision it delivered: resolution arriving during a firing request remains queued.

Delivery is **at least once**. A remote write may commit before its response is lost. Table API mode looks up `correlation_id` on retry, but it cannot guarantee duplicate prevention under ambiguous writes or eventual consistency. The production profile uses `SERVICENOW_MODE=scripted`; configure the authenticated Scripted REST resource in [the reference resource](../servicenow/scripted-rest-resource.js), lifecycle tombstones and unique database indexes before enabling it. The reference requires review and testing against your own instance's ACLs, business rules and concurrent request behavior; local mocks do not prove ServiceNow execution.

The scripted reference needs:

- Table `x_boutique_alert_cycle`: `u_key` string length 64 with a unique index, `u_status` choice (`firing`, `resolved`), and `u_revision` integer.
- Incident field `u_boutique_alert_key` string length 64 with a unique index.
- Dedicated integration ACL/role, permission to read/update these records, and an authenticated `POST /api/x_boutique/alerts/upsert` resource.
- Close-code values reviewed for your ITSM instance.

Retries use exponential backoff capped at 15 minutes. After 12 failed deliveries a row becomes a durable dead letter; it remains in pending/backlog metrics. Fix the receiver or credential, inspect the row through a privileged database session, then POST `{"keys":["<64-hex-cycle-key>"]}` to `/retry` with the same bearer credential. The endpoint requeues only unfinished rows. A new resolution also clears a firing failure's retry state. Queue database backups and restore drills must include completed cycle rows as well as pending work: completed rows provide deduplication tombstones. Do not prune them without an explicit incident retention/replay policy.

## Security and health

`WEBHOOK_TOKEN_FILE` authenticates both ingestion and requeue requests. `SERVICENOW_PASSWORD_FILE` and `SERVICENOW_USERNAME` supply a dedicated integration user's Basic authentication over verified HTTPS. Files are reread per request to support rotation. Redirects are rejected; credentials, alert payloads and database URLs are never logged. Keep annotations free of secrets and personal information. Inbound requests are limited to 1 MiB and 100 alerts, with bounded metadata. `ALLOW_HTTP_MOCK=true` permits only loopback or the local `mock-receivers` hostname and connects directly to that internal HTTP receiver, avoiding an ambient external proxy; do not set it for production. Verified HTTPS production requests retain normal proxy support.

`/health/live` checks process reachability. `/health/ready` queries the queue and rejects a worker heartbeat older than the lease duration; a remote ServiceNow outage does not disable ingestion. `/metrics` exposes pending count, oldest pending age, pending retry attempts, dead letters and worker heartbeat age without incident keys or alert labels. Dashboard retry attempts are a gauge of pending attempts, not a monotonically increasing lifetime counter. Add independent monitoring for queue database availability, backup age and capacity.

## Validation

```bash
mkdir -p test-reports
docker build --target test -t boutique-incident-bridge:unit-test .
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=bind,source=$(pwd)/test-reports,target=/reports" boutique-incident-bridge:unit-test
docker build -t boutique-incident-bridge:test .
python3 run-postgres-tests.py --image boutique-incident-bridge:test
```

The separate Test stage runs SQLite delivery, authentication, migration and race regressions through `ci/test.sh`, emitting JUnit XML. The runtime image build does not execute tests. The PostgreSQL runner starts a dedicated disposable database on an isolated Docker network, creates test-only credentials in a protected temporary directory, runs integration tests from the built image and removes only its own resources. It never connects to the orders database. Tests cover independent worker processes, locked-row skipping, concurrent resolution, lease recovery and queue deduplication. This disposable test database uses an isolated plaintext Docker network; the actual production lab database uses verified TLS.

For an already isolated disposable database, install `requirements.txt` with hash checking and set `TEST_QUEUE_DATABASE_URL`, then run `python -m unittest -v test_postgres`. That test truncates its `queue` table. Never point it at a deployed queue.
