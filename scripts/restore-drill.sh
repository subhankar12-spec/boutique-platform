#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../local"
BACKUP=${1:?Usage: restore-drill.sh /secure/path/backup.dump}
# Separate throwaway database; never overwrite boutique.
docker compose exec -T postgres dropdb -U boutique --if-exists boutique_restore_drill
docker compose exec -T postgres createdb -U boutique boutique_restore_drill
docker compose exec -T postgres pg_restore -U boutique -d boutique_restore_drill --exit-on-error < "$BACKUP"
docker compose exec -T postgres psql -U boutique -d boutique_restore_drill -v ON_ERROR_STOP=1 -c 'SELECT count(*) AS restored_orders FROM orders;'
echo 'Restore succeeded. Verify expected order count against your backup-time record.'
