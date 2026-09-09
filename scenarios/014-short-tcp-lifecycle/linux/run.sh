#!/usr/bin/env bash
set -euo pipefail
HOST=${1:?usage: $0 <host> [port] [count]}; PORT=${2:-18454}; COUNT=${3:-100}; ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
python3 "$ROOT/common/client/tcp_lab_client.py" "$HOST" "$PORT" --connections "$COUNT" --parallel 1 --scenario NETA-LAB-014
