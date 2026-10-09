# Recovery time and recovery point objectives

These are initial planning targets, not guarantees or achieved measurements. The platform operator owns the recovery process; the application operator validates orders, migrations and API behavior. In this lab both roles can be the repository owner, but record each responsibility in an exercise. Confirm targets after measuring restoration on the actual host/account.

**RTO** is the elapsed time from user-impacting failure to restored, verified service. Include detection, response, provisioning, data restoration, DNS/TLS, rollout and acceptance. A timed `pg_restore` measures one step only.

**RPO** is the maximum accepted age of lost committed data: compare the latest acknowledged write before failure with the latest write recovered. Use a controlled write ledger/known order IDs and timestamps; backup age or restored row count alone cannot prove it. Record zero loss as zero, and unobservable loss as unknown.

## Targets by recovery scope

| Scope | RTO target | RPO target | Required recovery source | Current status |
| --- | --- | --- | --- | --- |
| Bad application release, schema still compatible | 30 minutes | 0 committed DB writes lost by application-only rollback | Retained signed image/chart release and same-environment verification | Reviewed rollback implemented; live end-to-end exercise pending |
| Laptop/cloud-VM loss, local application and queue databases | 4 hours | 24 hours | Daily consistent encrypted backups on a separate failure domain; configuration and matching secrets | Local logical backup/restore helpers exist; scheduling/off-host storage and full-host drill pending |
| AWS orders PostgreSQL data restore in the same region | 60 minutes | 15 minutes | RDS automated backups/PITR and accessible KMS/IAM/secrets | Production retention 14 days, nonprod 3 days configured; AWS deployment/restore/cutover untested |
| AWS dedicated incident-queue PostgreSQL restore | 60 minutes | 15 minutes | Complete queue PITR, including pending rows and deduplication tombstones | Production retention 35 days, nonprod 7 days when enabled; restore/replay untested |
| Redis cart data | 60 minutes | 24 hours | Snapshot/AOF as applicable, matching credentials and validated restore | AWS snapshot retention 7 days production/1 day nonprod; off-host local restore untested |
| Jenkins controllers and delivery artifacts | 4 hours | 24 hours for history/config; preserve every accepted release needed for rollback | Separate encrypted controller backups plus signed release/evidence artifacts, plugins and signing keys | Recovery runbook exists; backup automation and controller restore drill pending |
| Metrics/logs/Grafana/Alertmanager state | 60 minutes | 24 hours for retained history/silences | Git-provisioned configuration plus encrypted durable state backups | Configuration reproducible; state backup/restore untested; incident queue uses its own stricter targets |
| Primary cluster rebuilt around recoverable managed data | 4 hours | Data-store targets above | Reviewed Terraform/Helm/GitOps, registry packages, state, secrets and platform trust | Code/runbooks available; complete environment rebuild untested |

The 15-minute AWS RPO is a target to verify using each database's **latest restorable time**, not a consequence of setting backup retention or a guaranteed RDS replication delay. DB restore creates a new instance and requires endpoint/secret changes and functional verification. Daily snapshots alone do not establish a 15-minute RPO.

A local 24-hour RPO requires successful daily off-host backups. The current manual scripts do not satisfy that schedule by themselves. Cart loss is accepted within its target for this learning app; restoring the original session signing key matters because anonymous users otherwise lose access to their existing sessions/order history. Choose a stricter cart target before treating carts as durable business records.

Git and registry recovery require the exact reviewed commits, signed records and package/image digests; keep credentials and signing keys out of Git. Retain known-good release/evidence artifacts in access-controlled storage for at least 35 days and refresh verification before its 30-day rollback age limit. Count-based Jenkins build retention alone can delete required artifacts sooner; configure and verify retention separately. Back up keys/secrets after each controlled change and controller state at least daily to meet these intended targets.

## What disaster recovery currently covers

[disaster-recovery.md](runbooks/disaster-recovery.md) documents manual recovery and acceptance. Existing capabilities include local orders backups, an isolated logical restore exercise, a Kubernetes database restore drill, Jenkins recovery instructions and same-region AWS backup configuration.

There is **no deployed secondary region/account, automated failover, cross-region backup replication or complete DR acceptance result**. Multi-AZ RDS/Redis reduces some availability failures within one region; it does not establish regional DR. Separate kind clusters share the laptop/VM and do not survive loss of that host without independent backups.

The local verified Git bundles/source ZIP live on the same workspace host. They preserve source work but are not an off-host DR copy and exclude ignored secrets, database volumes and controller state. All eight source repositories are now published to GitHub with matching `main` commits. Full Kubernetes/AWS recovery remains unverified; remote source availability and source reconstruction do not prove data recovery or replace off-host state/secrets backups.

Regional/account-loss recovery needs a separately reviewed backup location, replication/retention, key and access design, infrastructure/DNS procedure and measured exercise before an RTO/RPO can be accepted. No regional-recovery target is claimed by this implementation.

## Backup and exercise policy to activate

| Data | Intended protection | Validation cadence |
| --- | --- | --- |
| Orders and queue databases | Daily consistent encrypted off-host local backups; AWS PITR with configured retention and independent export/replication if region loss is in scope | Monthly isolated restore and after schema/backup changes |
| Redis | Daily consistent snapshot or reviewed persistence backup; encrypt independent copies | Monthly representative cart restore |
| Jenkins, signing/session keys and credentials | Separate encrypted controller backups; secure key/secret export after changes; preserve release artifacts | Quarterly isolated controller recovery and after core/plugin changes |
| Terraform state, source and GitOps | Versioned restricted backend; off-host exact commits/refs and documented access recovery | Quarterly environment reconstruction |
| Monitoring state | Consistent backups of queue, Grafana storage and silences; retain metrics/logs as policy requires | Quarterly restore/replay exercise |

This table is a policy to implement on the selected host/account. No scheduler, off-host backup destination, cross-region copy or extra paid resource was enabled by this documentation change. Backups need restore validation and age monitoring; a created file or configured retention is insufficient.

For each drill, retain UTC timestamps, observed RTO/RPO, exact source/artifact versions, backup checksum/location, consistency boundary, protected data checks, smoke evidence and follow-up actions. A template is in [recovery-exercise.md](runbooks/recovery-exercise.md). Restore only into isolated targets until a reviewed cutover is authorized; do not destroy the production system to demonstrate DR.
