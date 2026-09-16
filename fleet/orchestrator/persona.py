from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fleet.model import Persona
from .command import atomic_write_text


class PersonaStore:
    def __init__(self, catalog_dir: Path, seed: int) -> None:
        self.catalog_dir = catalog_dir
        self.seed = seed
        self._catalog = self._load_catalog()

    def _load_catalog(self) -> list[Persona]:
        personas = [Persona.from_dict(json.loads(path.read_text(encoding="utf-8")))
                    for path in sorted(self.catalog_dir.glob("*.json"))]
        if not personas:
            raise RuntimeError(f"no persona definitions found in {self.catalog_dir}")
        return personas

    @property
    def catalog(self) -> tuple[Persona, ...]:
        return tuple(self._catalog)

    def assign(self, endpoint_dir: Path, slot: str, index: int) -> tuple[Persona, str]:
        path = endpoint_dir / "persona.json"
        if path.exists():
            stored = json.loads(path.read_text(encoding="utf-8"))
            persona_id = stored["persona_id"]
            persona = next((p for p in self._catalog if p.id == persona_id), None)
            if persona is None:
                raise RuntimeError(f"persisted persona {persona_id!r} no longer exists")
            return persona, str(stored["hostname"])
        digest = hashlib.sha256(f"{self.seed}:{slot}".encode()).digest()
        persona = self._catalog[int.from_bytes(digest[:8], "big") % len(self._catalog)]
        hostname = f"{persona.hostname_prefix}-{index:04d}"
        atomic_write_text(
            path,
            json.dumps({"version": 1, "slot": slot, "persona_id": persona.id,
                        "hostname": hostname, "tenant": persona.tenant}, indent=2, sort_keys=True) + "\n",
        )
        return persona, hostname
