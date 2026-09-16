from __future__ import annotations

import hashlib
import json
import os
import random
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fleet.model import EndpointState, Persona
from fleet.linux.process_launcher import ProcessLauncher
from .command import CommandRunner, atomic_write_text
from .ground_truth import GroundTruthRecorder


THREAT_SCENARIOS = {"001", "002", "004", "005", "006", "007", "015", "024", "025"}


@dataclass(frozen=True)
class ScheduledScenario:
    due_offset_seconds: float
    endpoint_slot: str
    scenario_id: str
    parameters: dict[str, Any]


class PortAllocator:
    def __init__(self, bind_address: str, low: int = 20000, high: int = 45000) -> None:
        self.bind_address = bind_address
        self.low = low
        self.high = high
        self._lock = threading.Lock()
        self._allocated: set[int] = set()

    def acquire(self, key: str) -> int:
        digest = hashlib.sha256(key.encode()).digest()
        start = self.low + int.from_bytes(digest[:4], "big") % (self.high - self.low + 1)
        with self._lock:
            for offset in range(self.high - self.low + 1):
                port = self.low + ((start - self.low + offset) % (self.high - self.low + 1))
                if port in self._allocated:
                    continue
                family = socket.AF_INET6 if ":" in self.bind_address else socket.AF_INET
                with socket.socket(family, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind((self.bind_address, port))
                    except OSError:
                        continue
                self._allocated.add(port)
                return port
        raise RuntimeError("no free controlled-peer port available")

    def release(self, port: int) -> None:
        with self._lock:
            self._allocated.discard(port)


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

    def linux_script(self, scenario_id: str) -> Path:
        script = self.directory(scenario_id) / "linux" / "run.sh"
        if not script.exists():
            raise RuntimeError(f"NETA-LAB-{scenario_id.zfill(3)} has no Linux run.sh")
        return script

    def expected(self, scenario_id: str) -> Path:
        return self.directory(scenario_id) / "expected.yaml"


class ScenarioRunner:
    """Runs existing benign NETA-LAB scenarios inside one endpoint context."""

    def __init__(self, *, repo_root: Path, command_runner: CommandRunner,
                 launcher: ProcessLauncher, ground_truth: GroundTruthRecorder,
                 gateway: str) -> None:
        self.repo_root = repo_root
        self.command_runner = command_runner
        self.launcher = launcher
        self.ground_truth = ground_truth
        self.gateway = gateway
        self.catalog = ScenarioCatalog(repo_root)
        self.ports = PortAllocator(gateway)

    def _start_peer(self, scenario_id: str, port: int, parameters: dict[str, Any], log: Path, target_host: str):
        log.parent.mkdir(parents=True, exist_ok=True)
        handle = log.open("a", encoding="utf-8")
        sid = scenario_id.zfill(3)
        if target_host != self.gateway:
            handle.close()
            return None, None
        if sid == "001":
            command = ["python3", str(self.repo_root / "common/server/beacon_server.py"),
                       "--bind", self.gateway, "--port", str(port)]
        elif sid in {"008", "014", "015"}:
            if sid == "008":
                connections = 5
            else:
                connections = int(parameters.get("count", 100 if sid == "014" else 250))
            # Add one connection for the readiness probe below; the scenario
            # then supplies exactly its normal bounded connection count.
            command = ["python3", str(self.repo_root / "common/server/tcp_lab_server.py"),
                       "--bind", self.gateway, "--port", str(port),
                       "--connections", str(connections + 1), "--scenario", f"NETA-LAB-{sid}"]
        else:
            return None, None
        proc = self.command_runner.popen(command, stdout=handle, stderr=subprocess.STDOUT)
        peer_record = {
            "pid": proc.pid,
            "start_ticks": ProcessLauncher.process_start_ticks(proc.pid),
            "kind": "scenario-peer",
        }
        atomic_write_text(log.parent / "peer-process.json", json.dumps(peer_record, sort_keys=True) + "\n")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"controlled peer for NETA-LAB-{sid} exited early")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.1)
                if sock.connect_ex((self.gateway, port)) == 0:
                    break
            time.sleep(0.05)
        else:
            proc.terminate()
            raise RuntimeError(f"controlled peer for NETA-LAB-{sid} did not become ready")
        return proc, handle

    def _scenario_args(self, scenario_id: str, target_host: str, port: int, parameters: dict[str, Any]) -> list[str]:
        sid = scenario_id.zfill(3)
        if sid == "001":
            return [target_host, str(port), str(parameters.get("count", 6)),
                    str(parameters.get("interval_seconds", 1))]
        if sid == "008":
            return [target_host, str(port)]
        if sid == "014":
            return [target_host, str(port), str(parameters.get("count", 40))]
        if sid == "015":
            return [target_host, str(port), str(parameters.get("count", 100)),
                    str(parameters.get("parallel", 10))]
        custom = parameters.get("args")
        if isinstance(custom, list):
            return [str(x) for x in custom]
        raise RuntimeError(
            f"NETA-LAB-{sid} is not auto-wired for the fleet scheduler; provide parameters.args"
        )

    def run(self, endpoint: EndpointState, persona: Persona, context, scenario_id: str,
            parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        parameters = dict(parameters or {})
        sid = scenario_id.zfill(3)
        script = self.catalog.linux_script(sid)
        target_host = str(parameters.get("target_host", self.gateway))
        defaults = {"001": 18080, "008": 18448, "014": 18454, "015": 18455}
        allocated = False
        if "port" in parameters:
            port = int(parameters["port"])
        elif target_host == self.gateway and sid in defaults:
            port = self.ports.acquire(f"{endpoint.slot}:{time.time_ns()}:{sid}")
            allocated = True
        elif sid in defaults:
            port = defaults[sid]
        else:
            raise RuntimeError("non-auto-wired scenarios require parameters.port and parameters.args")
        parameters["target_host"] = target_host
        parameters["port"] = port
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
        peer = peer_log_handle = None
        exit_code = 1
        result_name = "FAILED"
        details: dict[str, Any] = {"output_dir": str(output_dir)}
        try:
            peer, peer_log_handle = self._start_peer(sid, port, parameters, output_dir / "peer.log", target_host)
            args = self._scenario_args(sid, target_host, port, parameters)
            env = os.environ.copy()
            env.update({"NETA_LAB_OUTPUT_DIR": str(output_dir)})
            command = ["bash", str(script), *args]
            completed = self.launcher.run(command, context=context, env=env,
                                          cwd=self.repo_root, check=False)
            exit_code = completed.returncode
            (output_dir / "scenario.stdout.log").write_text(completed.stdout, encoding="utf-8")
            (output_dir / "scenario.stderr.log").write_text(completed.stderr, encoding="utf-8")
            result_name = "PASS" if exit_code == 0 else "FAIL"
            details.update({"stdout_log": str(output_dir / "scenario.stdout.log"),
                            "stderr_log": str(output_dir / "scenario.stderr.log")})
        except Exception as exc:
            details["error"] = str(exc)
            result_name = "ERROR"
        finally:
            if peer is not None:
                try:
                    if sid == "001" and peer.poll() is None:
                        peer.terminate()
                    peer.wait(timeout=5)
                except Exception:
                    try:
                        peer.kill()
                    except Exception:
                        pass
            if peer_log_handle is not None:
                peer_log_handle.close()
            (output_dir / "peer-process.json").unlink(missing_ok=True)
            if allocated:
                self.ports.release(port)
        return self.ground_truth.finish_run(
            endpoint.state_dir / "ground-truth.jsonl", started,
            exit_code=exit_code, result=result_name, details=details,
        )


class ScenarioScheduler:
    def __init__(self, *, seed: int, max_concurrent: int) -> None:
        self.seed = seed
        self.max_concurrent = max_concurrent

    @staticmethod
    def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
        items = [(sid.zfill(3), weight) for sid, weight in weights.items() if weight > 0]
        if not items:
            raise RuntimeError("persona has no positive scenario weights")
        total = sum(weight for _, weight in items)
        pick = rng.random() * total
        upto = 0.0
        for sid, weight in items:
            upto += weight
            if pick <= upto:
                return sid
        return items[-1][0]

    def plan(self, endpoints: list[EndpointState], personas: dict[str, Persona],
             duration_seconds: float) -> list[ScheduledScenario]:
        rng = random.Random(self.seed)
        plan: list[ScheduledScenario] = []
        for endpoint in sorted(endpoints, key=lambda item: item.slot):
            persona = personas[endpoint.persona_id]
            rate_per_second = persona.scenario_rate_per_hour / 3600.0
            if rate_per_second <= 0 or not persona.scenario_weights:
                continue
            offset = rng.expovariate(rate_per_second)
            while offset < duration_seconds:
                available = dict(persona.scenario_weights)
                wants_threat = rng.random() < persona.threat_scenario_probability
                filtered = {sid: weight for sid, weight in available.items()
                            if ((sid.zfill(3) in THREAT_SCENARIOS) == wants_threat)}
                if not filtered:
                    filtered = available
                sid = self._weighted_choice(rng, filtered)
                params: dict[str, Any] = {"jitter_seconds": round(rng.uniform(0.0, 2.0), 3)}
                if sid == "001":
                    params.update({"count": rng.randint(4, 10), "interval_seconds": rng.randint(1, 4)})
                elif sid == "014":
                    params["count"] = rng.randint(20, 80)
                elif sid == "015":
                    params.update({"count": rng.randint(50, 160), "parallel": rng.randint(5, 16)})
                plan.append(ScheduledScenario(offset + float(params["jitter_seconds"]), endpoint.slot, sid, params))
                offset += rng.expovariate(rate_per_second)
        return sorted(plan, key=lambda item: (item.due_offset_seconds, item.endpoint_slot, item.scenario_id))

    def execute(self, plan: list[ScheduledScenario], *, endpoints: dict[str, EndpointState],
                personas: dict[str, Persona], context_for, runner: ScenarioRunner) -> list[dict[str, Any]]:
        started = time.monotonic()
        futures = []
        with ThreadPoolExecutor(max_workers=self.max_concurrent, thread_name_prefix="neta-scenario") as pool:
            for item in plan:
                delay = started + item.due_offset_seconds - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                endpoint = endpoints[item.endpoint_slot]
                futures.append(pool.submit(runner.run, endpoint, personas[endpoint.persona_id],
                                           context_for(endpoint), item.scenario_id, item.parameters))
            results = [future.result() for future in as_completed(futures)]
        return results
