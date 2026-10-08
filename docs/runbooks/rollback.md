# Rollback

Inspect user impact and the last known-good image digests. Revert the GitOps promotion commit and wait for Argo reconciliation; run rollout and smoke checks. Do not rebuild an old tag. Confirm schema compatibility before application rollback. Flyway migrations are forward-only in this baseline: use additive changes and a corrective migration, not an automatic destructive down migration.
