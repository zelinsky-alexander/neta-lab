#!/usr/bin/env bash
set -euo pipefail
HOST=${1:?usage: $0 <host> [port] [count] [parallel]}; PORT=${2:-18455}; COUNT=${3:-1000}; PAR=${4:-25}; ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
python3 "$ROOT/common/client/tcp_lab_client.py" "$HOST" "$PORT" --connections "$COUNT" --parallel "$PAR" --scenario NETA-LAB-015
