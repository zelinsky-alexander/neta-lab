from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fleet.model import EndpointState, FleetConfig
from fleet.linux.process_launcher import ProcessLauncher


@dataclass(frozen=True)
class EnrollmentConfig:
    coordinator: str
    fleet_ca: Path
    fleet_id: str
    tokens: dict[str, str]

    @classmethod
    def from_token_file(cls, *, coordinator: str, fleet_ca: Path,
                        fleet_id: str, token_file: Path,
                        slots: list[str]) -> "EnrollmentConfig":
        data: Any = json.loads(token_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            tokens = {str(k): str(v) for k, v in data.items()}
        elif isinstance(data, list):
            if len(data) < len(slots):
                raise RuntimeError("enrollment token list has fewer tokens than endpoint slots")
            tokens = {slot: str(data[index]) for index, slot in enumerate(slots)}
        else:
            raise RuntimeError("enrollment token file must contain an object or array")
        missing = [slot for slot in slots if not tokens.get(slot)]
        if missing:
            raise RuntimeError("missing enrollment token(s) for: " + ", ".join(missing))
        return cls(coordinator, fleet_ca, fleet_id, tokens)


class IdentityManager:
    def __init__(self, config: FleetConfig, launcher: ProcessLauncher) -> None:
        self.config = config
        self.launcher = launcher

    @staticmethod
    def load_identity(identity_dir: Path) -> dict[str, str] | None:
        path = identity_dir / "identity.conf"
        if not path.exists():
            return None
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        if not values.get("agent_id"):
            raise RuntimeError(f"invalid NETA identity: {path}")
        return values

    def ensure_enrolled(self, endpoint: EndpointState, context, enrollment: EnrollmentConfig | None) -> str | None:
        existing = self.load_identity(endpoint.identity_dir)
        if existing:
            return existing["agent_id"]
        if enrollment is None:
            if self.config.allow_unenrolled:
                return None
            raise RuntimeError(
                f"{endpoint.slot} is not enrolled; provide coordinator/fleet CA/token file or use --allow-unenrolled"
            )
        token = enrollment.tokens.get(endpoint.slot)
        if not token:
            raise RuntimeError(f"no enrollment token for {endpoint.slot}")
        env = os.environ.copy()
        # Never place the one-time token in persistent endpoint metadata or logs.
        command = [
            str(self.config.agent_binary.resolve()),
            "fleet", "enroll",
            "--coordinator", enrollment.coordinator,
            "--fleet-ca", str(enrollment.fleet_ca.resolve()),
            "--token", token,
            "--fleet-id", enrollment.fleet_id,
            "--display-name", endpoint.hostname,
            "--state-dir", str(endpoint.identity_dir),
        ]
        result = self.launcher.run(command, context=context, env=env, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"enrollment failed for {endpoint.slot}: {result.stderr.strip()}")
        identity = self.load_identity(endpoint.identity_dir)
        if not identity:
            raise RuntimeError(f"enrollment returned success but {endpoint.slot} has no identity.conf")
        return identity["agent_id"]

    @staticmethod
    def validate_unique(endpoints: list[EndpointState], *, require_all: bool) -> None:
        ids = [endpoint.agent_id for endpoint in endpoints if endpoint.agent_id]
        if require_all and len(ids) != len(endpoints):
            raise RuntimeError("not every endpoint has a real NETA AgentId")
        if len(ids) != len(set(ids)):
            raise RuntimeError("duplicate AgentId detected across simulated endpoints")
