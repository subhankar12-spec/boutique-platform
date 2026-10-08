#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../local"
DESTINATION=${1:?Usage: backup-local.sh /secure/path/backup.dump}
umask 077
docker compose exec -T postgres pg_dump -U boutique -d boutique -Fc > "$DESTINATION"
docker compose exec -T postgres pg_restore --list < "$DESTINATION" >/dev/null
echo 'Backup created and archive format verified. Perform the restore drill to validate data.'
