# NETA-LAB-024 — TLS Identity Change Only

Inverse independence test for LAB-023. The network remains healthy while the server identity rotates from certificate/SPKI A to B on the same hostname and port.

Run:

```bash
./linux/run.sh
```

Expected: `Performance: NORMAL`, `Trust: CHANGED`, and `TLS_IDENTITY_CHANGE`. A trust change alone must not create a transport-degradation verdict.
