# Scenario Format

Each scenario lives under `scenarios/NNN-name/` and should contain:

- `README.md` — purpose, safety, setup, execution, expected NETA evidence, expected finding, cleanup.
- `expected.yaml` — machine-readable ground truth and validation expectations.
- `linux/` — Linux client scripts when supported.
- `windows/` — Windows client scripts when supported.
- `server/` — controlled server helpers when required.

Scenario IDs are immutable once published. A scenario should distinguish independent lab ground truth from NETA observations. Lab markers such as run IDs or HTTP headers must never be required by detection rules; they exist only to make validation unambiguous.

Every scenario also has a constrained `acceptance_contract` mapping. It declares whether a detector is required, the trusted rule and semantic type, minimum severity, permitted coordinator status, required evidence and provenance, Portal visibility, assurance state, and forbidden rules. `automation/acceptance_contracts.py` rejects malformed or incomplete contracts and emits the normalized `contracts.json` consumed by full-cycle acceptance.
