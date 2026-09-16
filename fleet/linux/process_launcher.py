from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Mapping, Sequence

from fleet.model import ProcessRecord
from fleet.orchestrator.command import CommandRunner


@dataclass(frozen=True)
class NamespaceContext:
    netns_name: str | None = None
    uts_keeper_pid: int | None = None
    cgroup_path: Path | None = None


class ProcessLauncher:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    @staticmethod
    def process_start_ticks(pid: int) -> int:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        close = text.rfind(")")
        if close < 0:
            raise RuntimeError(f"cannot parse /proc/{pid}/stat")
        fields = text[close + 2:].split()
        # starttime is field 22 overall; after pid+comm this is index 19.
        return int(fields[19])

    @staticmethod
    def _wrapped(command: Sequence[str | os.PathLike[str]], context: NamespaceContext) -> list[str]:
        target = [os.fspath(x) for x in command]
        # Use `ip netns exec` for the network namespace so iproute2 also
        # applies /etc/netns/<name>/resolv.conf in a private mount namespace.
        # UTS is entered outside it; the inner iproute2 process preserves UTS.
        if context.netns_name:
            target = ["ip", "netns", "exec", context.netns_name, *target]
        if context.uts_keeper_pid:
            target = ["nsenter", f"--uts=/proc/{context.uts_keeper_pid}/ns/uts", "--", *target]
        if context.cgroup_path:
            # The tiny shell writes its own PID into the dedicated cgroup and then
            # execs the target, preserving PID/cgroup membership without preexec_fn.
            return [
                "/bin/sh", "-c",
                'printf "%s\\n" "$$" > "$1/cgroup.procs"; shift; exec "$@"',
                "neta-fleet-cgroup", os.fspath(context.cgroup_path), *target,
            ]
        return target

    def popen(self, command: Sequence[str | os.PathLike[str]], *, context: NamespaceContext,
              env: Mapping[str, str] | None = None, cwd: Path | None = None,
              stdout: IO[str] | int | None = None, stderr: IO[str] | int | None = None) -> tuple[subprocess.Popen[str], ProcessRecord]:
        process = self.runner.popen(self._wrapped(command, context), env=env, cwd=cwd,
                                    stdout=stdout, stderr=stderr)
        start_ticks = self.process_start_ticks(process.pid)
        return process, ProcessRecord(process.pid, start_ticks, "process")

    def run(self, command: Sequence[str | os.PathLike[str]], *, context: NamespaceContext,
            env: Mapping[str, str] | None = None, cwd: Path | None = None,
            check: bool = True):
        return self.runner.run(self._wrapped(command, context), env=env, cwd=cwd, check=check)

    @staticmethod
    def alive(record: ProcessRecord) -> bool:
        try:
            return ProcessLauncher.process_start_ticks(record.pid) == record.start_ticks
        except (FileNotFoundError, ProcessLookupError, RuntimeError, ValueError):
            return False

    @staticmethod
    def terminate(record: ProcessRecord, timeout: float = 5.0) -> None:
        if not ProcessLauncher.alive(record):
            return
        try:
            os.killpg(record.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not ProcessLauncher.alive(record):
                return
            time.sleep(0.05)
        try:
            os.killpg(record.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
