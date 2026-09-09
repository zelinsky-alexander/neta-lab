# NETA-LAB-015 — Connection Burst and Deduplication

Stress/correlation lab for socket identity, deduplication, phantom TIME_WAIT avoidance and bounded persistence.

Server: `python3 ../../common/server/tcp_lab_server.py --bind 0.0.0.0 --port 18455 --connections 1000 --scenario NETA-LAB-015`

Linux: `./linux/run.sh <LAB-IP> 18455 [count] [parallel]` (defaults 1000/25).

Compare ground-truth count with history rows, unique identities, duplicate rows, lifecycle-loss counters and DB growth. No threat finding is expected unless a distinct burst rule is intentionally enabled.
