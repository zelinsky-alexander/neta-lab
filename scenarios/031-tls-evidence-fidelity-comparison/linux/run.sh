#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../../.." && pwd); TLS="$ROOT/common/tls/tls_lab.sh"; PORT=${1:-18471}; TMP=$(mktemp -d)
cleanup(){ set +e; [[ -n ${PID:-} ]] && kill "$PID" 2>/dev/null; rm -rf "$TMP"; }; trap cleanup EXIT INT TERM
"$TLS" prepare "$TMP" neta-lab.local
"$TLS" server "$TMP" A 127.0.0.1 "$PORT" & PID=$!; sleep .3
"$TLS" client "$TMP" 127.0.0.1 "$PORT" neta-lab.local >/dev/null
echo 'NETA-LAB-031 phase=exact_application_session source=openssl'
if [[ -n ${NETA_SUPPORTING_TLS_PROBE_CMD:-} ]]; then
  NETA_LAB_HOST=127.0.0.1 NETA_LAB_PORT="$PORT" NETA_LAB_CA="$TMP/ca.pem" bash -lc "$NETA_SUPPORTING_TLS_PROBE_CMD"
  echo 'NETA-LAB-031 phase=supporting_probe executed=true'
else
  echo 'NETA-LAB-031 phase=supporting_probe executed=false capability_gap=NETA_SUPPORTING_TLS_PROBE_CMD_not_set'
fi
