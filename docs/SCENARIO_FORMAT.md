# Scenario Format

Each scenario lives under `scenarios/NNN-name/` and should contain:

- `README.md` — purpose, safety, setup, execution, expected NETA evidence, expected finding, cleanup.
- `expected.yaml` — machine-readable ground truth and validation expectations.
- `linux/` — Linux client scripts when supported.
- `windows/` — Windows client scripts when supported.
- `server/` — controlled server helpers when required.

Scenario IDs are immutable once published. A scenario should distinguish independent lab ground truth from NETA observations. Lab markers such as run IDs or HTTP headers must never be required by detection rules; they exist only to make validation unambiguous.

Initial expected-result fields are intentionally simple and may evolve when automated validation is added.
