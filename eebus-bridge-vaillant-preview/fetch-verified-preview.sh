#!/bin/sh
# Fail closed: only the exact signed digest from our preview workflow is valid.
set -eu
if [ "$#" -ne 2 ]; then
    echo "usage: fetch-verified-preview <pinned-image@digest> <target>" >&2
    exit 64
fi
image="$1"
output="$2"
repository="ghcr.io/meneomic/eebus-bridge"
issuer="https://token.actions.githubusercontent.com"
identity="https://github.com/meneomic/eebus-ha-bridge-v940f/.github/workflows/vaillant-preview-image.yml@refs/heads/feat/vaillant-rc-preview"

case "$image" in
    "${repository}@sha256:"*) ;;
    *) echo "preview source must use the expected image repository and digest" >&2; exit 65 ;;
esac
digest="${image#${repository}@sha256:}"
if ! printf '%s\n' "$digest" | grep -Eq '^[0-9a-f]{64}$'; then
    echo "invalid preview digest" >&2
    exit 65
fi

cosign verify \
    --certificate-identity "$identity" \
    --certificate-oidc-issuer "$issuer" \
    "$image" >/dev/null

mkdir -p "$(dirname "$output")"
temp_dir="$(mktemp -d "$(dirname "$output")/.eebus-preview.XXXXXX")"
trap 'rm -rf "$temp_dir"' EXIT HUP INT TERM
regctl image get-file --platform local "$image" /usr/local/bin/eebus-bridge "$temp_dir/eebus-bridge"
if [ ! -f "$temp_dir/eebus-bridge" ] || [ -L "$temp_dir/eebus-bridge" ] || [ ! -s "$temp_dir/eebus-bridge" ]; then
    echo "signed preview binary missing or invalid" >&2
    exit 67
fi
chmod 0755 "$temp_dir/eebus-bridge"
mv -f "$temp_dir/eebus-bridge" "$output"
