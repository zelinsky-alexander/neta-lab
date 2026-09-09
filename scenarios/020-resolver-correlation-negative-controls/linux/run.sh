#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../../.." && pwd)
python3 "$ROOT/common/resolver/resolver_lab.py" lookup-only --host localhost --port 18460 --scenario NETA-LAB-020-A
python3 "$ROOT/common/server/tcp_lab_server.py" --bind 127.0.0.2 --port 18460 --connections 1 --scenario NETA-LAB-020-B & P1=$!; sleep .2
python3 "$ROOT/common/resolver/resolver_lab.py" unrelated --host localhost --connect-address 127.0.0.2 --port 18460 --scenario NETA-LAB-020-B
wait "$P1"
python3 "$ROOT/common/server/tcp_lab_server.py" --bind 127.0.0.1 --port 18460 --connections 1 --scenario NETA-LAB-020-C & P2=$!; sleep .2
python3 "$ROOT/common/resolver/resolver_lab.py" ambiguous --host localhost --connect-address 127.0.0.1 --port 18460 --scenario NETA-LAB-020-C
wait "$P2"
