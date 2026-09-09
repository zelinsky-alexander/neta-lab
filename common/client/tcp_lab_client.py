#!/usr/bin/env python3
import argparse, json, os, socket, threading, time
from datetime import datetime, timezone

def ts(): return datetime.now(timezone.utc).isoformat()

def one(a, seq):
    sent=received=0; started=time.monotonic()
    family=socket.AF_INET6 if ':' in a.host else socket.AF_INET
    with socket.socket(family,socket.SOCK_STREAM) as s:
        s.settimeout(a.timeout); s.connect((a.host,a.port))
        if a.upload_bytes:
            chunk=b'N'*min(65536,a.upload_bytes); left=a.upload_bytes
            while left:
                n=min(left,len(chunk)); s.sendall(chunk[:n]); sent+=n; left-=n
        if a.hold_seconds: time.sleep(a.hold_seconds)
        try: s.shutdown(socket.SHUT_WR)
        except OSError: pass
        if a.read_response:
            while True:
                d=s.recv(65536)
                if not d: break
                received += len(d)
    print(json.dumps({'event':'client_connection','scenario':a.scenario,'seq':seq,'time':ts(),'pid':os.getpid(),'remote':a.host,'port':a.port,'bytes_sent':sent,'bytes_received':received,'duration_seconds':round(time.monotonic()-started,6)}),flush=True)

def main():
    p=argparse.ArgumentParser(description='Deterministic NETA TCP lab client')
    p.add_argument('host'); p.add_argument('port',type=int); p.add_argument('--connections',type=int,default=1)
    p.add_argument('--parallel',type=int,default=1); p.add_argument('--upload-bytes',type=int,default=0)
    p.add_argument('--hold-seconds',type=float,default=0); p.add_argument('--read-response',action='store_true')
    p.add_argument('--interval-ms',type=int,default=0); p.add_argument('--timeout',type=float,default=30); p.add_argument('--scenario',default='NETA-LAB')
    a=p.parse_args(); next_seq=1
    while next_seq<=a.connections:
        batch=[]
        for _ in range(min(a.parallel,a.connections-next_seq+1)):
            t=threading.Thread(target=one,args=(a,next_seq)); t.start(); batch.append(t); next_seq+=1
        for t in batch:t.join()
        if a.interval_ms and next_seq<=a.connections: time.sleep(a.interval_ms/1000)
if __name__=='__main__': main()
