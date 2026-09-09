#!/usr/bin/env bash
set -euo pipefail
BIND=${1:-0.0.0.0}; PORT=${2:-18456}; ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
exec python3 "$ROOT/common/server/tcp_lab_server.py" --bind "$BIND" --port "$PORT" --connections 1 --hold-seconds 3 --scenario NETA-LAB-016
