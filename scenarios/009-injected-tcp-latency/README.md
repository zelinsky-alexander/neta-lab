# NETA-LAB-009 — Injected TCP Latency

Linux-only P0 transport-assurance lab. Uses an isolated network namespace and veth pair, then compares a clean baseline connection with the same traffic under `tc netem delay`. It does not modify the host's normal interface.

Run: `sudo ./linux/run.sh [delay]` (default `100ms`).

Expected: RTT rises materially; process/endpoint stay stable; `Performance: DEGRADED`; no unrelated threat finding.
