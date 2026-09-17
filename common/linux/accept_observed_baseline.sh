#!/usr/bin/env bash
set -euo pipefail

PORT=${1:?usage: $0 <remote-port> [require-exact-tls] [remote-address]}
REQUIRE_EXACT_TLS=${2:-false}
REMOTE_ADDRESS=${3:-}
AGENT_BIN=${NETA_AGENT_BIN:-}
AGENT_DB=${NETA_AGENT_DB:-}
TIMEOUT_SECONDS=${NETA_BASELINE_ACCEPT_TIMEOUT_SECONDS:-30}
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

if [[ -z "$AGENT_BIN" || -z "$AGENT_DB" ]]; then
  echo "baseline acceptance not requested: NETA_AGENT_BIN/NETA_AGENT_DB are unset"
  exit 0
fi
[[ -x "$AGENT_BIN" ]] || { echo "NETA_AGENT_BIN is not executable: $AGENT_BIN" >&2; exit 2; }
[[ -f "$AGENT_DB" ]] || { echo "NETA_AGENT_DB does not exist: $AGENT_DB" >&2; exit 2; }
[[ "$REQUIRE_EXACT_TLS" == "true" || "$REQUIRE_EXACT_TLS" == "false" ]] || {
  echo "require-exact-tls must be true or false" >&2
  exit 2
}
[[ "$TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]] || {
  echo "NETA_BASELINE_ACCEPT_TIMEOUT_SECONDS must be a positive whole number" >&2
  exit 2
}

START_SECONDS=$SECONDS
LAST_ERROR=""
LAST_CONNECTION_ID=""
LAST_TARGET="${REMOTE_ADDRESS:-<unresolved>}:$PORT"
LAST_RTT_SAMPLES=0
LAST_EXACT_TLS=false
while (( SECONDS - START_SECONDS < TIMEOUT_SECONDS )); do
  READINESS=()
  mapfile -t READINESS < <(
    python3 "$SCRIPT_DIR/baseline_readiness.py" \
      "$AGENT_DB" "$PORT" "$REQUIRE_EXACT_TLS" "$REMOTE_ADDRESS" || true
  )
  CONNECTION_ID=${READINESS[0]:-}
  LAST_TARGET=${READINESS[1]:-$LAST_TARGET}
  LAST_RTT_SAMPLES=${READINESS[2]:-0}
  LAST_EXACT_TLS=${READINESS[3]:-false}
  [[ -n "$CONNECTION_ID" ]] && LAST_CONNECTION_ID=$CONNECTION_ID

  if [[ -n "$CONNECTION_ID" && "$LAST_RTT_SAMPLES" -ge 5 && \
        ( "$REQUIRE_EXACT_TLS" == "false" || "$LAST_EXACT_TLS" == "true" ) ]]; then
    if ACCEPT_OUTPUT=$("$AGENT_BIN" baseline accept-connection "$CONNECTION_ID" --db "$AGENT_DB" 2>&1); then
      [[ -n "$ACCEPT_OUTPUT" ]] && printf '%s\n' "$ACCEPT_OUTPUT"
      exit 0
    fi
    LAST_ERROR=$ACCEPT_OUTPUT
  fi
  sleep 0.25
done

if [[ -n "$LAST_CONNECTION_ID" ]]; then
  echo "timed out accepting observed baseline connection $LAST_CONNECTION_ID target=$LAST_TARGET rtt_samples=$LAST_RTT_SAMPLES exact_tls=$LAST_EXACT_TLS" >&2
  [[ -n "$LAST_ERROR" ]] && printf 'last baseline rejection: %s\n' "$LAST_ERROR" >&2
else
  echo "timed out waiting for observed baseline connection target=$LAST_TARGET rtt_samples=$LAST_RTT_SAMPLES exact_tls=$LAST_EXACT_TLS" >&2
fi
exit 1
