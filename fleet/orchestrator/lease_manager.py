from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Any

from .command import atomic_write_text


class LeaseManager:
    """Persistent deterministic DHCP-like lease allocator.

    IP addresses are intentionally ephemeral while endpoint identity is stable.
    Rotation increments a persistent generation and deterministically selects a
    different free address for the same endpoint.
    """

    def __init__(self, state_file: Path, subnet: str, gateway: str, seed: int) -> None:
        self.state_file = state_file
        self.network = ipaddress.ip_network(subnet, strict=True)
        self.gateway = ipaddress.ip_address(gateway)
        if self.gateway not in self.network:
            raise ValueError("gateway is outside configured subnet")
        if self.network.version != 4:
            raise ValueError("Phase 2 lease manager currently expects IPv4")
        self.seed = seed

    def _load(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {"version": 1, "leases": {}}
        data = json.loads(self.state_file.read_text(encoding="utf-8"))
        if data.get("version") != 1 or not isinstance(data.get("leases"), dict):
            raise RuntimeError(f"unsupported or corrupt lease state: {self.state_file}")
        return data

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_text(self.state_file, json.dumps(state, indent=2, sort_keys=True) + "\n")

    def _candidate(self, slot: str, generation: int, probe: int) -> ipaddress.IPv4Address:
        first = int(self.network.network_address) + 2
        last = int(self.network.broadcast_address) - 1
        span = last - first + 1
        if span <= 0:
            raise RuntimeError("subnet has no endpoint addresses")
        digest = hashlib.sha256(f"{self.seed}:{slot}:{generation}".encode()).digest()
        offset = int.from_bytes(digest[:8], "big") % span
        return ipaddress.ip_address(first + ((offset + probe) % span))

    def allocate(self, slot: str, *, rotate: bool = False) -> tuple[str, int, int]:
        state = self._load()
        leases: dict[str, Any] = state["leases"]
        current = leases.get(slot)
        if current and not rotate:
            return str(current["address"]), self.network.prefixlen, int(current.get("generation", 0))
        generation = (int(current.get("generation", 0)) + 1) if current else 0
        used = {
            str(value["address"])
            for name, value in leases.items()
            if name != slot and isinstance(value, dict) and "address" in value
        }
        old_address = str(current["address"]) if current else None
        for probe in range(max(1, self.network.num_addresses - 3)):
            candidate = self._candidate(slot, generation, probe)
            text = str(candidate)
            if candidate == self.gateway or text in used or (rotate and text == old_address):
                continue
            leases[slot] = {"address": text, "generation": generation}
            self._save(state)
            return text, self.network.prefixlen, generation
        raise RuntimeError("no free address is available in simulator subnet")

    def release(self, slot: str) -> None:
        state = self._load()
        if state["leases"].pop(slot, None) is not None:
            self._save(state)

    def all(self) -> dict[str, dict[str, Any]]:
        return dict(self._load()["leases"])
