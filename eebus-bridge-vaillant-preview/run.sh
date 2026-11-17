#!/usr/bin/with-contenv bashio
# Experimental bridge: never silently generate a new SHIP identity.
set -euo pipefail
umask 077
CONFIG_FILE="/etc/eebus-bridge/config.yaml"
SERIAL_FILE="/data/serial"
CERT_STORAGE="/data/certs"
backup_slug="$(bashio::config 'migration_backup_slug')"

if [ ! -s "$SERIAL_FILE" ] || [ ! -s "$CERT_STORAGE/cert.pem" ] || [ ! -s "$CERT_STORAGE/key.pem" ]; then
    if [[ ! "$backup_slug" =~ ^[0-9a-fA-F]{8}$ ]]; then
        bashio::log.fatal "Pairing identity missing; configure an 8-hex local migration_backup_slug (no keys in options)"
        exit 70
    fi
    /usr/local/bin/import-eebus-identity "/backup/${backup_slug}.tar" "/data"
fi
for file in "$SERIAL_FILE" "$CERT_STORAGE/cert.pem" "$CERT_STORAGE/key.pem"; do
    if [ ! -s "$file" ]; then
        bashio::log.fatal "Identity incomplete; refusing to start and regenerate EEBUS identity"
        exit 70
    fi
done

export EEBUS_GRPC_PORT="$(bashio::config 'grpc_port')"
export EEBUS_PORT="$(bashio::config 'eebus_port')"
export EEBUS_VENDOR="$(bashio::config 'vendor')"
export EEBUS_BRAND="$(bashio::config 'brand')"
export EEBUS_MODEL="$(bashio::config 'model')"
export EEBUS_CERT_STORAGE="$CERT_STORAGE"
export EEBUS_SERIAL="$(cat "$SERIAL_FILE")"

if bashio::config.true 'debug_events'; then
    export EEBUS_DEBUG_EVENTS="true"
    bashio::log.warning "SPINE discovery diagnostics enabled; redact logs before sharing"
fi
if bashio::config.true 'ship_log'; then
    export EEBUS_SHIP_LOG="true"
    bashio::log.warning "SHIP connection diagnostics enabled; redact logs before sharing"
fi

mkdir -p "$(dirname "$CONFIG_FILE")"
cat > "$CONFIG_FILE" <<'EOF'
certificates:
  auto_generate: false
EOF
bashio::log.info "Starting signed Vaillant EEBUS preview with preserved pairing identity"
exec /usr/local/bin/eebus-bridge --config "$CONFIG_FILE"
