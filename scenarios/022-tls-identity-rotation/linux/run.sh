#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../../.." && pwd); TLS="$ROOT/common/tls/tls_lab.sh"; PORT=${1:-18462}; SCENARIO=${2:-NETA-LAB-022}; TMP=$(mktemp -d)
[[ "$SCENARIO" =~ ^NETA-LAB-[0-9]{3}$ ]] || { echo "invalid scenario label: $SCENARIO" >&2; exit 2; }
cleanup(){ set +e; [[ -n ${CLIENT_PID:-} ]] && kill "$CLIENT_PID" 2>/dev/null; [[ -n ${PID:-} ]] && kill "$PID" 2>/dev/null; rm -rf "$TMP"; }; trap cleanup EXIT INT TERM
"$TLS" prepare "$TMP" neta-lab.local
for ID in A B; do "$TLS" fingerprint "$TMP" "$ID"; done
"$TLS" server "$TMP" A 127.0.0.1 "$PORT" & PID=$!; sleep .3
"$TLS" client "$TMP" 127.0.0.1 "$PORT" neta-lab.local "${NETA_BASELINE_HOLD_SECONDS:-8}" >"$TMP/baseline-client.log" 2>&1 & CLIENT_PID=$!
echo "$SCENARIO phase=baseline identity=A"
"$ROOT/common/linux/accept_observed_baseline.sh" "$PORT" true 127.0.0.1
wait "$CLIENT_PID"; unset CLIENT_PID
kill "$PID"; wait "$PID" 2>/dev/null || true
"$TLS" server "$TMP" B 127.0.0.1 "$PORT" & PID=$!; sleep .3; "$TLS" client "$TMP" 127.0.0.1 "$PORT" neta-lab.local 2 >/dev/null; echo "$SCENARIO phase=validation identity=B"
