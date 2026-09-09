# Wave C — Resolver and TLS Identity

Implemented scenarios:

- NETA-LAB-019 resolver-to-connection correlation
- NETA-LAB-020 resolver false-correlation controls
- NETA-LAB-021 stable TLS identity
- NETA-LAB-022 TLS certificate/SPKI rotation
- NETA-LAB-023 TLS transport degradation only
- NETA-LAB-024 TLS identity change only
- NETA-LAB-025 compound transport degradation + TLS identity change
- NETA-LAB-031 exact/supporting TLS fidelity comparison

Core invariants:

1. `getaddrinfo()` is application resolver evidence, not proof of an exact DNS packet transaction.
2. Temporal proximity alone must not create resolver-to-connection attribution.
3. Exact OpenSSL application-session evidence and supporting independent TLS probes retain distinct provenance/fidelity.
4. Transport performance and TLS trust are independent verdict dimensions.
5. Compound observations may be correlated without asserting causality.
6. Missing instrumentation is a capability gap, never fabricated evidence.

TLS lab certificates are generated locally at run time from a short-lived lab CA. No private keys or generated certificates are committed.
