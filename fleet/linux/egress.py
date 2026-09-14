from __future__ import annotations

import json
from pathlib import Path

from fleet.orchestrator.command import CommandRunner, atomic_write_text


class LinuxEgressManager:
    """Optional, explicitly enabled IPv4 NAT for isolated endpoint namespaces.

    Rules are tagged and removed exactly on cleanup. The default fleet config does
    not touch forwarding/firewall state.
    """

    def __init__(self, runner: CommandRunner, *, state_file: Path, fleet_name: str,
                 subnet: str, bridge: str,
                 ip_forward_path: Path = Path("/proc/sys/net/ipv4/ip_forward")) -> None:
        self.runner = runner
        self.state_file = state_file
        self.subnet = subnet
        self.bridge = bridge
        self.ip_forward_path = ip_forward_path
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in fleet_name)
        self.comment = f"neta-lab-{safe}"[:250]

    def _rule_specs(self) -> list[tuple[str, ...]]:
        return [
            ("-t", "nat", "POSTROUTING", "-s", self.subnet, "!", "-o", self.bridge,
             "-m", "comment", "--comment", self.comment, "-j", "MASQUERADE"),
            ("FORWARD", "-i", self.bridge, "-m", "comment", "--comment", self.comment,
             "-j", "ACCEPT"),
            ("FORWARD", "-o", self.bridge, "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED",
             "-m", "comment", "--comment", self.comment, "-j", "ACCEPT"),
        ]

    @staticmethod
    def _commands(spec: tuple[str, ...], operation: str) -> list[str]:
        if spec[0] == "-t":
            prefix = list(spec[:2])
            chain = spec[2]
            rule = list(spec[3:])
            return ["iptables", *prefix, operation, chain, *rule]
        chain = spec[0]
        rule = list(spec[1:])
        return ["iptables", operation, chain, *rule]

    def enable(self) -> None:
        self.runner.require("iptables", "sysctl")
        previous = self.ip_forward_path.read_text(encoding="ascii").strip()
        changed_forwarding = previous != "1"
        if changed_forwarding:
            self.runner.run(["sysctl", "-w", "net.ipv4.ip_forward=1"])

        # Persist restoration state before touching firewall rules so a failure in
        # the middle of setup can still be recovered by disable().
        atomic_write_text(
            self.state_file,
            json.dumps({"version": 1, "previous_ip_forward": previous,
                        "changed_ip_forward": changed_forwarding,
                        "comment": self.comment}, indent=2, sort_keys=True) + "\n",
        )
        try:
            for spec in self._rule_specs():
                check = self._commands(spec, "-C")
                add = self._commands(spec, "-A")
                if self.runner.run(check, check=False).returncode != 0:
                    self.runner.run(add)
        except Exception:
            self.disable()
            raise

    def disable(self) -> None:
        for spec in reversed(self._rule_specs()):
            check = self._commands(spec, "-C")
            delete = self._commands(spec, "-D")
            if self.runner.run(check, check=False).returncode == 0:
                self.runner.run(delete, check=False)
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text(encoding="utf-8"))
                if state.get("changed_ip_forward") and state.get("previous_ip_forward") in {"0", "1"}:
                    self.runner.run(["sysctl", "-w",
                                     f"net.ipv4.ip_forward={state['previous_ip_forward']}"], check=False)
            except (json.JSONDecodeError, OSError):
                pass
            self.state_file.unlink(missing_ok=True)
