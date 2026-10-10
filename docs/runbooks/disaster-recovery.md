# Disaster recovery runbook

Scope: recover a failed primary host/cluster or restore same-region data into an isolated replacement. Targets and current gaps are in [recovery-targets.md](../recovery-targets.md). Regional/account loss is not supported by a tested DR deployment. Review paid provisioning and service/data cutover before execution; this runbook does not authorize destroying a live system.

## Establish the recovery boundary

1. Record the first known impact time, affected environment, failure domain and incident owner. Use an independent status/communication path if Jenkins or monitoring is down.
2. Pause deployments and stop/fence writes on the affected environment through a reviewed maintenance procedure. Fence the old writers before starting replacement writers, including incident workers, to prevent split-brain and duplicate remote delivery. Preserve readable disks, logs and evidence.
3. Choose application rollback for a compatible code regression; use this procedure for lost/corrupt infrastructure or data. Rollback cannot reverse a destructive migration or recover deleted orders.
4. Inventory accessible backup times, exact GitOps/CI commits, registry images/chart packages, Terraform backend versions, cloud IAM/KMS, secrets, TLS trust and DNS. Identify missing dependencies before choosing a recovery point. Prefer a point before corruption, not simply the newest snapshot.

## Reconstruct the foundation

Recover source from the trusted remote or independently secured Git bundles, retaining full history and reviewed refs. Local bundles in `/workspace/devops-boutique-git-backup` are a source aid, not an independent disaster backup. The source ZIP excludes credentials and runtime data.

For the laptop/VM lab, use a supported host, the pinned tool installer and [production-lab.md](../production-lab.md). Recover protected local CA/configuration/secret state before recreating workloads. Preserve existing private state rather than regenerating keys against old data. A new host may need explicit registry/repository authentication and DNS mapping; validate trust rather than disabling TLS.

For AWS, inspect actual surviving resources and state before planning. Restore access to the restricted versioned backend and KMS; select state versions deliberately and reconcile actual resource state. Do not force-unlock an active writer or blindly apply stale state. Use the trusted infrastructure job to review a saved plan. The audit root is account-level and must not be duplicated as a side effect of rebuilding a cluster. Restore private network access, platform controllers and External Secrets before applications. Region/account-loss infrastructure is a separate unimplemented design.

## Restore data into replacements

For local orders, use the existing non-production exercise first:

```bash
# Run from boutique-platform. Choose a protected absolute path on this host.
./scripts/backup-local.sh /secure/path/orders.dump
./scripts/restore-drill.sh /secure/path/orders.dump
# Kubernetes lab alternative, on the supported operator host:
python3 scripts/production-lab.py restore-drill --environment dev
```

These are isolated verification steps, not automatic production cutover. The Compose drill uses `boutique_restore_drill`; the Kubernetes drill uses a unique disposable database, records restore seconds and validates order count/Flyway history. The live database is preserved. Compare against the backup consistency boundary and known writes. A row count alone misses changed/missing records; inspect selected order IDs, totals, ownership and timestamps using protected operator access.

For AWS orders/queue, restore RDS PITR or a reviewed snapshot to a **new** private instance. Validate the chosen restorable timestamp, KMS permissions, schema/Flyway history and application database role. Review security groups, TLS hostname/CA and new endpoint secrets. The repository has no automatic endpoint cutover job; review and execute that change separately. Do not run test fixtures that truncate a queue against a deployed database.

Restore the complete incident queue, including completed-cycle tombstones, pending/resolution state and deduplication keys. Fence old workers and inspect in-flight leases. Wait for old leases to expire or perform a reviewed database correction; do not blindly replay every row. Reconcile delivered incidents with the receiver, because a write can have succeeded remotely before its response was lost. Retrying can be at least once, not exactly once.

Restore Redis persistence/snapshots and matching credentials where available. Validate representative carts. Recover the original frontend session signing key so existing cookies/session ownership remain valid; rotating it is a distinct intentional security operation, not a normal restore step.

## Recover delivery and observability

Restore the Jenkins controller with triggers/agents disabled initially. Follow [jenkins-recovery.md](jenkins-recovery.md), matching core/plugin locks and restoring original encrypted credential material, scoped credentials, release artifacts and job definitions. Never expose release credentials to untrusted build jobs. Validate JCasC/job integrity and scoped approvals before reconnecting agents.

Reconcile reviewed Helm/GitOps into the intended namespaces. Preserve stable resource names, reviewed image/package digests and controller trust. Start with data health, then application services, ingress/DNS and monitoring. Restore required Grafana/Alertmanager state and monitoring credentials. Keep notifications on internal mocks during an exercise; authorize a real receiver test separately before declaring real paging operational.

## Acceptance and controlled cutover

1. Check database health and recovered writes against the recorded ledger, backup boundary and migration compatibility. Record observed data loss and RPO; mark unknown if write history is unavailable.
2. Validate Argo source/revision, native rollout health, actual image IDs and TLS. Run the complete HTTPS smoke suite against the replacement's configured origin and retain fresh evidence. Rerun verification after recovery; retained reports describe the earlier deployment.
3. Confirm checkout ownership/pricing/idempotency, Redis state, incident queue delivery/reconciliation and monitoring visibility. Check that the old system cannot keep accepting writes.
4. Review the endpoint/DNS/secret cutover and restoration impact, then deliberately reopen traffic/writes. Do not switch DNS to an unvalidated replacement.
5. Record service recovery time and RTO only when these acceptance checks pass and the intended traffic works. `pg_restore` completion is not end-to-end recovery.
6. Retain the failed system/backups until a separate retention/decommission decision. Record gaps, data-loss decisions and recovery improvements using [recovery-exercise.md](recovery-exercise.md).

Run a monthly isolated data restore and quarterly environment/controller reconstruction on the selected host/account. A full-host exercise should recover on another host from independent backup storage while preserving the original. The current cloud runner cannot validate the full two-cluster path; an isolated Compose orders restore is the exercised boundary so far.
