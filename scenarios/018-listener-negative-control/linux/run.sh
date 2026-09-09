#!/usr/bin/env bash
set -euo pipefail
BIND=${1:-0.0.0.0}; PORT=${2:-18458}; IDLE=${3:-15}
echo "NETA-LAB-018 idle listener phase: ${IDLE}s on $BIND:$PORT"
python3 - "$BIND" "$PORT" "$IDLE" <<'PY'
import socket,sys,time,json,os
bind=sys.argv[1]; port=int(sys.argv[2]); idle=float(sys.argv[3]); fam=socket.AF_INET6 if ':' in bind else socket.AF_INET
s=socket.socket(fam,socket.SOCK_STREAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind((bind,port)); s.listen(8)
print(json.dumps({'event':'listener_idle','scenario':'NETA-LAB-018','pid':os.getpid(),'bind':bind,'port':port,'idle_seconds':idle}),flush=True); time.sleep(idle)
print(json.dumps({'event':'listener_accept_phase','scenario':'NETA-LAB-018'}),flush=True); c,a=s.accept(); print(json.dumps({'event':'accepted','scenario':'NETA-LAB-018','peer':a[0],'peer_port':a[1]}),flush=True); c.close(); s.close()
PY
