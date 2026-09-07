#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 4 ]]; then
  echo "Usage: $0 <host> [port=18080] [count=12] [interval_seconds=5]" >&2
  exit 2
fi

host="$1"
port="${2:-18080}"
count="${3:-12}"
interval="${4:-5}"
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
url="http://${host}:${port}/beacon"

echo "NETA-LAB-001 run_id=${run_id} target=${url} count=${count} interval=${interval}s"

for ((i=1; i<=count; i++)); do
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[${ts}] request ${i}/${count}"
  curl --silent --show-error --fail \
    --header "X-NETA-Lab-Scenario: NETA-LAB-001" \
    --header "X-NETA-Lab-Run: ${run_id}" \
    --user-agent "NETA-Lab/001" \
    "${url}" >/dev/null
  if (( i < count )); then
    sleep "${interval}"
  fi
done

echo "NETA-LAB-001 complete run_id=${run_id}"
