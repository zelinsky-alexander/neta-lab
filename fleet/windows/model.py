from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WindowsFleetConfig:
    name: str
    state_root: Path
    runtime_root: Path
    endpoint_prefix: str
    docker_network: str
    subnet: str
    container_image: str
    agent_binary: Path
    pipe_name: str
    queue_capacity: int
    seed: int
    agent_duration_seconds: int
    agent_poll_ms: int
    max_db_mb: int
    heartbeat_seconds: int
    heartbeat_jitter_percent: int
    reporting_mode: str
    min_confidence: float
    reporting_cooldown_seconds: int
    scenario_max_concurrent: int
    allow_unenrolled: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WindowsFleetConfig":
        return cls(
            name=str(data.get("name", "windows-default")),
            state_root=Path(data.get("state_root", "C:/ProgramData/NETA-Lab/fleet/windows-default")),
            runtime_root=Path(data.get("runtime_root", "C:/ProgramData/NETA-Lab/run/windows-default")),
            endpoint_prefix=str(data.get("endpoint_prefix", "win")),
            docker_network=str(data.get("docker_network", "neta-sim-win")),
            subnet=str(data.get("subnet", "172.30.0.0/16")),
            container_image=str(data.get("container_image", "mcr.microsoft.com/windows/servercore:ltsc2025")),
            agent_binary=Path(data.get("agent_binary", "../neta-agent/build-windows/Release/neta-agent.exe")),
            pipe_name=str(data.get("pipe_name", "neta-sensor-broker")),
            queue_capacity=int(data.get("queue_capacity", 1024)),
            seed=int(data.get("seed", 82913741)),
            agent_duration_seconds=int(data.get("agent_duration_seconds", 86400)),
            agent_poll_ms=int(data.get("agent_poll_ms", 100)),
            max_db_mb=int(data.get("max_db_mb", 200)),
            heartbeat_seconds=int(data.get("heartbeat_seconds", 60)),
            heartbeat_jitter_percent=int(data.get("heartbeat_jitter_percent", 20)),
            reporting_mode=str(data.get("reporting_mode", "SIGNIFICANT_ONLY")),
            min_confidence=float(data.get("min_confidence", 0.80)),
            reporting_cooldown_seconds=int(data.get("reporting_cooldown_seconds", 1800)),
            scenario_max_concurrent=int(data.get("scenario_max_concurrent", 8)),
            allow_unenrolled=bool(data.get("allow_unenrolled", False)),
        )


@dataclass
class WindowsEndpointState:
    slot: str
    index: int
    hostname: str
    persona_id: str
    tenant: str
    container_name: str
    container_id: str
    root_pid: int
    ip_address: str
    state_dir: Path
    identity_dir: Path
    database: Path
    agent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "index": self.index,
            "hostname": self.hostname,
            "persona_id": self.persona_id,
            "tenant": self.tenant,
            "container_name": self.container_name,
            "container_id": self.container_id,
            "root_pid": self.root_pid,
            "ip_address": self.ip_address,
            "state_dir": str(self.state_dir),
            "identity_dir": str(self.identity_dir),
            "database": str(self.database),
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WindowsEndpointState":
        return cls(
            slot=str(data["slot"]),
            index=int(data["index"]),
            hostname=str(data["hostname"]),
            persona_id=str(data["persona_id"]),
            tenant=str(data["tenant"]),
            container_name=str(data["container_name"]),
            container_id=str(data.get("container_id", "")),
            root_pid=int(data.get("root_pid", 0)),
            ip_address=str(data.get("ip_address", "")),
            state_dir=Path(data["state_dir"]),
            identity_dir=Path(data["identity_dir"]),
            database=Path(data["database"]),
            agent_id=data.get("agent_id"),
        )


@dataclass(frozen=True)
class EnrollmentConfig:
    coordinator: str
    fleet_ca: Path
    fleet_id: str
    tokens: dict[str, str]
