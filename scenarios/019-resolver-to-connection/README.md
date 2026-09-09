# NETA-LAB-019 — Resolver-to-Connection Correlation

Validates exact application resolver observation plus bounded correlation to a subsequent outbound connection. The lab uses `getaddrinfo()` ground truth and intentionally does **not** claim an exact DNS packet transaction.

## Run

```bash
./linux/run.sh
```

The default uses `localhost` and a controlled loopback TCP server so no host DNS configuration is required.

## Expected

- resolver query name, return code and resolved address set;
- resolver process/source/fidelity;
- outbound connection lifecycle and process attribution;
- relation `RESOLVED_ADDRESS_FOR_OUTBOUND_CONNECTION` when correlation is justified;
- no security finding by default.

Ground-truth timestamps and scenario IDs are validation-only and must not be used by detection/correlation logic.
