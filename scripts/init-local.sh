#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../local"
if [[ -e .env ]]; then echo 'Existing configuration preserved.'; exit 0; fi
umask 077
python3 - <<'INIT'
import secrets
from pathlib import Path
Path('.env').write_text(''.join(f'{name}={secrets.token_hex(32)}\n' for name in ['SESSION_SECRET','DATABASE_PASSWORD','REDIS_PASSWORD']))
INIT
echo 'Generated secrets in ignored local/.env.'
