from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FleetConfig:
    name: str = "default"
    state_root: Path = Path("/var/lib/neta-lab/fleet/default")
    runtime_root: Path = Path("/run/neta-lab/fleet/default")
    cgroup_root: Path = Path("/sys/fs/cgroup/neta-lab/default")
    bridge: str = "neta-sim0"
    subnet: str = "10.70.0.0/16"
    gateway: str = "10.70.0.1"
    dns_servers: tuple[str, ...] = ("1.1.1.1", "8.8.8.8")
    endpoint_prefix: str = "lnx"
    queue_capacity: int = 1024
    seed: int = 82913741
    agent_binary: Path = Path("./build/neta-agent")
    agent_duration_seconds: int = 86400
    agent_poll_ms: int = 100
    max_db_mb: int = 200
    heartbeat_seconds: int = 60
    heartbeat_jitter_percent: int = 20
    reporting_mode: str = "SIGNIFICANT_ONLY"
    min_confidence: float = 0.80
    reporting_cooldown_seconds: int = 1800
    scenario_max_concurrent: int = 8
    allow_unenrolled: bool = False
    enable_nat: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FleetConfig":
        defaults = cls()
        def p(key: str) -> Path:
            return Path(data.get(key, getattr(defaults, key)))
        return cls(
            name=str(data.get("name", defaults.name)),
            state_root=p("state_root"),
            runtime_root=p("runtime_root"),
            cgroup_root=p("cgroup_root"),
            bridge=str(data.get("bridge", defaults.bridge)),
            subnet=str(data.get("subnet", defaults.subnet)),
            gateway=str(data.get("gateway", defaults.gateway)),
            dns_servers=tuple(data.get("dns_servers", defaults.dns_servers)),
            endpoint_prefix=str(data.get("endpoint_prefix", defaults.endpoint_prefix)),
            queue_capacity=int(data.get("queue_capacity", defaults.queue_capacity)),
            seed=int(data.get("seed", defaults.seed)),
            agent_binary=Path(data.get("agent_binary", defaults.agent_binary)),
            agent_duration_seconds=int(data.get("agent_duration_seconds", defaults.agent_duration_seconds)),
            agent_poll_ms=int(data.get("agent_poll_ms", defaults.agent_poll_ms)),
            max_db_mb=int(data.get("max_db_mb", defaults.max_db_mb)),
            heartbeat_seconds=int(data.get("heartbeat_seconds", defaults.heartbeat_seconds)),
            heartbeat_jitter_percent=int(data.get("heartbeat_jitter_percent", defaults.heartbeat_jitter_percent)),
            reporting_mode=str(data.get("reporting_mode", defaults.reporting_mode)),
            min_confidence=float(data.get("min_confidence", defaults.min_confidence)),
            reporting_cooldown_seconds=int(data.get("reporting_cooldown_seconds", defaults.reporting_cooldown_seconds)),
            scenario_max_concurrent=int(data.get("scenario_max_concurrent", defaults.scenario_max_concurrent)),
            allow_unenrolled=bool(data.get("allow_unenrolled", defaults.allow_unenrolled)),
            enable_nat=bool(data.get("enable_nat", defaults.enable_nat)),
        )


@dataclass(frozen=True)
class Persona:
    id: str
    role: str
    platform: str
    hostname_prefix: str
    activity: str
    working_hours: str
    normal_apps: tuple[str, ...]
    scenario_rate_per_hour: float
    scenario_weights: dict[str, float]
    threat_scenario_probability: float = 0.0
    tenant: str = "lab-default"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Persona":
        return cls(
            id=str(data["id"]),
            role=str(data["role"]),
            platform=str(data.get("platform", "linux")),
            hostname_prefix=str(data.get("hostname_prefix", data["id"])),
            activity=str(data.get("activity", "medium")),
            working_hours=str(data.get("working_hours", "always")),
            normal_apps=tuple(str(x) for x in data.get("normal_apps", [])),
            scenario_rate_per_hour=float(data.get("scenario_rate_per_hour", 0.0)),
            scenario_weights={str(k).zfill(3): float(v) for k, v in data.get("scenario_weights", {}).items()},
            threat_scenario_probability=float(data.get("threat_scenario_probability", 0.0)),
            tenant=str(data.get("tenant", "lab-default")),
        )


@dataclass
class EndpointState:
    slot: str
    index: int
    hostname: str
    persona_id: str
    tenant: str
    ip_address: str
    prefix_length: int
    netns_name: str
    host_veth: str
    peer_veth: str
    cgroup_path: Path
    state_dir: Path
    identity_dir: Path
    database: Path
    netns_inode: int = 0
    cgroup_id: int = 0
    uts_keeper_pid: int | None = None
    agent_pid: int | None = None
    agent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "index": self.index,
            "hostname": self.hostname,
            "persona_id": self.persona_id,
            "tenant": self.tenant,
            "ip_address": self.ip_address,
            "prefix_length": self.prefix_length,
            "netns_name": self.netns_name,
            "host_veth": self.host_veth,
            "peer_veth": self.peer_veth,
            "cgroup_path": str(self.cgroup_path),
            "state_dir": str(self.state_dir),
            "identity_dir": str(self.identity_dir),
            "database": str(self.database),
            "netns_inode": self.netns_inode,
            "cgroup_id": self.cgroup_id,
            "uts_keeper_pid": self.uts_keeper_pid,
            "agent_pid": self.agent_pid,
            "agent_id": self.agent_id,
        }


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    start_ticks: int
    kind: str
    slot: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"pid": self.pid, "start_ticks": self.start_ticks, "kind": self.kind, "slot": self.slot}


@dataclass
class RuntimeState:
    broker: ProcessRecord | None = None
    peer_processes: list[ProcessRecord] = field(default_factory=list)
    endpoint_processes: dict[str, list[ProcessRecord]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker.to_dict() if self.broker else None,
            "peer_processes": [x.to_dict() for x in self.peer_processes],
            "endpoint_processes": {
                slot: [x.to_dict() for x in records]
                for slot, records in self.endpoint_processes.items()
            },
        }
