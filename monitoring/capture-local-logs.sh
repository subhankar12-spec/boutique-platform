#!/usr/bin/env bash
# Keep this process running while using the local monitoring profile. No Docker socket is mounted in Alloy.
set -euo pipefail
cd "$(dirname "$0")/../local"
mkdir -p ../monitoring/logs
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM
for service in frontend catalogue cart orders; do
  docker compose --env-file .env logs --follow --no-color --no-log-prefix "$service" >> "../monitoring/logs/$service.log" &
  pids+=("$!")
done
wait
