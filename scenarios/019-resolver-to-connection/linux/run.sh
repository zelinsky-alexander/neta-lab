#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../../.." && pwd); PORT=${1:-18459}
python3 "$ROOT/common/server/tcp_lab_server.py" --bind 127.0.0.1 --port "$PORT" --connections 1 --scenario NETA-LAB-019 & PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
sleep .2
python3 "$ROOT/common/resolver/resolver_lab.py" resolve-connect --host localhost --connect-address 127.0.0.1 --port "$PORT" --scenario NETA-LAB-019
wait "$PID"; trap - EXIT
