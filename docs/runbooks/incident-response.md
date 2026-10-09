# Incident Response

Record start time, environment and user impact. Check frontend readiness, service logs, metrics, data health and recent GitOps changes. Mitigate before exploring every root cause. Verify recovery with the full smoke suite. Write a brief incident record containing timeline, contributing causes, recovery evidence and owned follow-up actions.

Compare user impact against [SLOs](../slo.md). For infrastructure/data loss, follow the [DR runbook](disaster-recovery.md), including write fencing and replacement validation. Measure RTO from first impact and record RPO from acknowledged/recovered writes using [recovery-exercise.md](recovery-exercise.md).
