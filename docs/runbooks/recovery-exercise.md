# Recovery exercise record

Copy this template to your incident/exercise record store. Keep raw database exports, sensitive identifiers and credentials in access-controlled storage; reference them by protected evidence location. An unknown value is not a pass.

| Field | Record |
| --- | --- |
| Exercise ID, owner, reviewer and environment | |
| Scenario and actual failure domain | |
| Approved scope and cutover/writes-fencing decisions | |
| Target RTO / RPO from recovery-targets.md | |
| First user impact / detection / mitigation start (UTC) | |
| Latest acknowledged controlled write before failure (UTC; protected ledger reference) | |
| Backup ID, consistency timestamp, checksum and independent storage location | |
| Latest recovered controlled write and missing-write checks | |
| Restoration complete / verification complete / traffic restored (UTC) | |
| Observed end-to-end RTO and observed RPO; pass/fail/unknown | |
| Source/CI/GitOps commits, chart/image digests and state version | |
| Database integrity, Flyway, cart/session and incident-queue reconciliation | |
| HTTPS smoke, native rollout and notification evidence locations | |
| Old writer fencing and replacement endpoint/TLS checks | |
| Cleanup decision; backups/original system retained | |
| Gaps, follow-up owners and due dates | |

RTO = service restored and verified timestamp minus first user-impact timestamp. RPO measures missing committed history using the controlled ledger; do not infer it solely from backup retention, restored row count or a newer database timestamp. If the original host never failed, label this an isolated restore/reconstruction exercise and do not claim a tested production failover.

Capture the SLO window/traffic/telemetry impact using [slo.md](../slo.md). Keep acceptance records distinct from proposed targets. No live recovery or scheduled backup is implied by filling in this template.
