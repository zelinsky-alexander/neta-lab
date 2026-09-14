#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
python3 -m compileall -q "$ROOT/fleet"
python3 -m unittest discover -s "$ROOT/tests" -p 'test_fleet_phase2.py' -v
bash -n "$ROOT/automation/neta-fleet-linux"
echo "NETA fleet Phase 2 non-root tests passed"
