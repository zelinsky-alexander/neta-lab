# NETA-LAB-021 — TLS Stable Identity

Validates repeated exact OpenSSL application TLS sessions to the same hostname and the same certificate/SPKI identity.

Run:

```bash
./linux/run.sh
```

The runner creates a short-lived local CA and hostname-valid server certificate, starts a controlled TLS server, and performs three verified `openssl s_client` sessions with the same SNI/hostname.

Expected after baseline acceptance: `Trust: STABLE`; no `TLS_IDENTITY_CHANGE` finding. Missing exact TLS instrumentation is a capability gap, not a fabricated pass/fail.
