from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from fleet.orchestrator.command import CommandRunner


@dataclass(frozen=True)
class EndpointNetwork:
    netns_name: str
    host_veth: str
    peer_veth: str
    interface: str = "eth0"


class LinuxNetworkManager:
    def __init__(self, runner: CommandRunner, *, bridge: str, gateway: str,
                 prefix_length: int, dns_servers: tuple[str, ...],
                 ownership_file: Path | None = None) -> None:
        self.runner = runner
        self.bridge = bridge
        self.gateway = gateway
        self.prefix_length = prefix_length
        self.dns_servers = dns_servers
        self.ownership_file = ownership_file

    @staticmethod
    def names(slot: str, index: int) -> EndpointNetwork:
        suffix = f"{index:05d}"
        # Linux IFNAMSIZ is 16 including NUL, so stay well below 15 chars.
        return EndpointNetwork(
            netns_name=f"neta-{slot}",
            host_veth=f"nl{suffix}h",
            peer_veth=f"nl{suffix}e",
        )

    def ensure_bridge(self) -> None:
        exists = self.runner.run(["ip", "link", "show", "dev", self.bridge], check=False)
        owned = bool(self.ownership_file and self.ownership_file.exists())
        if exists.returncode == 0 and not owned:
            raise RuntimeError(
                f"refusing to reuse pre-existing bridge {self.bridge!r}; choose another bridge name"
            )
        if exists.returncode != 0:
            self.runner.run(["ip", "link", "add", self.bridge, "type", "bridge"])
            if self.ownership_file:
                self.ownership_file.parent.mkdir(parents=True, exist_ok=True)
                self.ownership_file.write_text(
                    json.dumps({"version": 1, "bridge": self.bridge}, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                os.chmod(self.ownership_file, 0o600)
        self.runner.run(["ip", "address", "replace", f"{self.gateway}/{self.prefix_length}", "dev", self.bridge])
        self.runner.run(["ip", "link", "set", self.bridge, "up"])

    def _netns_exists(self, name: str) -> bool:
        result = self.runner.run(["ip", "netns", "list"], check=False)
        return any(line.split()[0] == name for line in result.stdout.splitlines() if line.strip())

    def _write_resolv_conf(self, netns: str) -> None:
        if not self.dns_servers:
            return
        directory = Path("/etc/netns") / netns
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "resolv.conf"
        path.write_text("".join(f"nameserver {server}\n" for server in self.dns_servers), encoding="utf-8")
        os.chmod(path, 0o644)

    def create_endpoint(self, network: EndpointNetwork, ip_address: str) -> None:
        if self._netns_exists(network.netns_name):
            self.delete_endpoint(network)
        self.runner.run(["ip", "netns", "add", network.netns_name])
        try:
            self.runner.run(["ip", "link", "add", network.host_veth, "type", "veth", "peer", "name", network.peer_veth])
            self.runner.run(["ip", "link", "set", network.host_veth, "master", self.bridge])
            self.runner.run(["ip", "link", "set", network.host_veth, "up"])
            self.runner.run(["ip", "link", "set", network.peer_veth, "netns", network.netns_name])
            self.runner.run(["ip", "-n", network.netns_name, "link", "set", network.peer_veth, "name", network.interface])
            self.runner.run(["ip", "-n", network.netns_name, "link", "set", "lo", "up"])
            self.runner.run(["ip", "-n", network.netns_name, "link", "set", network.interface, "up"])
            self.runner.run(["ip", "-n", network.netns_name, "address", "replace",
                             f"{ip_address}/{self.prefix_length}", "dev", network.interface])
            self.runner.run(["ip", "-n", network.netns_name, "route", "replace", "default", "via", self.gateway])
            self._write_resolv_conf(network.netns_name)
        except Exception:
            self.delete_endpoint(network)
            raise

    def rotate_ip(self, network: EndpointNetwork, ip_address: str) -> None:
        self.runner.run(["ip", "-n", network.netns_name, "address", "flush", "dev", network.interface, "scope", "global"])
        self.runner.run(["ip", "-n", network.netns_name, "address", "add",
                         f"{ip_address}/{self.prefix_length}", "dev", network.interface])
        self.runner.run(["ip", "-n", network.netns_name, "route", "replace", "default", "via", self.gateway])

    def delete_endpoint(self, network: EndpointNetwork) -> None:
        if self._netns_exists(network.netns_name):
            self.runner.run(["ip", "netns", "del", network.netns_name], check=False)
        self.runner.run(["ip", "link", "del", network.host_veth], check=False)
        directory = Path("/etc/netns") / network.netns_name
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)

    def delete_bridge(self) -> None:
        if self.ownership_file is None or not self.ownership_file.exists():
            return
        try:
            state = json.loads(self.ownership_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if state.get("bridge") != self.bridge:
            return
        self.runner.run(["ip", "link", "del", self.bridge], check=False)
        self.ownership_file.unlink(missing_ok=True)

    def netns_inode(self, network: EndpointNetwork) -> int:
        path = Path("/var/run/netns") / network.netns_name
        value = path.stat().st_ino
        if value <= 0:
            raise RuntimeError(f"invalid network namespace inode for {network.netns_name}")
        return value

    def current_address(self, network: EndpointNetwork) -> str | None:
        result = self.runner.run(["ip", "-n", network.netns_name, "-j", "address", "show", "dev", network.interface], check=False)
        if result.returncode != 0:
            return None
        try:
            payload = json.loads(result.stdout)
            for entry in payload:
                for info in entry.get("addr_info", []):
                    if info.get("family") == "inet" and info.get("scope") == "global":
                        return str(info.get("local"))
        except (json.JSONDecodeError, TypeError):
            return None
        return None
