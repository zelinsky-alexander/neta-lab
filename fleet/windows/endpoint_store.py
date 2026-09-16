from __future__ import annotations

import json
from pathlib import Path

from fleet.windows.model import WindowsEndpointState


class WindowsEndpointStore:
    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root
        self.endpoints_root = state_root / "endpoints"

    def endpoint_dir(self, slot: str) -> Path:
        return self.endpoints_root / slot

    def save(self, endpoint: WindowsEndpointState) -> None:
        directory = self.endpoint_dir(endpoint.slot)
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / "endpoint.json.tmp"
        temporary.write_text(json.dumps(endpoint.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(directory / "endpoint.json")

    def load(self, slot: str) -> WindowsEndpointState | None:
        path = self.endpoint_dir(slot) / "endpoint.json"
        if not path.exists():
            return None
        return WindowsEndpointState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def load_all(self) -> list[WindowsEndpointState]:
        result: list[WindowsEndpointState] = []
        if not self.endpoints_root.exists():
            return result
        for path in sorted(self.endpoints_root.glob("*/endpoint.json")):
            result.append(WindowsEndpointState.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return result
