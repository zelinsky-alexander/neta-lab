from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class SupervisorChannel:
    def __init__(self, endpoint_state_dir: Path) -> None:
        self.control_dir = endpoint_state_dir / "control"
        self.commands_dir = self.control_dir / "commands"
        self.responses_dir = self.control_dir / "responses"
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)

    def wait_ready(self, timeout_seconds: float = 30.0) -> dict[str, Any]:
        ready = self.control_dir / "ready.json"
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if ready.exists():
                return json.loads(ready.read_text(encoding="utf-8-sig"))
            time.sleep(0.1)
        raise RuntimeError(f"Windows endpoint supervisor did not become ready: {self.control_dir}")

    def request(self, command_type: str, payload: dict[str, Any] | None = None,
                timeout_seconds: float = 120.0) -> dict[str, Any]:
        command_id = str(uuid.uuid4())
        command = {"id": command_id, "type": command_type, **(payload or {})}
        target = self.commands_dir / f"{command_id}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(command, sort_keys=True), encoding="utf-8")
        temporary.replace(target)

        response = self.responses_dir / f"{command_id}.json"
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if response.exists():
                result = json.loads(response.read_text(encoding="utf-8-sig"))
                response.unlink(missing_ok=True)
                if result.get("status") != "ok":
                    raise RuntimeError(str(result.get("error", "Windows endpoint command failed")))
                return result
            time.sleep(0.1)
        raise RuntimeError(f"Windows endpoint command timed out: {command_type}")
