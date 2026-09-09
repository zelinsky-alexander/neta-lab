# NETA-LAB-010 — Packet Loss / Retransmission Degradation

Linux-only P0 lab using an isolated network namespace/veth pair. A clean connection is followed by the same generated transfer under controlled `tc netem loss`.

Run: `sudo ./linux/run.sh [loss-percent]` (default `5%`).

Expected: retransmission delta and transport degradation; `Performance: DEGRADED`, `Trust: STABLE`. The lab must not claim TLS identity caused the degradation.
