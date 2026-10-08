#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/init-local.sh
(cd local && docker compose up -d --build)
python3 tests/smoke/smoke.py
