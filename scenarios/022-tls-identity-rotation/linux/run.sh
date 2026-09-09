#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../../.." && pwd); TLS="$ROOT/common/tls/tls_lab.sh"; PORT=${1:-18462}; TMP=$(mktemp -d)
cleanup(){ set +e; [[ -n ${PID:-} ]] && kill "$PID" 2>/dev/null; rm -rf "$TMP"; }; trap cleanup EXIT INT TERM
"$TLS" prepare "$TMP" neta-lab.local
for ID in A B; do "$TLS" fingerprint "$TMP" "$ID"; done
"$TLS" server "$TMP" A 127.0.0.1 "$PORT" & PID=$!; sleep .3; "$TLS" client "$TMP" 127.0.0.1 "$PORT" neta-lab.local >/dev/null; echo 'NETA-LAB-022 identity=A'
kill "$PID"; wait "$PID" 2>/dev/null || true
"$TLS" server "$TMP" B 127.0.0.1 "$PORT" & PID=$!; sleep .3; "$TLS" client "$TMP" 127.0.0.1 "$PORT" neta-lab.local >/dev/null; echo 'NETA-LAB-022 identity=B'
