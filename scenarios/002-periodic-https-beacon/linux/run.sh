#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 4 ]]; then
  echo "Usage: $0 <host> [port=18443] [count=12] [interval_seconds=5]" >&2
  exit 2
fi

host="$1"
port="${2:-18443}"
count="${3:-12}"
interval="${4:-5}"
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
url="https://${host}:${port}/beacon"

echo "NETA-LAB-002 run_id=${run_id} target=${url} count=${count} interval=${interval}s"
echo "WARNING: TLS certificate verification is disabled for this controlled lab scenario."

for ((i=1; i<=count; i++)); do
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[${ts}] request ${i}/${count}"
  curl --silent --show-error --fail --insecure \
    --header "X-NETA-Lab-Scenario: NETA-LAB-002" \
    --header "X-NETA-Lab-Run: ${run_id}" \
    --user-agent "NETA-Lab/002" \
    "${url}" >/dev/null
  if (( i < count )); then
    sleep "${interval}"
  fi
done

echo "NETA-LAB-002 complete run_id=${run_id}"
