# NETA-LAB-031 — TLS Evidence Fidelity Comparison

Ensures NETA preserves the distinction between exact application TLS-session evidence and a separate supporting TLS probe.

Run:

```bash
bash ./linux/run.sh
```

The runner always creates one verified `openssl s_client` application session. To include the supporting-probe phase, set `NETA_SUPPORTING_TLS_PROBE_CMD` to the current NETA command that performs the independent supporting TLS probe against `127.0.0.1:<port>`.

Example shape only:

```bash
NETA_SUPPORTING_TLS_PROBE_CMD='<current neta-agent supporting-probe command>' bash ./linux/run.sh
```

If that variable is absent, the scenario reports the supporting phase as a capability/test-configuration gap rather than pretending it ran.

Required invariant: supporting probe evidence must never be labeled as exact application-session identity.
