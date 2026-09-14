from __future__ import annotations

import os
import signal
import time
from pathlib import Path


class CgroupManager:
    def __init__(self, root: Path) -> None:
        self.root = root

    def validate(self) -> None:
        if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
            raise RuntimeError("NETA fleet simulator requires cgroup v2")
        if os.geteuid() != 0:
            raise RuntimeError("NETA Linux fleet setup requires root privileges")

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def endpoint_path(self, slot: str) -> Path:
        return self.root / slot

    def ensure_endpoint(self, slot: str) -> Path:
        self.ensure_root()
        path = self.endpoint_path(slot)
        path.mkdir(exist_ok=True)
        return path

    def cgroup_id(self, slot: str) -> int:
        path = self.endpoint_path(slot)
        value = path.stat().st_ino
        if value <= 0:
            raise RuntimeError(f"invalid cgroup id for {slot}")
        return value

    def kill_endpoint(self, slot: str, timeout: float = 5.0) -> None:
        path = self.endpoint_path(slot)
        if not path.exists():
            return
        kill_file = path / "cgroup.kill"
        if kill_file.exists():
            try:
                kill_file.write_text("1\n", encoding="ascii")
            except OSError:
                pass
        else:
            procs = path / "cgroup.procs"
            try:
                pids = [int(x) for x in procs.read_text(encoding="ascii").split()]
            except (OSError, ValueError):
                pids = []
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                remaining = (path / "cgroup.procs").read_text(encoding="ascii").strip()
            except OSError:
                return
            if not remaining:
                return
            time.sleep(0.05)
        try:
            pids = [int(x) for x in (path / "cgroup.procs").read_text().split()]
        except (OSError, ValueError):
            pids = []
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def remove_endpoint(self, slot: str) -> None:
        path = self.endpoint_path(slot)
        if not path.exists():
            return
        self.kill_endpoint(slot)
        try:
            path.rmdir()
        except OSError as exc:
            raise RuntimeError(f"unable to remove cgroup {path}: {exc}") from exc

    def remove_root_if_empty(self) -> None:
        try:
            self.root.rmdir()
        except OSError:
            pass
