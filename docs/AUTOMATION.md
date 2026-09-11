# NETA Lab automation

`automation/run-linux-suite.sh` is the non-interactive command runner used by the NETA full-cycle acceptance harness. Existing scenario scripts remain the canonical scenario implementations and continue to support manual debugging.

Examples:

```bash
bash automation/run-linux-suite.sh --list
bash automation/run-linux-suite.sh --target-host 10.0.1.20 --scenarios all --output-dir /tmp/neta-lab-results
bash automation/run-linux-suite.sh --target-host 10.0.1.20 --scenarios 001,002,003,008
```

The runner writes `summary.tsv`, `summary.json`, per-scenario logs, and copies each available `expected.yaml` beside its result. A non-zero scenario command or a missing required controlled target makes the runner fail.

Linux scenarios with their own local network namespace/TLS/resolver setup run directly. Scenarios that need a controlled outbound target receive `--target-host`. Windows-only scenarios 004-006 are reported as `NOT_APPLICABLE` in a Linux run.

NETA-LAB-016, NETA-LAB-017, and the connected phase of NETA-LAB-018 require a second owned host. The local runner reports them as `PEER_REQUIRED`; `neta-coordinator/integration/aws/full-cycle.sh` supplies that peer and records a separate peer summary. For 018 the orchestrator deliberately leaves the listener idle for the scenario's required window before initiating the one controlled peer connection. This keeps the Lab runner useful on a single developer endpoint without pretending an inbound peer exists or violating the negative-control phase.

The automation layer adds no new runtime/library dependency. It uses Bash, Python 3 standard library, and the scenario tools already required by NETA Lab. Scenario `expected.yaml` files remain ground truth; automation must not reinterpret unavailable evidence as a negative observation.
