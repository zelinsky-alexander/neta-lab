#!/usr/bin/env python3
import argparse, json, socket, threading, time
from datetime import datetime, timezone

def ts(): return datetime.now(timezone.utc).isoformat()

def handle(conn, addr, args, seq):
    received=0; started=time.monotonic(); conn.settimeout(args.timeout)
    try:
        while True:
            data=conn.recv(65536)
            if not data: break
            received += len(data)
            if args.echo: conn.sendall(data)
        if args.response_bytes:
            chunk=b'R'*min(65536,args.response_bytes); left=args.response_bytes
            while left:
                n=min(left,len(chunk)); conn.sendall(chunk[:n]); left-=n
        if args.hold_seconds: time.sleep(args.hold_seconds)
    except (socket.timeout, ConnectionResetError, BrokenPipeError): pass
    finally:
        print(json.dumps({'event':'connection','scenario':args.scenario,'seq':seq,'time':ts(),'peer':addr[0],'peer_port':addr[1],'bytes_received':received,'response_bytes':args.response_bytes,'duration_seconds':round(time.monotonic()-started,6)}), flush=True); conn.close()

def main():
    p=argparse.ArgumentParser(description='Bounded NETA TCP lab server')
    p.add_argument('--bind',default='127.0.0.1'); p.add_argument('--port',type=int,default=18440); p.add_argument('--connections',type=int,default=1)
    p.add_argument('--timeout',type=float,default=30); p.add_argument('--hold-seconds',type=float,default=0); p.add_argument('--response-bytes',type=int,default=0)
    p.add_argument('--echo',action='store_true'); p.add_argument('--scenario',default='NETA-LAB'); a=p.parse_args()
    family=socket.AF_INET6 if ':' in a.bind else socket.AF_INET
    with socket.socket(family,socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind((a.bind,a.port)); s.listen(128)
        print(json.dumps({'event':'server_started','scenario':a.scenario,'time':ts(),'bind':a.bind,'port':a.port,'expected_connections':a.connections}), flush=True)
        threads=[]
        for i in range(a.connections):
            c,addr=s.accept(); t=threading.Thread(target=handle,args=(c,addr,a,i+1)); t.start(); threads.append(t)
        for t in threads:t.join()
        print(json.dumps({'event':'server_complete','scenario':a.scenario,'time':ts(),'accepted':a.connections}), flush=True)
if __name__=='__main__': main()
