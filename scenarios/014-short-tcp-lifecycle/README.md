# NETA-LAB-014 — Very Short TCP Lifecycle Coverage

Capability/regression lab for event-driven connect/close visibility below polling intervals.

Server: `python3 ../../common/server/tcp_lab_server.py --bind 0.0.0.0 --port 18454 --connections 100 --scenario NETA-LAB-014`

Linux: `./linux/run.sh <LAB-IP> 18454 [count]` (default 100).

Ground truth is the exact client connection count. Required evidence: connect/close events, process attribution, exact outbound direction and lifecycle loss accounting. Expected threat finding: none.
