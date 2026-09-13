#!/usr/bin/env bash
set -euo pipefail

HOST="${1:?usage: run.sh <lab-host> [port]}"
PORT="${2:-18580}"
RUN_ID="linux-$(date -u +%Y%m%dT%H%M%SZ)-$$"
TMP="$(mktemp -d -t neta-lab-005-XXXXXX)"
STAGE="$TMP/stage.txt"
ENCODED="$TMP/stage.b64"
DECODED="$TMP/stage.decoded.txt"
BASE_URL="http://${HOST}:${PORT}"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT INT TERM

for tool in curl base64 sha256sum; do command -v "$tool" >/dev/null || { echo "required tool missing: $tool" >&2; exit 2; }; done

package_provenance() {
  local tool_path="$1" canonical package
  canonical="$(readlink -f "$tool_path" 2>/dev/null || printf '%s' "$tool_path")"
  if command -v dpkg-query >/dev/null 2>&1; then
    package="$(dpkg-query -S "$canonical" 2>/dev/null | head -n1 | cut -d: -f1 || true)"
    if [[ -n "$package" ]]; then
      dpkg-query -W -f='manager=dpkg package=${Package} version=${Version} status=${db:Status-Abbrev}\n' "$package" 2>/dev/null || true
      return
    fi
  fi
  if command -v rpm >/dev/null 2>&1; then
    rpm -qf --qf 'manager=rpm package=%{NAME} version=%{VERSION}-%{RELEASE}\n' "$canonical" 2>/dev/null && return
  fi
  printf 'manager=unknown package=unavailable path=%s\n' "$canonical"
}

CURL_PATH="$(command -v curl)"
BASE64_PATH="$(command -v base64)"
printf 'scenario=NETA-LAB-005\nrun_id=%s\ncurl_path=%s\ncurl_provenance=' "$RUN_ID" "$CURL_PATH"
package_provenance "$CURL_PATH"
printf 'base64_path=%s\nbase64_provenance=' "$BASE64_PATH"
package_provenance "$BASE64_PATH"

curl --fail --silent --show-error --retry 2 --connect-timeout 5 \
  -H "X-NETA-Lab-Run: $RUN_ID" -o "$STAGE" "${BASE_URL}/stage.txt?run_id=${RUN_ID}"
base64 "$STAGE" >"$ENCODED"
base64 --decode "$ENCODED" >"$DECODED"

ORIGINAL_SHA256="$(sha256sum "$STAGE" | awk '{print $1}')"
DECODED_SHA256="$(sha256sum "$DECODED" | awk '{print $1}')"
[[ "$ORIGINAL_SHA256" == "$DECODED_SHA256" ]] || { echo "encode/decode hash mismatch" >&2; exit 1; }

curl --fail --silent --show-error --retry 2 --connect-timeout 5 \
  -H "X-NETA-Lab-Run: $RUN_ID" "${BASE_URL}/callback?run_id=${RUN_ID}" >/dev/null

printf 'stage_sha256=%s\ndecoded_sha256=%s\nNETA-LAB-005 Linux staging chain complete\n' \
  "$ORIGINAL_SHA256" "$DECODED_SHA256"
