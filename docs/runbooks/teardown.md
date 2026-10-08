# Teardown

For local services, docker compose down preserves volumes; use --volumes only when you explicitly intend data loss. Delete only your named kind cluster. For AWS review a destroy plan, retain required backups, explicitly remove deletion protection, and verify remaining billable resources. The state bucket remains protected. Never destroy production as an automated cleanup step.
