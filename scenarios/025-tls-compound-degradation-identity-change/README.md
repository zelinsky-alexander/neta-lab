# NETA-LAB-025 — Compound TLS Identity Change + Network Degradation

Validates simultaneous but independent transport and trust changes.

Run as root:

```bash
sudo ./linux/run.sh
```

The runner creates an isolated netns/veth lab, records a healthy TLS session with identity A, applies `tc netem delay 120ms loss 1%`, rotates the controlled server to identity B, then reconnects.

Expected: `Performance: DEGRADED`, `Trust: CHANGED`, and `TLS_IDENTITY_CHANGE`. NETA may report the changes as contemporaneous/correlated but must not claim the certificate change caused the transport degradation.
