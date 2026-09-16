#!/usr/bin/env bash
set -euo pipefail

PORT=${1:?usage: $0 <remote-port> [require-exact-tls]}
REQUIRE_EXACT_TLS=${2:-false}
AGENT_BIN=${NETA_AGENT_BIN:-}
AGENT_DB=${NETA_AGENT_DB:-}

if [[ -z "$AGENT_BIN" || -z "$AGENT_DB" ]]; then
  echo "baseline acceptance not requested: NETA_AGENT_BIN/NETA_AGENT_DB are unset"
  exit 0
fi
[[ -x "$AGENT_BIN" ]] || { echo "NETA_AGENT_BIN is not executable: $AGENT_BIN" >&2; exit 2; }
[[ -f "$AGENT_DB" ]] || { echo "NETA_AGENT_DB does not exist: $AGENT_DB" >&2; exit 2; }

CONNECTION_ID=$(python3 - "$AGENT_DB" "$PORT" "$REQUIRE_EXACT_TLS" <<'PY'
import sqlite3, sys, time

database, port, require_tls = sys.argv[1], int(sys.argv[2]), sys.argv[3].lower() == "true"
deadline = time.monotonic() + 15
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
while time.monotonic() < deadline:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        row = connection.execute(query, (port, int(require_tls))).fetchone()
    if row:
        print(row[0])
        raise SystemExit(0)
    time.sleep(0.25)
raise SystemExit(f"timed out waiting for observed baseline connection on port {port}")
PY
)

"$AGENT_BIN" baseline accept-connection "$CONNECTION_ID" --db "$AGENT_DB"
