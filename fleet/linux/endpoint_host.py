from __future__ import annotations

import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

from fleet.model import EndpointState, FleetConfig, ProcessRecord
from fleet.orchestrator.command import CommandRunner, atomic_write_text
from fleet.orchestrator.lease_manager import LeaseManager
from fleet.orchestrator.persona import PersonaStore
from .cgroup import CgroupManager
from .namespace import UtsNamespaceManager
from .network import EndpointNetwork, LinuxNetworkManager
from .process_launcher import NamespaceContext, ProcessLauncher


class LinuxEndpointHost:
    def __init__(self, *, config: FleetConfig, runner: CommandRunner,
                 leases: LeaseManager, personas: PersonaStore) -> None:
        self.config = config
        self.runner = runner
        self.leases = leases
        self.personas = personas
        self.cgroups = CgroupManager(config.cgroup_root)
        self.launcher = ProcessLauncher(runner)
        self.uts = UtsNamespaceManager(runner, self.launcher)
        self.network = LinuxNetworkManager(
            runner,
            bridge=config.bridge,
            gateway=config.gateway,
            prefix_length=leases.network.prefixlen,
            dns_servers=config.dns_servers,
            ownership_file=config.state_root / "network-bridge.json",
        )

    def validate(self) -> None:
        self.cgroups.validate()
        self.runner.require("ip", "nsenter", "unshare", "hostname", "python3")
        if not self.config.agent_binary.exists():
            raise RuntimeError(f"neta-agent binary not found: {self.config.agent_binary}")

    def slot(self, index: int) -> str:
        return f"{self.config.endpoint_prefix}-{index:04d}"

    def endpoint_dir(self, slot: str) -> Path:
        return self.config.state_root / "endpoints" / slot

    def prepare(self, index: int, *, rotate_ip: bool = False) -> EndpointState:
        slot = self.slot(index)
        directory = self.endpoint_dir(slot)
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        persona, hostname = self.personas.assign(directory, slot, index)
        ip_address, prefix, _generation = self.leases.allocate(slot, rotate=rotate_ip)
        names = self.network.names(slot, index)
        cgroup_path = self.cgroups.ensure_endpoint(slot)
        identity_dir = directory / "identity"
        identity_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(identity_dir, 0o700)
        (directory / "logs").mkdir(exist_ok=True)
        (directory / "scenarios").mkdir(exist_ok=True)
        state = EndpointState(
            slot=slot,
            index=index,
            hostname=hostname,
            persona_id=persona.id,
            tenant=persona.tenant,
            ip_address=ip_address,
            prefix_length=prefix,
            netns_name=names.netns_name,
            host_veth=names.host_veth,
            peer_veth=names.peer_veth,
            cgroup_path=cgroup_path,
            state_dir=directory,
            identity_dir=identity_dir,
            database=directory / "neta.db",
        )
        atomic_write_text(directory / "endpoint.json", json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n")
        return state

    def create_kernel_environment(self, state: EndpointState) -> tuple[EndpointState, ProcessRecord]:
        network = EndpointNetwork(state.netns_name, state.host_veth, state.peer_veth)
        self.network.create_endpoint(network, state.ip_address)
        keeper_proc, keeper = self.uts.start_keeper(
            state.hostname,
            state.cgroup_path,
            state.state_dir / "logs" / "uts-keeper.log",
        )
        # Popen ownership is intentionally kept by PID/runtime metadata; the long-lived
        # process survives this method while the orchestrator is alive.
        del keeper_proc
        netns_inode = self.network.netns_inode(network)
        cgroup_id = self.cgroups.cgroup_id(state.slot)
        updated = replace(state, netns_inode=netns_inode, cgroup_id=cgroup_id,
                          uts_keeper_pid=keeper.pid)
        atomic_write_text(updated.state_dir / "endpoint.json", json.dumps(updated.to_dict(), indent=2, sort_keys=True) + "\n")
        return updated, keeper

    def process_context(self, state: EndpointState) -> NamespaceContext:
        if not state.uts_keeper_pid:
            raise RuntimeError(f"endpoint {state.slot} has no UTS keeper")
        return NamespaceContext(
            netns_name=state.netns_name,
            uts_keeper_pid=state.uts_keeper_pid,
            cgroup_path=state.cgroup_path,
        )

    def rotate_ip(self, state: EndpointState) -> EndpointState:
        new_ip, prefix, _generation = self.leases.allocate(state.slot, rotate=True)
        network = EndpointNetwork(state.netns_name, state.host_veth, state.peer_veth)
        self.network.rotate_ip(network, new_ip)
        updated = replace(state, ip_address=new_ip, prefix_length=prefix)
        atomic_write_text(updated.state_dir / "endpoint.json", json.dumps(updated.to_dict(), indent=2, sort_keys=True) + "\n")
        return updated

    def cleanup_kernel_environment(self, state: EndpointState) -> None:
        network = EndpointNetwork(state.netns_name, state.host_veth, state.peer_veth)
        self.cgroups.kill_endpoint(state.slot)
        self.network.delete_endpoint(network)
        try:
            self.cgroups.remove_endpoint(state.slot)
        except RuntimeError:
            pass
