# NETA-LAB-016 — Inbound TCP Accepted Connection

Validates true inbound assurance: accepted socket, INBOUND direction, owning server process, remote peer and TCP evidence. A listener alone must not become an ordinary connection-history object.

On the observed endpoint: `./linux/run-server.sh [bind] [port]` (default `0.0.0.0:18456`).

From another owned lab host: `python3 common/client/tcp_lab_client.py <SERVER-IP> 18456 --connections 1 --upload-bytes 1048576 --scenario NETA-LAB-016-client`.

Expected threat finding: none; inbound is not suspicious merely because it is inbound.
