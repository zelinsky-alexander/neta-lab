from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fleet.model import EndpointState, ProcessRecord
from fleet.linux.network import EndpointNetwork, LinuxNetworkManager
from fleet.linux.process_launcher import ProcessLauncher


@dataclass(frozen=True)
class EndpointHealth:
    slot: str
    agent_alive: bool
    uts_alive: bool
    netns_present: bool
    cgroup_present: bool
    expected_ip: str
    observed_ip: str | None
    enrolled: bool
    database_bytes: int

    @property
    def healthy(self) -> bool:
        return (
            self.agent_alive and self.uts_alive and self.netns_present and
            self.cgroup_present and self.expected_ip == self.observed_ip
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "healthy": self.healthy}


class HealthMonitor:
    def __init__(self, network: LinuxNetworkManager) -> None:
        self.network = network

    def endpoint(self, state: EndpointState, records: list[ProcessRecord]) -> EndpointHealth:
        agent = next((x for x in records if x.kind == "agent"), None)
        keeper = next((x for x in records if x.kind == "uts-keeper"), None)
        ns_path = Path("/var/run/netns") / state.netns_name
        network = EndpointNetwork(state.netns_name, state.host_veth, state.peer_veth)
        return EndpointHealth(
            slot=state.slot,
            agent_alive=bool(agent and ProcessLauncher.alive(agent)),
            uts_alive=bool(keeper and ProcessLauncher.alive(keeper)),
            netns_present=ns_path.exists(),
            cgroup_present=state.cgroup_path.exists(),
            expected_ip=state.ip_address,
            observed_ip=self.network.current_address(network) if ns_path.exists() else None,
            enrolled=(state.identity_dir / "identity.conf").exists(),
            database_bytes=state.database.stat().st_size if state.database.exists() else 0,
        )
