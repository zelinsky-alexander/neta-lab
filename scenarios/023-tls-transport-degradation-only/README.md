# NETA-LAB-023 — TLS Transport Degradation Only

Validates that transport degradation and TLS trust remain independent.

Run as root:

```bash
sudo ./linux/run.sh
```

The runner creates an isolated Linux network namespace/veth pair, serves one hostname-valid TLS identity A, records a healthy baseline connection, then applies `tc netem delay 120ms loss 1%` only to the temporary veth and reconnects with the same certificate/SPKI.

Expected: `Performance: DEGRADED`, `Trust: STABLE`, and no `TLS_IDENTITY_CHANGE` finding.
