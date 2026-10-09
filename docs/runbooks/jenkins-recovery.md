# Jenkins Recovery

Back up each Jenkins home volume separately to encrypted access-controlled storage. Treat credential material and controller identity keys as sensitive. Restore to isolated controllers with the matching core/plugin lock, disable triggers, confirm job/config integrity, then re-enable agents and trusted credentials deliberately. Never restore release credentials onto the validation controller.

The intended controller RTO is four hours and configuration/history RPO is 24 hours; see [recovery-targets.md](../recovery-targets.md). Back up original credential encryption material/signing keys and retained release/evidence artifacts independently; regenerate neither during ordinary recovery. Count-based build retention does not guarantee the 35-day artifact policy. This remains a runbook until an isolated controller restore is measured.
