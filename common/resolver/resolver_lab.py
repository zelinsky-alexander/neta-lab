#!/usr/bin/env python3
import argparse, json, socket, time

p=argparse.ArgumentParser()
p.add_argument('mode', choices=['resolve-connect','lookup-only','unrelated','ambiguous'])
p.add_argument('--host', default='localhost')
p.add_argument('--port', type=int, default=18459)
p.add_argument('--connect-address', default='127.0.0.1')
p.add_argument('--scenario', required=True)
a=p.parse_args()

def resolve(name):
    t=time.time_ns(); infos=socket.getaddrinfo(name,a.port,type=socket.SOCK_STREAM)
    addrs=[]
    for item in infos:
        x=item[4][0]
        if x not in addrs: addrs.append(x)
    print(json.dumps({'scenario':a.scenario,'event':'resolver_ground_truth','observed_ns':t,'query_name':name,'return_code':0,'addresses':addrs}),flush=True)
    return addrs

def connect(addr):
    t=time.time_ns()
    with socket.create_connection((addr,a.port),timeout=5) as s:
        s.sendall(b'NETA-LAB\n')
    print(json.dumps({'scenario':a.scenario,'event':'connection_ground_truth','observed_ns':t,'address':addr,'port':a.port}),flush=True)

if a.mode=='lookup-only': resolve(a.host)
elif a.mode=='resolve-connect':
    xs=resolve(a.host); connect(a.connect_address if a.connect_address else xs[0])
elif a.mode=='unrelated': resolve(a.host); connect(a.connect_address)
else:
    resolve(a.host); resolve(a.host); connect(a.connect_address)
