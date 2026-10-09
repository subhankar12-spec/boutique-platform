#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ENVIRONMENT=${1:-dev}
case "$ENVIRONMENT" in dev|staging|production) ;; *) echo 'Invalid environment'; exit 1;; esac
if ! kind get clusters | grep -qx boutique; then kind create cluster --name boutique --config local/kind.yaml --image kindest/node:v1.34.0; fi
kubectl config use-context kind-boutique
./scripts/init-local.sh
(cd local && docker compose build)
for service in frontend catalogue cart orders; do
  docker tag "boutique-$service:latest" "boutique-$service:local"
  kind load docker-image "boutique-$service:local" --name boutique
done
python3 scripts/k8s-secrets.py "$ENVIRONMENT"
python3 ../boutique-gitops/scripts/render.py "$ENVIRONMENT" --profile local | kubectl --context kind-boutique apply -f -
for service in frontend catalogue cart orders; do kubectl -n "boutique-$ENVIRONMENT" rollout status "deployment/$service" --timeout=240s; done
echo "Use kubectl -n boutique-$ENVIRONMENT port-forward service/frontend 8080:8080; then run python3 tests/smoke/smoke.py"
