#!/usr/bin/env bash
set -euo pipefail
MODE=${1:?usage: $0 <degradation|compound> <scenario> [port]}; SCENARIO=${2:?scenario}; PORT=${3:-18463}
[[ $MODE == degradation || $MODE == compound ]] || { echo "mode must be degradation or compound" >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo "run as root; isolated netns required" >&2; exit 1; }
command -v ip >/dev/null; command -v tc >/dev/null; command -v openssl >/dev/null
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../.." && pwd); TLS="$ROOT/common/tls/tls_lab.sh"; TMP=$(mktemp -d)
SUFFIX=$$; NS=neta-tls-$SUFFIX; VH=neta-th-$SUFFIX; VN=neta-tn-$SUFFIX
cleanup(){ set +e; [[ -n ${PID:-} ]] && kill "$PID" 2>/dev/null; ip netns del "$NS" 2>/dev/null; rm -rf "$TMP"; }; trap cleanup EXIT INT TERM
"$TLS" prepare "$TMP" neta-lab.local
ip netns add "$NS"; ip link add "$VH" type veth peer name "$VN"; ip link set "$VN" netns "$NS"
ip addr add 10.204.0.1/30 dev "$VH"; ip link set "$VH" up
ip netns exec "$NS" ip addr add 10.204.0.2/30 dev "$VN"; ip netns exec "$NS" ip link set lo up; ip netns exec "$NS" ip link set "$VN" up
ip netns exec "$NS" "$TLS" server "$TMP" A 10.204.0.2 "$PORT" & PID=$!; sleep .3
"$TLS" fingerprint "$TMP" A; "$TLS" client "$TMP" 10.204.0.2 "$PORT" neta-lab.local >/dev/null; echo "$SCENARIO phase=baseline identity=A"
tc qdisc add dev "$VH" root netem delay 120ms loss 1%
if [[ $MODE == compound ]]; then kill "$PID"; wait "$PID" 2>/dev/null || true; ip netns exec "$NS" "$TLS" server "$TMP" B 10.204.0.2 "$PORT" & PID=$!; sleep .3; "$TLS" fingerprint "$TMP" B; ID=B; else ID=A; fi
"$TLS" client "$TMP" 10.204.0.2 "$PORT" neta-lab.local >/dev/null; echo "$SCENARIO phase=impaired identity=$ID delay=120ms loss=1%"
