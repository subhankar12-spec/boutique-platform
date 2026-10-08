#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
for repo in boutique-frontend boutique-catalogue boutique-cart boutique-orders boutique-ci boutique-infrastructure boutique-gitops boutique-platform; do
  if [[ -e "$repo/.git" ]]; then echo "Preserved $repo"; else git init -b main "$repo"; fi
done
