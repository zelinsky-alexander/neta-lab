from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path


class DockerWindowsRuntime:
    def __init__(self, executable: str = "docker") -> None:
        self.executable = executable

    def _run(self, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.executable, *args],
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def preflight(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("Phase 3 Windows fleet orchestration must run on Windows")
        info = self._run(["info", "--format", "{{.OSType}}"])
        if info.stdout.strip().lower() != "windows":
            raise RuntimeError("Docker is not running the Windows container engine")

    def network_exists(self, name: str) -> bool:
        return self._run(["network", "inspect", name], check=False).returncode == 0

    def ensure_nat_network(self, name: str, subnet: str) -> bool:
        if self.network_exists(name):
            details = self.network_inspect(name)
            driver = str(details.get("Driver", "")).lower()
            configured = [str(item.get("Subnet", "")) for item in details.get("IPAM", {}).get("Config", [])]
            if driver != "nat" or subnet not in configured:
                raise RuntimeError(f"existing Docker network {name} is not the expected nat/{subnet} network")
            return False
        self._run(["network", "create", "--driver", "nat", "--subnet", subnet, name])
        return True

    def remove_network(self, name: str) -> None:
        self._run(["network", "rm", name], check=False)

    def network_inspect(self, name: str) -> dict:
        result = self._run(["network", "inspect", name])
        data = json.loads(result.stdout)
        if not data:
            raise RuntimeError(f"Docker network {name} was not returned by inspect")
        return data[0]

    def network_gateway(self, name: str) -> str:
        details = self.network_inspect(name)
        configs = details.get("IPAM", {}).get("Config", [])
        if not configs or not configs[0].get("Gateway"):
            raise RuntimeError(f"Docker network {name} does not expose an IPv4 gateway")
        return str(configs[0]["Gateway"])

    def container_exists(self, name: str) -> bool:
        return self._run(["inspect", name], check=False).returncode == 0

    def create_container(
        self,
        *,
        name: str,
        hostname: str,
        network: str,
        image: str,
        state_dir: Path,
        repo_root: Path,
        agent_binary: Path,
        pipe_name: str,
        slot: str,
        environment: dict[str, str] | None = None,
    ) -> None:
        if self.container_exists(name):
            return
        state_dir.mkdir(parents=True, exist_ok=True)
        source_pipe = rf"\\.\pipe\{pipe_name}"
        agent_dir = agent_binary.parent.resolve()
        command = [
            "create", "--isolation=process", "--name", name, "--hostname", hostname,
            "--network", network,
            "--env", f"NETA_ENDPOINT_SLOT={slot}",
            "--env", "NETA_SENSOR_MODE=broker",
            "--env", f"NETA_SENSOR_BROKER={pipe_name}",
        ]
        for key, value in sorted((environment or {}).items()):
            command.extend(["--env", f"{key}={value}"])
        command.extend([
            "--mount", f"type=bind,source={state_dir.resolve()},target=C:\\neta-state",
            "--mount", f"type=bind,source={repo_root.resolve()},target=C:\\neta-lab,readonly",
            "--mount", f"type=bind,source={agent_dir},target=C:\\neta-agent,readonly",
            "--mount", f"type=npipe,source={source_pipe},target={source_pipe}",
            image,
            "powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", "C:\\neta-lab\\fleet\\windows\\supervisor.ps1",
            "-ControlDir", "C:\\neta-state\\control",
        ])
        self._run(command)

    def start_container(self, name: str) -> None:
        self._run(["start", name])

    def stop_container(self, name: str, timeout_seconds: int = 10) -> None:
        self._run(["stop", "--time", str(timeout_seconds), name], check=False)

    def remove_container(self, name: str) -> None:
        self._run(["rm", "--force", name], check=False)

    def inspect_endpoint(self, name: str, network: str) -> tuple[str, int, str]:
        result = self._run(["inspect", name])
        data = json.loads(result.stdout)[0]
        container_id = str(data["Id"])
        root_pid = int(data["State"].get("Pid", 0))
        networks = data.get("NetworkSettings", {}).get("Networks", {})
        ip_address = str(networks.get(network, {}).get("IPAddress", ""))
        if root_pid <= 0:
            raise RuntimeError(f"container {name} has no host-visible root PID")
        if not ip_address:
            raise RuntimeError(f"container {name} has no IPv4 address on {network}")
        return container_id, root_pid, ip_address

    def is_running(self, name: str) -> bool:
        result = self._run(["inspect", "--format", "{{.State.Running}}", name], check=False)
        return result.returncode == 0 and result.stdout.strip().lower() == "true"
