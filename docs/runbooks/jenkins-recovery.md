# Jenkins recovery

Back up the controller home to encrypted access-controlled off-host storage,
including original Jenkins credential encryption material and identity keys.
Retain accepted image/chart artifacts and exact source/config revisions.
Restore with matching core/plugins on an isolated host, with triggers/agents
disabled. Confirm job/library pins, credential scopes and approvals before
reconnecting reviewed-code workers. Never expose credentials to untrusted jobs.

Target controller RTO is four hours; config/history RPO is 24 hours. Count-based
build retention does not guarantee the 35-day artifact policy. Registry images
and Git-pinned chart packages must survive the Jenkins outage. There are no custom
artifact/evidence signing keys in the simplified setup. Keep session/TLS trust
keys independently backed up. Acceptance requires a measured controller restore.
