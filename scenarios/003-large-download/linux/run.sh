#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "Usage: $0 <host> [port=18080] [size_mib=50]" >&2
  exit 2
fi

host="$1"
port="${2:-18080}"
size_mib="${3:-50}"
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
url="http://${host}:${port}/large-download?size_mib=${size_mib}"
tmp="$(mktemp -t neta-lab-003-XXXXXX.bin)"
trap 'rm -f "$tmp"' EXIT

expected_bytes=$((size_mib * 1024 * 1024))

echo "NETA-LAB-003 run_id=${run_id} target=${url} expected_bytes=${expected_bytes}"

curl --silent --show-error --fail \
  --header "X-NETA-Lab-Scenario: NETA-LAB-003" \
  --header "X-NETA-Lab-Run: ${run_id}" \
  --user-agent "NETA-Lab/003" \
  --output "$tmp" \
  "$url"

actual_bytes="$(wc -c < "$tmp" | tr -d '[:space:]')"
if [[ "$actual_bytes" != "$expected_bytes" ]]; then
  echo "NETA-LAB-003 FAIL: expected ${expected_bytes} bytes, got ${actual_bytes}" >&2
  exit 1
fi

echo "NETA-LAB-003 complete run_id=${run_id} bytes=${actual_bytes}"
