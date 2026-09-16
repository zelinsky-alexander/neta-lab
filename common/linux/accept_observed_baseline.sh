#!/usr/bin/env bash
set -euo pipefail

PORT=${1:?usage: $0 <remote-port> [require-exact-tls]}
REQUIRE_EXACT_TLS=${2:-false}
AGENT_BIN=${NETA_AGENT_BIN:-}
AGENT_DB=${NETA_AGENT_DB:-}
TIMEOUT_SECONDS=${NETA_BASELINE_ACCEPT_TIMEOUT_SECONDS:-30}

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
while (( SECONDS - START_SECONDS < TIMEOUT_SECONDS )); do
  CONNECTION_ID=$(python3 - "$AGENT_DB" "$PORT" "$REQUIRE_EXACT_TLS" <<'PY'
import sqlite3
import sys

database, port, require_tls = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "true"
query = """
SELECT c.id
  FROM connections c
 WHERE c.remote_port=? AND c.direction='OUTBOUND'
   AND EXISTS (
       SELECT 1 FROM transport_samples s
        WHERE s.connection_id=c.id AND s.rtt_us>0)
   AND (?=0 OR EXISTS (
       SELECT 1 FROM connection_tls_session_evidence t
        WHERE t.connection_id=c.id
          AND t.correlation_fidelity='EXACT'
          AND t.observation_fidelity='EXACT'))
 ORDER BY c.id DESC LIMIT 1
"""
with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
    row = connection.execute(query, (port, int(require_tls))).fetchone()
if row:
    print(row[0])
PY
)

  if [[ -n "$CONNECTION_ID" ]]; then
    LAST_CONNECTION_ID=$CONNECTION_ID
    if ACCEPT_OUTPUT=$("$AGENT_BIN" baseline accept-connection "$CONNECTION_ID" --db "$AGENT_DB" 2>&1); then
      [[ -n "$ACCEPT_OUTPUT" ]] && printf '%s\n' "$ACCEPT_OUTPUT"
      exit 0
    fi
    LAST_ERROR=$ACCEPT_OUTPUT
  fi
  sleep 0.25
done

if [[ -n "$LAST_CONNECTION_ID" ]]; then
  echo "timed out accepting observed baseline connection $LAST_CONNECTION_ID on port $PORT" >&2
  [[ -n "$LAST_ERROR" ]] && printf 'last baseline rejection: %s\n' "$LAST_ERROR" >&2
else
  echo "timed out waiting for observed baseline connection on port $PORT" >&2
fi
exit 1
