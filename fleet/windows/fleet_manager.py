from __future__ import annotations

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from fleet.model import Persona
from fleet.orchestrator.ground_truth import GroundTruthRecorder
from fleet.orchestrator.persona import PersonaStore
from fleet.windows.command_channel import SupervisorChannel
from fleet.windows.docker_runtime import DockerWindowsRuntime
from fleet.windows.endpoint_store import WindowsEndpointStore
from fleet.windows.model import EnrollmentConfig, WindowsEndpointState, WindowsFleetConfig
from fleet.windows.scenario_runner import WindowsScenarioRunner
from fleet.windows.scheduler import WindowsScenarioScheduler


class WindowsFleetManager:
    def __init__(self, *, config: WindowsFleetConfig, repo_root: Path,
                 runtime: DockerWindowsRuntime | None = None) -> None:
        self.config = config
        self.repo_root = repo_root
        self.runtime = runtime or DockerWindowsRuntime()
        self.store = WindowsEndpointStore(config.state_root)
        self.personas = PersonaStore(repo_root / "fleet/windows/personas", config.seed)
        self.ground_truth = GroundTruthRecorder(config.state_root / "ground-truth" / "runs.jsonl")

    @property
    def runtime_file(self) -> Path:
        return self.config.runtime_root / "runtime.json"

    def _environment(self) -> dict[str, str]:
        return {
            "NETA_FLEET_STATE_DIR": "C:\\neta-state\\identity",
            "NETA_FLEET_HEARTBEAT_SECONDS": str(self.config.heartbeat_seconds),
            "NETA_FLEET_HEARTBEAT_JITTER_PERCENT": str(self.config.heartbeat_jitter_percent),
            "NETA_FLEET_REPORTING_MODE": self.config.reporting_mode,
            "NETA_FLEET_MIN_CONFIDENCE": str(self.config.min_confidence),
            "NETA_FLEET_REPORTING_COOLDOWN_SECONDS": str(self.config.reporting_cooldown_seconds),
        }

    def _endpoint(self, index: int) -> tuple[WindowsEndpointState, Persona]:
        slot = f"{self.config.endpoint_prefix}-{index:04d}"
        endpoint_dir = self.store.endpoint_dir(slot)
        endpoint_dir.mkdir(parents=True, exist_ok=True)
        persona, hostname = self.personas.assign(endpoint_dir, slot, index)
        existing = self.store.load(slot)
        state = WindowsEndpointState(
            slot=slot,
            index=index,
            hostname=hostname,
            persona_id=persona.id,
            tenant=persona.tenant,
            container_name=f"neta-{slot}",
            container_id=existing.container_id if existing else "",
            root_pid=existing.root_pid if existing else 0,
            ip_address=existing.ip_address if existing else "",
            state_dir=endpoint_dir,
            identity_dir=endpoint_dir / "identity",
            database=endpoint_dir / "neta.db",
            agent_id=existing.agent_id if existing else None,
        )
        return state, persona

    def _start_pipe_bootstrap(self) -> subprocess.Popen[str]:
        self.config.runtime_root.mkdir(parents=True, exist_ok=True)
        ready = self.config.runtime_root / "pipe-bootstrap.ready"
        ready.unlink(missing_ok=True)
        process = subprocess.Popen(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(self.repo_root / "fleet/windows/pipe_bootstrap.ps1"),
             "-PipeName", self.config.pipe_name, "-ReadyFile", str(ready)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if ready.exists():
                return process
            if process.poll() is not None:
                error = process.stderr.read() if process.stderr else ""
                raise RuntimeError(f"named-pipe bootstrap failed: {error.strip()}")
            time.sleep(0.1)
        process.terminate()
        raise RuntimeError("named-pipe bootstrap did not become ready")

    @staticmethod
    def _stop_process(process: subprocess.Popen[str] | None) -> None:
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _start_broker(self, endpoints: list[WindowsEndpointState]) -> subprocess.Popen[str]:
        command = [str(self.config.agent_binary), "sensor-broker",
                   "--pipe", self.config.pipe_name,
                   "--queue-capacity", str(self.config.queue_capacity)]
        for endpoint in endpoints:
            command.extend(["--map", f"{endpoint.slot}:{endpoint.root_pid}"])
        log_path = self.config.state_root / "broker.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("a", encoding="utf-8")
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True)
        log.close()
        time.sleep(1.0)
        if process.poll() is not None:
            raise RuntimeError(f"Windows sensor broker exited early with code {process.returncode}; see {log_path}")
        return process

    def _save_runtime(self, *, endpoints: list[WindowsEndpointState], broker_pid: int,
                      network_owned: bool) -> None:
        self.config.runtime_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "broker_pid": broker_pid,
            "network_owned": network_owned,
            "network": self.config.docker_network,
            "pipe_name": self.config.pipe_name,
            "endpoints": [endpoint.to_dict() for endpoint in endpoints],
        }
        temporary = self.runtime_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.runtime_file)

    def _load_runtime(self) -> dict[str, Any]:
        if not self.runtime_file.exists():
            return {}
        return json.loads(self.runtime_file.read_text(encoding="utf-8"))

    @staticmethod
    def _agent_id(identity_dir: Path) -> str | None:
        path = identity_dir / "identity.conf"
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("agent_id="):
                return line.split("=", 1)[1].strip() or None
        return None

    def _enroll(self, endpoint: WindowsEndpointState, enrollment: EnrollmentConfig) -> None:
        if self._agent_id(endpoint.identity_dir):
            endpoint.agent_id = self._agent_id(endpoint.identity_dir)
            return
        token = enrollment.tokens.get(endpoint.slot)
        if not token:
            raise RuntimeError(f"no unused enrollment token supplied for {endpoint.slot}")
        ca_copy = endpoint.state_dir / "fleet-ca.crt"
        shutil.copyfile(enrollment.fleet_ca, ca_copy)
        arguments = [
            "fleet", "enroll",
            "--coordinator", enrollment.coordinator,
            "--fleet-ca", "C:\\neta-state\\fleet-ca.crt",
            "--token", token,
            "--fleet-id", enrollment.fleet_id,
            "--display-name", endpoint.hostname,
            "--state-dir", "C:\\neta-state\\identity",
        ]
        SupervisorChannel(endpoint.state_dir).request(
            "agent-command", {"arguments": arguments}, timeout_seconds=120.0)
        endpoint.agent_id = self._agent_id(endpoint.identity_dir)
        if not endpoint.agent_id:
            raise RuntimeError(f"production enrollment did not create AgentId for {endpoint.slot}")

    def up(self, count: int, enrollment: EnrollmentConfig | None = None) -> list[WindowsEndpointState]:
        if count < 1 or count > 500:
            raise RuntimeError("Windows Phase 3 endpoint count must be in 1..500")
        self.runtime.preflight()
        if not self.config.agent_binary.exists():
            raise RuntimeError(f"neta-agent.exe not found: {self.config.agent_binary}")
        if enrollment is None and not self.config.allow_unenrolled:
            raise RuntimeError("real enrollment is required unless --allow-unenrolled is explicitly selected")

        self.config.state_root.mkdir(parents=True, exist_ok=True)
        self.config.runtime_root.mkdir(parents=True, exist_ok=True)
        network_owned = self.runtime.ensure_nat_network(self.config.docker_network, self.config.subnet)
        bootstrap = self._start_pipe_bootstrap()
        endpoints: list[WindowsEndpointState] = []
        try:
            for index in range(1, count + 1):
                endpoint, _ = self._endpoint(index)
                self.runtime.create_container(
                    name=endpoint.container_name,
                    hostname=endpoint.hostname,
                    network=self.config.docker_network,
                    image=self.config.container_image,
                    state_dir=endpoint.state_dir,
                    repo_root=self.repo_root,
                    agent_binary=self.config.agent_binary,
                    pipe_name=self.config.pipe_name,
                    slot=endpoint.slot,
                    environment=self._environment(),
                )
                if not self.runtime.is_running(endpoint.container_name):
                    self.runtime.start_container(endpoint.container_name)
                SupervisorChannel(endpoint.state_dir).wait_ready()
                endpoint.container_id, endpoint.root_pid, endpoint.ip_address = self.runtime.inspect_endpoint(
                    endpoint.container_name, self.config.docker_network)
                endpoint.agent_id = self._agent_id(endpoint.identity_dir)
                self.store.save(endpoint)
                endpoints.append(endpoint)
        finally:
            self._stop_process(bootstrap)

        broker = self._start_broker(endpoints)
        try:
            for endpoint in endpoints:
                if enrollment is not None:
                    self._enroll(endpoint, enrollment)
                self.store.save(endpoint)
                SupervisorChannel(endpoint.state_dir).request(
                    "start-agent",
                    {"duration_seconds": self.config.agent_duration_seconds,
                     "poll_ms": self.config.agent_poll_ms,
                     "max_db_mb": self.config.max_db_mb},
                    timeout_seconds=30.0,
                )
            self._save_runtime(endpoints=endpoints, broker_pid=broker.pid, network_owned=network_owned)
            return endpoints
        except Exception:
            self._terminate_pid(broker.pid)
            raise

    @staticmethod
    def _terminate_pid(pid: int) -> None:
        if pid <= 0:
            return
        subprocess.run(["taskkill.exe", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    @staticmethod
    def _pid_running(pid: int) -> bool:
        if pid <= 0:
            return False
        result = subprocess.run(
            ["tasklist.exe", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        return result.returncode == 0 and f'"{pid}"' in result.stdout

    def down(self, *, purge_state: bool = False) -> None:
        runtime = self._load_runtime()
        broker_pid = int(runtime.get("broker_pid", 0))
        for endpoint in self.store.load_all():
            if self.runtime.container_exists(endpoint.container_name):
                try:
                    SupervisorChannel(endpoint.state_dir).request("shutdown", timeout_seconds=5.0)
                except Exception:
                    pass
                self.runtime.stop_container(endpoint.container_name)
                self.runtime.remove_container(endpoint.container_name)
        self._terminate_pid(broker_pid)
        if runtime.get("network_owned"):
            self.runtime.remove_network(str(runtime.get("network", self.config.docker_network)))
        shutil.rmtree(self.config.runtime_root, ignore_errors=True)
        if purge_state:
            shutil.rmtree(self.config.state_root, ignore_errors=True)

    def status(self) -> dict[str, Any]:
        runtime = self._load_runtime()
        broker_pid = int(runtime.get("broker_pid", 0))
        endpoints = []
        for endpoint in self.store.load_all():
            running = self.runtime.container_exists(endpoint.container_name) and self.runtime.is_running(endpoint.container_name)
            endpoints.append({
                "slot": endpoint.slot,
                "container": endpoint.container_name,
                "running": running,
                "ip_address": endpoint.ip_address,
                "root_pid": endpoint.root_pid,
                "agent_id": self._agent_id(endpoint.identity_dir),
                "database_bytes": endpoint.database.stat().st_size if endpoint.database.exists() else 0,
            })
        return {"broker_pid": broker_pid, "broker_running": self._pid_running(broker_pid), "endpoints": endpoints}

    def scenario_runner(self) -> WindowsScenarioRunner:
        gateway = self.runtime.network_gateway(self.config.docker_network)
        return WindowsScenarioRunner(repo_root=self.repo_root, gateway=gateway, ground_truth=self.ground_truth)

    def persona_map(self) -> dict[str, Persona]:
        return {persona.id: persona for persona in self.personas.catalog}

    def run_scenario(self, slot: str, scenario_id: str,
                     parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        endpoint = self.store.load(slot)
        if endpoint is None:
            raise RuntimeError(f"unknown Windows endpoint slot: {slot}")
        persona = self.persona_map()[endpoint.persona_id]
        return self.scenario_runner().run(endpoint, persona, scenario_id, parameters)

    def schedule(self, duration_seconds: float) -> list[dict[str, Any]]:
        endpoints = self.store.load_all()
        personas = self.persona_map()
        plan = WindowsScenarioScheduler(self.config.seed).plan(endpoints, personas, duration_seconds)
        runner = self.scenario_runner()
        started = time.monotonic()
        results: list[dict[str, Any]] = []
        for item in plan:
            delay = started + item.due_offset_seconds - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            endpoint = next(value for value in endpoints if value.slot == item.endpoint_slot)
            results.append(runner.run(endpoint, personas[endpoint.persona_id], item.scenario_id, item.parameters))
        return results
