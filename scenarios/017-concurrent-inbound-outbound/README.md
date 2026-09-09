# NETA-LAB-017 — Concurrent Inbound + Outbound

Validates real `--all` semantics by producing one outbound connection and one inbound accepted connection concurrently.

On the observed Linux endpoint run `./linux/run.sh <OUTBOUND-SERVER-IP> [out-port] [in-port]`; while it waits, connect once from another owned host to the printed inbound port.

Required: correct client/server process attribution, OUTBOUND and INBOUND direction respectively, no listener history row, bounded persistence, and no threat finding by default.
