from __future__ import annotations

import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from fleet.model import Persona
from fleet.orchestrator.ground_truth import GroundTruthRecorder
from fleet.windows.command_channel import SupervisorChannel
from fleet.windows.model import WindowsEndpointState


class ScenarioCatalog:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.scenarios_root = repo_root / "scenarios"

    def directory(self, scenario_id: str) -> Path:
        sid = scenario_id.zfill(3)
        matches = sorted(self.scenarios_root.glob(f"{sid}-*"))
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one scenario directory for NETA-LAB-{sid}")
        return matches[0]

    def windows_script_host(self, scenario_id: str) -> Path:
        script = self.directory(scenario_id) / "windows" / "run.ps1"
        if not script.exists():
            raise RuntimeError(f"NETA-LAB-{scenario_id.zfill(3)} has no Windows run.ps1")
        return script

    def windows_script_container(self, scenario_id: str) -> str:
        relative = self.windows_script_host(scenario_id).relative_to(self.repo_root)
        return "C:\\neta-lab\\" + str(relative).replace("/", "\\")

    def expected(self, scenario_id: str) -> Path:
        return self.directory(scenario_id) / "expected.yaml"


class HostPeerServer:
    def __init__(self, repo_root: Path, bind_address: str) -> None:
        self.repo_root = repo_root
        self.bind_address = bind_address
        self._lock = threading.Lock()
        self._allocated: set[int] = set()

    def _allocate_port(self) -> int:
        with self._lock:
            for port in range(22000, 46000):
                if port in self._allocated:
                    continue
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind((self.bind_address, port))
                    except OSError:
                        continue
                self._allocated.add(port)
                return port
        raise RuntimeError("no free Windows fleet controlled-peer port available")

    def start_beacon(self, log_path: Path) -> tuple[int, subprocess.Popen[str], Any]:
        port = self._allocate_port()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = log_path.open("a", encoding="utf-8")
        process = subprocess.Popen(
            ["python", str(self.repo_root / "common/server/beacon_server.py"),
             "--bind", self.bind_address, "--port", str(port)],
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                handle.close()
                self.release(port)
                raise RuntimeError("Windows fleet controlled peer exited before becoming ready")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.2)
                if probe.connect_ex((self.bind_address, port)) == 0:
                    return port, process, handle
            time.sleep(0.1)
        process.terminate()
        handle.close()
        self.release(port)
        raise RuntimeError("Windows fleet controlled peer did not become ready")

    def release(self, port: int) -> None:
        with self._lock:
            self._allocated.discard(port)


class WindowsScenarioRunner:
    def __init__(self, *, repo_root: Path, gateway: str, ground_truth: GroundTruthRecorder) -> None:
        self.repo_root = repo_root
        self.gateway = gateway
        self.ground_truth = ground_truth
        self.catalog = ScenarioCatalog(repo_root)
        self.peers = HostPeerServer(repo_root, gateway)

    def _arguments(self, scenario_id: str, parameters: dict[str, Any], peer_port: int | None) -> list[str]:
        sid = scenario_id.zfill(3)
        if sid == "001":
            if peer_port is None:
                raise RuntimeError("NETA-LAB-001 requires controlled peer")
            return [self.gateway, str(peer_port), str(parameters.get("count", 6)),
                    str(parameters.get("interval_seconds", 1))]
        if sid == "006":
            return []
        custom = parameters.get("args")
        if not isinstance(custom, list):
            raise RuntimeError(f"NETA-LAB-{sid} requires parameters.args in Windows fleet mode")
        return [str(value) for value in custom]

    def run(self, endpoint: WindowsEndpointState, persona: Persona, scenario_id: str,
            parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        sid = scenario_id.zfill(3)
        parameters = dict(parameters or {})
        output_dir = endpoint.state_dir / "scenarios" / f"{time.time_ns()}-{sid}"
        output_dir.mkdir(parents=True, exist_ok=True)
        started = self.ground_truth.start_run(
            endpoint_file=endpoint.state_dir / "ground-truth.jsonl",
            endpoint_slot=endpoint.slot,
            agent_id=endpoint.agent_id,
            tenant=endpoint.tenant,
            persona_id=persona.id,
            scenario_id=sid,
            expected_path=self.catalog.expected(sid),
            parameters=parameters,
        )
        peer_process: subprocess.Popen[str] | None = None
        peer_handle = None
        peer_port: int | None = None
        result = "ERROR"
        exit_code = 1
        details: dict[str, Any] = {"output_dir": str(output_dir)}
        try:
            if sid == "001":
                peer_port, peer_process, peer_handle = self.peers.start_beacon(output_dir / "peer.log")
                parameters.update({"target_host": self.gateway, "port": peer_port})
            arguments = self._arguments(sid, parameters, peer_port)
            response = SupervisorChannel(endpoint.state_dir).request(
                "scenario",
                {"script": self.catalog.windows_script_container(sid), "arguments": arguments},
                timeout_seconds=float(parameters.get("timeout_seconds", 180)),
            )
            exit_code = int(response.get("exit_code", 0))
            result = "PASS" if exit_code == 0 else "FAIL"
            details.update({"supervisor_response": response})
        except Exception as exc:
            details["error"] = str(exc)
        finally:
            if peer_process is not None:
                if peer_process.poll() is None:
                    peer_process.terminate()
                    try:
                        peer_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        peer_process.kill()
                if peer_handle is not None:
                    peer_handle.close()
                if peer_port is not None:
                    self.peers.release(peer_port)
        return self.ground_truth.finish_run(
            endpoint.state_dir / "ground-truth.jsonl",
            started,
            exit_code=exit_code,
            result=result,
            details=details,
        )
