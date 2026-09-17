#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../../.." && pwd); TLS="$ROOT/common/tls/tls_lab.sh"; PORT=${1:-18461}; TMP=$(mktemp -d)
cleanup(){ set +e; [[ -n ${CLIENT_PID:-} ]] && kill "$CLIENT_PID" 2>/dev/null; [[ -n ${PID:-} ]] && kill "$PID" 2>/dev/null; rm -rf "$TMP"; }; trap cleanup EXIT INT TERM
"$TLS" prepare "$TMP" neta-lab.local
"$TLS" fingerprint "$TMP" A
"$TLS" server "$TMP" A 127.0.0.1 "$PORT" & PID=$!; sleep .3
"$TLS" client "$TMP" 127.0.0.1 "$PORT" neta-lab.local "${NETA_BASELINE_HOLD_SECONDS:-8}" >"$TMP/baseline-client.log" 2>&1 & CLIENT_PID=$!
echo 'NETA-LAB-021 phase=baseline identity=A'
"$ROOT/common/linux/accept_observed_baseline.sh" "$PORT" true 127.0.0.1
wait "$CLIENT_PID"; unset CLIENT_PID
for i in 1 2; do "$TLS" client "$TMP" 127.0.0.1 "$PORT" neta-lab.local 2 >/dev/null; echo "NETA-LAB-021 phase=validation session=$i identity=A"; done
