from __future__ import annotations

import subprocess
from pathlib import Path

from fleet.model import ProcessRecord
from fleet.orchestrator.command import CommandRunner
from .process_launcher import NamespaceContext, ProcessLauncher


class UtsNamespaceManager:
    def __init__(self, runner: CommandRunner, launcher: ProcessLauncher) -> None:
        self.runner = runner
        self.launcher = launcher

    def start_keeper(self, hostname: str, cgroup_path: Path, log_file: Path) -> tuple[subprocess.Popen[str], ProcessRecord]:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log = log_file.open("a", encoding="utf-8")
        command = [
            "unshare", "--uts", "--fork", "--kill-child",
            "/bin/sh", "-c", 'hostname "$1"; exec sleep infinity', "neta-uts", hostname,
        ]
        process, record = self.launcher.popen(
            command,
            context=NamespaceContext(cgroup_path=cgroup_path),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        return process, ProcessRecord(record.pid, record.start_ticks, "uts-keeper")
