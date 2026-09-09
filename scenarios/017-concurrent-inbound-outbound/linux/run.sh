#!/usr/bin/env bash
set -euo pipefail
OUT=${1:?usage: $0 <outbound-server-ip> [out-port] [in-port]}; OP=${2:-18457}; IP=${3:-18458}; ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
python3 "$ROOT/common/server/tcp_lab_server.py" --bind 0.0.0.0 --port "$IP" --connections 1 --hold-seconds 2 --scenario NETA-LAB-017-inbound & SP=$!
trap 'kill $SP 2>/dev/null || true' EXIT
echo "NETA-LAB-017 inbound listener ready on port $IP; connect once from another owned host"
python3 "$ROOT/common/client/tcp_lab_client.py" "$OUT" "$OP" --connections 1 --upload-bytes 1048576 --hold-seconds 2 --scenario NETA-LAB-017-outbound
wait "$SP"
