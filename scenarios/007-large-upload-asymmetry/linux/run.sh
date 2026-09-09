#!/usr/bin/env bash
set -euo pipefail
HOST=${1:?usage: $0 <host> [port]}; PORT=${2:-18447}; ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
python3 "$ROOT/common/client/tcp_lab_client.py" "$HOST" "$PORT" --connections 1 --upload-bytes 33554432 --scenario NETA-LAB-007
