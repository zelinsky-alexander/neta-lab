#!/usr/bin/env bash
set -euo pipefail
MODE=${1:?usage: $0 <latency|loss> [value] [port]}; VALUE=${2:-100ms}; PORT=${3:-18448}
case "$MODE" in latency|loss) ;; *) echo "mode must be latency or loss" >&2; exit 2;; esac
command -v ip >/dev/null; command -v tc >/dev/null; command -v python3 >/dev/null
[[ $EUID -eq 0 ]] || { echo "run as root; this creates an isolated network namespace" >&2; exit 1; }
SUFFIX=$$; NS=neta-lab-$SUFFIX; VH=neta-vh-$SUFFIX; VN=neta-vn-$SUFFIX
cleanup(){ set +e; [[ -n ${SERVER_PID:-} ]] && kill "$SERVER_PID" 2>/dev/null; ip netns del "$NS" 2>/dev/null; }
trap cleanup EXIT INT TERM
ip netns add "$NS"; ip link add "$VH" type veth peer name "$VN"; ip link set "$VN" netns "$NS"
ip addr add 10.203.0.1/30 dev "$VH"; ip link set "$VH" up
ip netns exec "$NS" ip addr add 10.203.0.2/30 dev "$VN"; ip netns exec "$NS" ip link set lo up; ip netns exec "$NS" ip link set "$VN" up
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
ip netns exec "$NS" python3 "$ROOT/common/server/tcp_lab_server.py" --bind 10.203.0.2 --port "$PORT" --connections 2 --scenario "NETA-LAB-netem-$MODE" & SERVER_PID=$!
sleep .3
python3 "$ROOT/common/client/tcp_lab_client.py" 10.203.0.2 "$PORT" --connections 1 --upload-bytes 8388608 --hold-seconds 2 --scenario "NETA-LAB-netem-$MODE-baseline"
if [[ $MODE == latency ]]; then tc qdisc add dev "$VH" root netem delay "$VALUE"; else tc qdisc add dev "$VH" root netem loss "$VALUE"; fi
python3 "$ROOT/common/client/tcp_lab_client.py" 10.203.0.2 "$PORT" --connections 1 --upload-bytes 8388608 --hold-seconds 2 --scenario "NETA-LAB-netem-$MODE-impaired"
wait "$SERVER_PID"
