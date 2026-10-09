#!/usr/bin/env bash
# Install verified CLI artifacts into a caller-selected writable directory.
set -euo pipefail
DESTINATION=${1:-"$PWD/.tools"}
mkdir -p "$DESTINATION"
DESTINATION=$(cd "$DESTINATION" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fsSL https://dl.k8s.io/release/v1.34.0/bin/linux/amd64/kubectl -o "$TMP/kubectl"
curl -fsSL https://dl.k8s.io/release/v1.34.0/bin/linux/amd64/kubectl.sha256 -o "$TMP/kubectl.sha256"
printf '%s  %s\n' "$(cat "$TMP/kubectl.sha256")" "$TMP/kubectl" | sha256sum -c -
curl -fsSL https://github.com/kubernetes-sigs/kind/releases/download/v0.30.0/kind-linux-amd64 -o "$TMP/kind"
curl -fsSL https://github.com/kubernetes-sigs/kind/releases/download/v0.30.0/kind-linux-amd64.sha256sum -o "$TMP/kind.sha256"
printf '%s  %s\n' "$(cut -d ' ' -f 1 "$TMP/kind.sha256")" "$TMP/kind" | sha256sum -c -
curl -fsSL https://releases.hashicorp.com/terraform/1.11.4/terraform_1.11.4_linux_amd64.zip -o "$TMP/terraform.zip"
curl -fsSL https://releases.hashicorp.com/terraform/1.11.4/terraform_1.11.4_SHA256SUMS -o "$TMP/SHA256SUMS"
(cd "$TMP" && awk '$2 == "terraform_1.11.4_linux_amd64.zip" {print $1 "  terraform.zip"}' SHA256SUMS | sha256sum -c - && unzip -q terraform.zip terraform)
curl -fsSL https://github.com/yannh/kubeconform/releases/download/v0.6.7/kubeconform-linux-amd64.tar.gz -o "$TMP/kubeconform.tar.gz"
curl -fsSL https://github.com/yannh/kubeconform/releases/download/v0.6.7/CHECKSUMS -o "$TMP/KUBECONFORM_SUMS"
(cd "$TMP" && awk '$2 == "kubeconform-linux-amd64.tar.gz" {print $1 "  kubeconform.tar.gz"}' KUBECONFORM_SUMS | sha256sum -c - && tar -xzf kubeconform.tar.gz kubeconform)
curl -fsSL https://get.helm.sh/helm-v3.22.0-linux-amd64.tar.gz -o "$TMP/helm.tar.gz"
printf '%s  %s\n' '1e4ab49e429626cf6c6958d914248b78c9730803c2751b87627e171dc800e7bb' "$TMP/helm.tar.gz" | sha256sum -c -
tar -xzf "$TMP/helm.tar.gz" -C "$TMP" linux-amd64/helm
install -m 0755 "$TMP/linux-amd64/helm" "$DESTINATION/helm"
install -m 0755 "$TMP/kubectl" "$TMP/kind" "$TMP/terraform" "$TMP/kubeconform" "$DESTINATION/"
echo "Add $DESTINATION to PATH. Requires Linux amd64, curl, unzip and sha256sum."
