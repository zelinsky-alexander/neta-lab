#!/usr/bin/env bash
set -euo pipefail

CALLBACK_URL="${1:?callback URL required}"
RUN_ID="${2:?run id required}"
CA_CERT="${3:-}"

curl_args=(--fail --silent --show-error --retry 2 --connect-timeout 5)
if [[ -n "$CA_CERT" ]]; then
  [[ -r "$CA_CERT" ]] || { echo "payload CA certificate is not readable: $CA_CERT" >&2; exit 2; }
  curl_args+=(--cacert "$CA_CERT")
elif [[ "${NETA_LAB_TLS_INSECURE:-0}" == "1" ]]; then
  curl_args+=(--insecure)
else
  echo "payload requires CA certificate" >&2
  exit 2
fi

curl "${curl_args[@]}" -H "X-NETA-Lab-Run: $RUN_ID" "${CALLBACK_URL}?run_id=${RUN_ID}" >/dev/null
printf 'NETA-LAB-004 payload callback complete run_id=%s\n' "$RUN_ID"
