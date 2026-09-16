from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GroundTruthRecorder:
    def __init__(self, fleet_file: Path) -> None:
        self.fleet_file = fleet_file
        self._lock = threading.Lock()

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def expected_manifest(path: Path) -> dict[str, Any]:
        result: dict[str, Any] = {
            "scenario_version": None,
            "expected_evidence_types": {},
            "expected_finding": None,
        }
        if not path.exists():
            return result
        section = None
        in_findings = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not line.startswith(" ") and stripped.endswith(":"):
                section = stripped[:-1]
                in_findings = section == "expected_findings"
                continue
            if section == "scenario" and line.startswith("  ") and ":" in stripped:
                key, value = stripped.split(":", 1)
                if key == "version":
                    result["scenario_version"] = value.strip().strip("'\"")
            elif section == "expected_evidence" and line.startswith("  ") and ":" in stripped:
                key, value = stripped.split(":", 1)
                result["expected_evidence_types"][key.strip()] = value.strip()
            elif in_findings and stripped.startswith("- type:") and result["expected_finding"] is None:
                result["expected_finding"] = stripped.split(":", 1)[1].strip()
        return result

    def _append(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line.encode())
                os.fsync(fd)
            finally:
                os.close(fd)

    def start_run(
        self,
        *,
        endpoint_file: Path,
        endpoint_slot: str,
        agent_id: str | None,
        tenant: str,
        persona_id: str,
        scenario_id: str,
        expected_path: Path,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        expected = self.expected_manifest(expected_path)
        record = {
            "record_type": "scenario_started",
            "run_id": str(uuid.uuid4()),
            "endpoint_slot": endpoint_slot,
            "agent_id": agent_id,
            "tenant": tenant,
            "persona_id": persona_id,
            "scenario_id": f"NETA-LAB-{scenario_id.zfill(3)}",
            "scenario_version": expected["scenario_version"],
            "start_timestamp": self.now(),
            "end_timestamp": None,
            "parameters": parameters,
            "expected_evidence_types": expected["expected_evidence_types"],
            "expected_rule_finding": expected["expected_finding"],
            "actual_observed_evidence": None,
            "actual_finding": None,
            "result": "RUNNING",
        }
        self._append(self.fleet_file, record)
        self._append(endpoint_file, record)
        return record

    def finish_run(self, endpoint_file: Path, started: dict[str, Any], *, exit_code: int,
                   result: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        record = dict(started)
        record.update({
            "record_type": "scenario_finished",
            "end_timestamp": self.now(),
            "exit_code": exit_code,
            "result": result,
            "details": details or {},
        })
        self._append(self.fleet_file, record)
        self._append(endpoint_file, record)
        return record

    def annotate_validation(self, endpoint_file: Path, *, run_id: str,
                            actual_observed_evidence: Any, actual_finding: Any,
                            result: str) -> None:
        record = {
            "record_type": "scenario_validation",
            "run_id": run_id,
            "timestamp": self.now(),
            "actual_observed_evidence": actual_observed_evidence,
            "actual_finding": actual_finding,
            "result": result,
        }
        self._append(self.fleet_file, record)
        self._append(endpoint_file, record)
