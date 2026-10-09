# Rollback

Restore a previously verified immutable image through GitOps, then verify it again. An application image rollback does not undo a Flyway migration or restore database data.

## Select the recovery candidate

Inspect current user impact, runtime metrics/logs, the deployed digest and recent changes. Select the successful `boutique-verify` build for the known-good digest in the **same environment**, and its original protected-main service release build. Production recovery requires production evidence; a dev/staging success cannot substitute for it.

Retained evidence must be at most 30 days old, refer to an earlier trusted GitOps commit and match the selected service/digest. Keep or periodically refresh verification of long-lived production releases before this window expires. A failed or unverified deployment cannot become a known-good candidate simply because its image exists in the registry.

Confirm backward schema compatibility before approving. This project's Flyway migrations are forward-only: prefer additive changes and a corrective forward migration where reverting application code would break the current schema. A destructive down migration is not automated by this workflow.

## Execute recovery

1. Run `boutique-rollback` with `TARGET`, `SERVICE`, the previous exact `IMAGE`, original `RELEASE_BUILD` and that environment's previous successful `EVIDENCE_BUILD`.
2. Review the archived planned diff, signed original release and signed previous verification. The job checks the current selected digest to reject a stale recovery request and uses the common environment delivery lock.
3. For production, `release-manager` authorizes recovery after compatibility review. Review the GitOps PR through its protected policy check and required CODEOWNER approval. Use a distinct reviewer from the PR creator.
4. Merge the reviewed PR and let Argo reconcile. The job frees its working agent before starting `boutique-verify`, while retaining the delivery lock through that verification. A failed child marks recovery unsuccessful.
5. Inspect the new signed evidence, metrics/logs and alerts. Retain the recovery verification build and record the incident timeline and follow-up work.

If the PR head/base changes, rerun the fixed policy check. If recovery fails, preserve evidence and investigate readiness, image pulling, dependency health, migrations and TLS/routing before proposing another change. Do not delete persistent data or the incident queue to clear an alert.

Do not use `kubectl set image` or `rollout undo` as the normal recovery path: Argo will reconcile the Git selection. A direct revert of a promotion commit also needs a matching signed rollback record and required policy checks; prefer the supplied job. Data loss requires the separately reviewed [backup/restore](backup-restore.md) procedure, not an image rollback.
