from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from fleet.model import EndpointState, FleetConfig, ProcessRecord, RuntimeState
from fleet.linux.endpoint_host import LinuxEndpointHost
from fleet.linux.egress import LinuxEgressManager
from fleet.linux.process_launcher import ProcessLauncher
from .command import CommandRunner, atomic_write_text
from .ground_truth import GroundTruthRecorder
from .health_monitor import HealthMonitor
from .identity_manager import EnrollmentConfig, IdentityManager
from .lease_manager import LeaseManager
from .persona import PersonaStore
from .scenario_scheduler import ScenarioRunner, ScenarioScheduler


class FleetManager:
    def __init__(self, *, repo_root: Path, config: FleetConfig,
                 persona_dir: Path | None = None, runner: CommandRunner | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.config = config
        self.runner = runner or CommandRunner()
        self.config.state_root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.config.state_root, 0o700)
        self.config.runtime_root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.config.runtime_root, 0o700)
        self.leases = LeaseManager(self.config.state_root / "leases.json",
                                   self.config.subnet, self.config.gateway, self.config.seed)
        self.personas = PersonaStore(persona_dir or self.repo_root / "fleet/personas", self.config.seed)
        self.host = LinuxEndpointHost(config=self.config, runner=self.runner,
                                      leases=self.leases, personas=self.personas)
        self.identity = IdentityManager(self.config, self.host.launcher)
        self.egress = LinuxEgressManager(
            self.runner, state_file=self.config.state_root / "network-egress.json",
            fleet_name=self.config.name, subnet=self.config.subnet, bridge=self.config.bridge,
        )
        self.ground_truth = GroundTruthRecorder(self.config.state_root / "ground-truth" / "runs.jsonl")
        self.scenario_runner = ScenarioRunner(
            repo_root=self.repo_root,
            command_runner=self.runner,
            launcher=self.host.launcher,
            ground_truth=self.ground_truth,
            gateway=self.config.gateway,
        )
        self.runtime_file = self.config.runtime_root / "runtime.json"

    @staticmethod
    def _process_from_dict(data: dict[str, Any]) -> ProcessRecord:
        return ProcessRecord(int(data["pid"]), int(data["start_ticks"]),
                             str(data["kind"]), data.get("slot"))

    def _load_runtime(self) -> RuntimeState:
        if not self.runtime_file.exists():
            return RuntimeState()
        data = json.loads(self.runtime_file.read_text(encoding="utf-8"))
        return RuntimeState(
            broker=self._process_from_dict(data["broker"]) if data.get("broker") else None,
            peer_processes=[self._process_from_dict(x) for x in data.get("peer_processes", [])],
            endpoint_processes={
                slot: [self._process_from_dict(x) for x in records]
                for slot, records in data.get("endpoint_processes", {}).items()
            },
        )

    def _save_runtime(self, runtime: RuntimeState) -> None:
        atomic_write_text(self.runtime_file, json.dumps(runtime.to_dict(), indent=2, sort_keys=True) + "\n")

    @staticmethod
    def _endpoint_from_dict(data: dict[str, Any]) -> EndpointState:
        return EndpointState(
            slot=str(data["slot"]), index=int(data["index"]), hostname=str(data["hostname"]),
            persona_id=str(data["persona_id"]), tenant=str(data.get("tenant", "lab-default")),
            ip_address=str(data["ip_address"]), prefix_length=int(data["prefix_length"]),
            netns_name=str(data["netns_name"]), host_veth=str(data["host_veth"]),
            peer_veth=str(data["peer_veth"]), cgroup_path=Path(data["cgroup_path"]),
            state_dir=Path(data["state_dir"]), identity_dir=Path(data["identity_dir"]),
            database=Path(data["database"]), netns_inode=int(data.get("netns_inode", 0)),
            cgroup_id=int(data.get("cgroup_id", 0)), uts_keeper_pid=data.get("uts_keeper_pid"),
            agent_pid=data.get("agent_pid"), agent_id=data.get("agent_id"),
        )

    def endpoints(self) -> list[EndpointState]:
        endpoints: list[EndpointState] = []
        root = self.config.state_root / "endpoints"
        if not root.exists():
            return endpoints
        manifest_path = self.config.state_root / "fleet.json"
        active_slots: set[str] | None = None
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                active_slots = {str(item["slot"]) for item in manifest.get("endpoints", [])}
            except (json.JSONDecodeError, KeyError, TypeError):
                active_slots = None
        for path in sorted(root.glob("*/endpoint.json")):
            if active_slots is not None and path.parent.name not in active_slots:
                continue
            endpoints.append(self._endpoint_from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return endpoints

    def _persist_endpoint(self, state: EndpointState) -> None:
        atomic_write_text(state.state_dir / "endpoint.json",
                          json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n")

    def _start_broker(self, endpoints: list[EndpointState], runtime: RuntimeState) -> None:
        socket_path = self.config.runtime_root / "sensor-broker.sock"
        socket_path.unlink(missing_ok=True)
        command = [str(self.config.agent_binary.resolve()), "sensor-broker",
                   "--socket", str(socket_path), "--queue-capacity", str(self.config.queue_capacity)]
        for endpoint in endpoints:
            command += ["--map", f"{endpoint.slot}:{endpoint.netns_inode}:{endpoint.cgroup_id}"]
        log_path = self.config.state_root / "broker.log"
        log = log_path.open("a", encoding="utf-8")
        proc = self.runner.popen(command, stdout=log, stderr=subprocess.STDOUT)
        record = ProcessRecord(proc.pid, ProcessLauncher.process_start_ticks(proc.pid), "broker")
        runtime.broker = record
        self._save_runtime(runtime)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"sensor broker exited early; see {log_path}")
            if socket_path.exists():
                return
            time.sleep(0.05)
        raise RuntimeError("sensor broker did not create its socket within 10 seconds")

    def _agent_environment(self, endpoint: EndpointState) -> dict[str, str]:
        env = os.environ.copy()
        env.update({
            "NETA_SENSOR_MODE": "broker",
            "NETA_ENDPOINT_SLOT": endpoint.slot,
            "NETA_SENSOR_BROKER": str(self.config.runtime_root / "sensor-broker.sock"),
            "NETA_FLEET_STATE_DIR": str(endpoint.identity_dir),
            "NETA_FLEET_REPORTING_MODE": self.config.reporting_mode,
            "NETA_FLEET_MIN_CONFIDENCE": str(self.config.min_confidence),
            "NETA_FLEET_REPORTING_COOLDOWN_SECONDS": str(self.config.reporting_cooldown_seconds),
            "NETA_FLEET_HEARTBEAT_SECONDS": str(self.config.heartbeat_seconds),
            "NETA_FLEET_HEARTBEAT_JITTER_PERCENT": str(self.config.heartbeat_jitter_percent),
        })
        return env

    def _start_agent(self, endpoint: EndpointState, runtime: RuntimeState) -> EndpointState:
        context = self.host.process_context(endpoint)
        command = [
            str(self.config.agent_binary.resolve()), "observe", "--all",
            "--duration", str(self.config.agent_duration_seconds),
            "--poll-ms", str(self.config.agent_poll_ms),
            "--db", str(endpoint.database),
            "--max-db-mb", str(self.config.max_db_mb),
        ]
        log_path = endpoint.state_dir / "logs" / "agent.log"
        log = log_path.open("a", encoding="utf-8")
        process, record = self.host.launcher.popen(
            command, context=context, env=self._agent_environment(endpoint),
            cwd=self.repo_root, stdout=log, stderr=subprocess.STDOUT,
        )
        agent_record = ProcessRecord(record.pid, record.start_ticks, "agent", endpoint.slot)
        runtime.endpoint_processes.setdefault(endpoint.slot, [])
        runtime.endpoint_processes[endpoint.slot] = [
            x for x in runtime.endpoint_processes[endpoint.slot] if x.kind != "agent"
        ] + [agent_record]
        updated = replace(endpoint, agent_pid=process.pid)
        self._persist_endpoint(updated)
        self._save_runtime(runtime)
        time.sleep(0.05)
        if process.poll() is not None:
            raise RuntimeError(f"agent for {endpoint.slot} exited early; see {log_path}")
        return updated

    def up(self, count: int, enrollment: EnrollmentConfig | None = None) -> list[EndpointState]:
        if count <= 0:
            raise ValueError("endpoint count must be positive")
        if count > 500:
            raise ValueError("Phase 2 is intentionally capped at 500 Linux endpoints")
        existing_runtime = self._load_runtime()
        if existing_runtime.broker and ProcessLauncher.alive(existing_runtime.broker):
            raise RuntimeError("fleet is already running; use status/down/recover")
        self.host.validate()
        runtime = RuntimeState()
        endpoints: list[EndpointState] = []
        try:
            self.host.network.ensure_bridge()
            if self.config.enable_nat:
                self.egress.enable()
            for index in range(1, count + 1):
                state = self.host.prepare(index)
                state, keeper = self.host.create_kernel_environment(state)
                runtime.endpoint_processes[state.slot] = [
                    ProcessRecord(keeper.pid, keeper.start_ticks, "uts-keeper", state.slot)
                ]
                self._save_runtime(runtime)
                endpoints.append(state)

            netns_values = {e.netns_inode for e in endpoints}
            cgroup_values = {e.cgroup_id for e in endpoints}
            if len(netns_values) != len(endpoints) or len(cgroup_values) != len(endpoints):
                raise RuntimeError("kernel endpoint attribution IDs are not unique")

            enrolled: list[EndpointState] = []
            for state in endpoints:
                agent_id = self.identity.ensure_enrolled(state, self.host.process_context(state), enrollment)
                state = replace(state, agent_id=agent_id)
                self._persist_endpoint(state)
                enrolled.append(state)
            endpoints = enrolled
            self.identity.validate_unique(endpoints, require_all=not self.config.allow_unenrolled)

            self._start_broker(endpoints, runtime)
            endpoints = [self._start_agent(endpoint, runtime) for endpoint in endpoints]
            manifest = {
                "version": 1,
                "count": len(endpoints),
                "seed": self.config.seed,
                "bridge": self.config.bridge,
                "subnet": self.config.subnet,
                "gateway": self.config.gateway,
                "endpoints": [endpoint.to_dict() for endpoint in endpoints],
            }
            atomic_write_text(self.config.state_root / "fleet.json",
                              json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            return endpoints
        except Exception:
            self._cleanup_partial(endpoints, runtime)
            raise

    def _cleanup_stale_scenario_peers(self) -> None:
        root = self.config.state_root / "endpoints"
        if not root.exists():
            return
        for record_file in root.glob("*/scenarios/*/peer-process.json"):
            try:
                data = json.loads(record_file.read_text(encoding="utf-8"))
                record = ProcessRecord(int(data["pid"]), int(data["start_ticks"]),
                                       str(data.get("kind", "scenario-peer")))
                ProcessLauncher.terminate(record)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
            record_file.unlink(missing_ok=True)

    def _cleanup_partial(self, endpoints: list[EndpointState], runtime: RuntimeState) -> None:
        self._cleanup_stale_scenario_peers()
        for records in runtime.endpoint_processes.values():
            for record in records:
                if record.kind == "agent":
                    ProcessLauncher.terminate(record)
        if runtime.broker:
            ProcessLauncher.terminate(runtime.broker)
        for endpoint in reversed(endpoints):
            self.host.cleanup_kernel_environment(endpoint)
        self.host.network.delete_bridge()
        if self.config.enable_nat:
            self.egress.disable()
        self.runtime_file.unlink(missing_ok=True)

    def stop_agents_and_broker(self) -> None:
        runtime = self._load_runtime()
        for slot, records in runtime.endpoint_processes.items():
            for record in records:
                if record.kind == "agent":
                    ProcessLauncher.terminate(record)
            runtime.endpoint_processes[slot] = [x for x in records if x.kind != "agent"]
        if runtime.broker:
            ProcessLauncher.terminate(runtime.broker)
            runtime.broker = None
        self._save_runtime(runtime)

    def down(self, *, purge_state: bool = False) -> None:
        self._cleanup_stale_scenario_peers()
        runtime = self._load_runtime()
        endpoints = self.endpoints()
        for records in runtime.endpoint_processes.values():
            for record in records:
                if record.kind == "agent":
                    ProcessLauncher.terminate(record)
        if runtime.broker:
            ProcessLauncher.terminate(runtime.broker)
        for endpoint in reversed(endpoints):
            self.host.cleanup_kernel_environment(endpoint)
        self.host.network.delete_bridge()
        if self.config.enable_nat or (self.config.state_root / "network-egress.json").exists():
            self.egress.disable()
        self.host.cgroups.remove_root_if_empty()
        self.runtime_file.unlink(missing_ok=True)
        try:
            (self.config.runtime_root / "sensor-broker.sock").unlink()
        except FileNotFoundError:
            pass
        if purge_state:
            shutil.rmtree(self.config.state_root, ignore_errors=True)

    def restart_endpoint(self, slot: str, *, rotate_ip: bool) -> EndpointState:
        endpoints = {endpoint.slot: endpoint for endpoint in self.endpoints()}
        if slot not in endpoints:
            raise RuntimeError(f"unknown endpoint slot: {slot}")
        state = endpoints[slot]
        runtime = self._load_runtime()
        records = runtime.endpoint_processes.get(slot, [])
        for record in records:
            if record.kind == "agent":
                ProcessLauncher.terminate(record)
        runtime.endpoint_processes[slot] = [x for x in records if x.kind != "agent"]
        if rotate_ip:
            state = self.host.rotate_ip(state)
        state = self._start_agent(state, runtime)
        lifecycle = {
            "record_type": "endpoint_restart",
            "timestamp": self.ground_truth.now(),
            "endpoint_slot": slot,
            "agent_id": state.agent_id,
            "ip_address": state.ip_address,
            "ip_rotated": rotate_ip,
        }
        self.ground_truth._append(self.config.state_root / "ground-truth" / "lifecycle.jsonl", lifecycle)
        self.ground_truth._append(state.state_dir / "ground-truth.jsonl", lifecycle)
        return state

    def recover(self, count: int, enrollment: EnrollmentConfig | None = None) -> list[EndpointState]:
        # Kernel objects and PIDs are disposable; personas, leases, DBs and enrolled
        # identity directories are intentionally persistent.
        try:
            self.down(purge_state=False)
        except Exception:
            # Continue with named-resource recreation even after an unclean host exit.
            pass
        return self.up(count, enrollment)

    def status(self) -> dict[str, Any]:
        runtime = self._load_runtime()
        monitor = HealthMonitor(self.host.network)
        endpoint_health = [
            monitor.endpoint(endpoint, runtime.endpoint_processes.get(endpoint.slot, []))
            for endpoint in self.endpoints()
        ]
        broker_alive = bool(runtime.broker and ProcessLauncher.alive(runtime.broker))
        return {
            "broker_alive": broker_alive,
            "endpoint_count": len(endpoint_health),
            "healthy_endpoints": sum(1 for item in endpoint_health if item.healthy),
            "endpoints": [item.to_dict() for item in endpoint_health],
        }

    def run_scenario(self, slot: str, scenario_id: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        endpoint = next((x for x in self.endpoints() if x.slot == slot), None)
        if endpoint is None:
            raise RuntimeError(f"unknown endpoint slot: {slot}")
        persona = next(p for p in self.personas.catalog if p.id == endpoint.persona_id)
        return self.scenario_runner.run(endpoint, persona, self.host.process_context(endpoint),
                                        scenario_id, parameters)

    def schedule(self, duration_seconds: float) -> list[dict[str, Any]]:
        endpoints = self.endpoints()
        personas = {persona.id: persona for persona in self.personas.catalog}
        scheduler = ScenarioScheduler(seed=self.config.seed,
                                      max_concurrent=self.config.scenario_max_concurrent)
        plan = scheduler.plan(endpoints, personas, duration_seconds)
        return scheduler.execute(
            plan,
            endpoints={endpoint.slot: endpoint for endpoint in endpoints},
            personas=personas,
            context_for=self.host.process_context,
            runner=self.scenario_runner,
        )

    @staticmethod
    def _connection_count(database: Path, remote_ip: str, remote_port: int) -> int:
        if not database.exists():
            return 0
        with sqlite3.connect(database) as db:
            try:
                row = db.execute(
                    "SELECT COUNT(*) FROM connections WHERE remote_ip=? AND remote_port=?",
                    (remote_ip, remote_port),
                ).fetchone()
                return int(row[0]) if row else 0
            except sqlite3.Error:
                return 0

    def acceptance(self, enrollment: EnrollmentConfig | None = None) -> dict[str, Any]:
        self.runner.require("curl")
        endpoints: list[EndpointState] = []
        try:
            endpoints = self.up(3, enrollment)
            by_slot = {endpoint.slot: endpoint for endpoint in endpoints}
            middle = self.host.slot(2)
            result = self.run_scenario(middle, "001", {"count": 5, "interval_seconds": 0.25})
            time.sleep(1.0)
            port = int(result["parameters"]["port"])
            counts = {
                slot: self._connection_count(endpoint.database, self.config.gateway, port)
                for slot, endpoint in by_slot.items()
            }
            passed = result["result"] == "PASS" and counts[middle] > 0 and all(
                count == 0 for slot, count in counts.items() if slot != middle
            )
            identity_ids = [e.agent_id for e in endpoints if e.agent_id]
            if not self.config.allow_unenrolled:
                passed = passed and len(identity_ids) == 3 and len(set(identity_ids)) == 3
            report = {
                "passed": passed,
                "scenario_result": result["result"],
                "target_slot": middle,
                "target_port": port,
                "connection_counts": counts,
                "unique_netns": len({e.netns_inode for e in endpoints}) == 3,
                "unique_cgroups": len({e.cgroup_id for e in endpoints}) == 3,
                "unique_agent_ids": len(identity_ids) == len(set(identity_ids)),
                "enrolled_count": len(identity_ids),
            }
            atomic_write_text(self.config.state_root / "acceptance.json",
                              json.dumps(report, indent=2, sort_keys=True) + "\n")
            if not passed:
                raise RuntimeError("Phase 2 endpoint-isolation acceptance failed: " + json.dumps(report))
            return report
        finally:
            if endpoints or self.runtime_file.exists():
                self.down(purge_state=False)
