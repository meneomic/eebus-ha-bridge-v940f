#!/usr/bin/env bash
# Import ONLY three known pairing-identity files from a verified,
# unprotected HA backup into this app's private /data. Never print contents.
set -euo pipefail
umask 077
if [ "$#" -ne 2 ]; then
    echo "usage: import-eebus-identity <local-backup.tar> <private-data-dir>" >&2
    exit 64
fi
backup="$1"
target="$2"
source="aa6fc4a7_eebus_bridge.tar.gz"
if [ ! -f "$backup" ] || [ -L "$backup" ] || [ ! -s "$backup" ]; then
    echo "Migration aborted: backup missing or invalid" >&2
    exit 65
fi
if [ ! -d "$target" ] || [ -L "$target" ]; then
    echo "Migration aborted: private data directory missing or invalid" >&2
    exit 65
fi
# Fail closed on any previously imported or partially imported identity:
# never overwrite keys and never permit a new SKI to be generated.
if [ -e "$target/serial" ] || [ -e "$target/certs" ]; then
    echo "Migration aborted: existing identity found; manual review required" >&2
    exit 66
fi

staging="$(mktemp -d "$target/.eebus-restore.XXXXXX")"
trap 'rm -rf "$staging"' EXIT
mkdir -m 0700 "$staging/certs"
for item in serial certs/cert.pem certs/key.pem; do
    # Two nested archives: the outer HA backup and its unencrypted add-on tar.
    # -O writes ONE nominated member to stdout; no untrusted paths extracted.
    if ! tar -xOf "$backup" "$source" | tar -xzOf - "data/$item" > "$staging/$item"; then
        echo "Migration aborted: backup member missing/corrupt (file $item)" >&2
        exit 67
    fi
    if [ ! -s "$staging/$item" ]; then
        echo "Migration aborted: identity file empty ($item)" >&2
        exit 67
    fi
done
if ! grep -Eq '^[0-9a-fA-F]{16}$' "$staging/serial"; then
    echo "Migration aborted: serial format invalid" >&2
    exit 67
fi
if ! grep -q '^-----BEGIN CERTIFICATE-----$' "$staging/certs/cert.pem" ||
   ! grep -Eq '^-----BEGIN (EC |RSA |)PRIVATE KEY-----$' "$staging/certs/key.pem"; then
    echo "Migration aborted: invalid certificate/key PEM header" >&2
    exit 67
fi

chmod 0600 "$staging/serial" "$staging/certs/cert.pem" "$staging/certs/key.pem"
# /data and the staging directory share a filesystem; moves are atomic.
mv "$staging/certs" "$target/certs"
mv "$staging/serial" "$target/serial"
echo "EEBUS pairing certificate, private key, and serial imported (contents hidden)"
