# NETA-LAB-022 — TLS Certificate / SPKI Rotation

Validates deterministic TLS identity change on the same hostname, port and otherwise healthy transport.

Run `./linux/run.sh`.

The runner creates one local CA and two separately generated hostname-valid leaf certificates A/B. It connects once to A, restarts the controlled server on the same endpoint with B, then reconnects.

Expected: `Performance: NORMAL`, `Trust: CHANGED`, finding `TLS_IDENTITY_CHANGE`. The two leaf/SPKI hashes are printed as independent ground truth.
