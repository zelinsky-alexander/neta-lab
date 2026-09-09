#!/usr/bin/env bash
set -euo pipefail
HOST=${1:?usage: $0 <host> [port]}; PORT=${2:-18448}; ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
python3 "$ROOT/common/client/tcp_lab_client.py" "$HOST" "$PORT" --connections 5 --upload-bytes 1048576 --hold-seconds 3 --interval-ms 500 --scenario NETA-LAB-008
