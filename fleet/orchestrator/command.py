from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Mapping, Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner:
    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def require(self, *commands: str) -> None:
        missing = [name for name in commands if shutil.which(name) is None]
        if missing:
            raise RuntimeError("missing required command(s): " + ", ".join(missing))

    def run(
        self,
        argv: Sequence[str | os.PathLike[str]],
        *,
        check: bool = True,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        capture: bool = True,
    ) -> CommandResult:
        command = [os.fspath(x) for x in argv]
        if self.dry_run:
            return CommandResult(0, "DRY-RUN " + " ".join(command) + "\n", "")
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            cwd=os.fspath(cwd) if cwd else None,
            env=dict(env) if env is not None else None,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
        result = CommandResult(completed.returncode, completed.stdout or "", completed.stderr or "")
        if check and completed.returncode != 0:
            raise RuntimeError(
                f"command failed ({completed.returncode}): {' '.join(command)}\n{result.stderr.strip()}"
            )
        return result

    def popen(
        self,
        argv: Sequence[str | os.PathLike[str]],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        stdout: IO[str] | int | None = None,
        stderr: IO[str] | int | None = None,
    ) -> subprocess.Popen[str]:
        if self.dry_run:
            raise RuntimeError("popen is unavailable in dry-run mode")
        return subprocess.Popen(
            [os.fspath(x) for x in argv],
            text=True,
            cwd=os.fspath(cwd) if cwd else None,
            env=dict(env) if env is not None else None,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )


def atomic_write_text(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)
