from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from fleet.model import Persona
from fleet.windows.command_channel import SupervisorChannel
from fleet.windows.docker_runtime import DockerWindowsRuntime
from fleet.windows.model import WindowsEndpointState, WindowsFleetConfig
from fleet.windows.scheduler import WindowsScenarioScheduler


class CapturingDockerRuntime(DockerWindowsRuntime):
    def __init__(self) -> None:
        super().__init__("docker")
        self.commands: list[list[str]] = []

    def _run(self, args: list[str], *, check: bool = True):
        self.commands.append(list(args))
        if args[:1] == ["inspect"]:
            return mock.Mock(returncode=1, stdout="", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")


class Phase3WindowsFleetTests(unittest.TestCase):
    def test_config_defaults_and_override(self) -> None:
        config = WindowsFleetConfig.from_dict({"endpoint_prefix": "w", "queue_capacity": 77})
        self.assertEqual(config.endpoint_prefix, "w")
        self.assertEqual(config.queue_capacity, 77)
        self.assertEqual(config.pipe_name, "neta-sensor-broker")
        self.assertIn("servercore", config.container_image)

    def test_endpoint_round_trip(self) -> None:
        endpoint = WindowsEndpointState(
            slot="win-0002", index=2, hostname="dev-win-0002",
            persona_id="windows-developer-workstation", tenant="tenant-engineering",
            container_name="neta-win-0002", container_id="abc", root_pid=1234,
            ip_address="172.30.0.10", state_dir=Path("state"),
            identity_dir=Path("state/identity"), database=Path("state/neta.db"),
            agent_id="agent-2",
        )
        decoded = WindowsEndpointState.from_dict(endpoint.to_dict())
        self.assertEqual(decoded.slot, endpoint.slot)
        self.assertEqual(decoded.root_pid, 1234)
        self.assertEqual(decoded.agent_id, "agent-2")

    def test_scheduler_is_seeded_and_endpoint_specific(self) -> None:
        persona = Persona(
            id="windows-test", role="test", platform="windows", hostname_prefix="win",
            activity="medium", working_hours="always", normal_apps=(),
            scenario_rate_per_hour=3600.0,
            scenario_weights={"001": 4.0, "006": 1.0},
            threat_scenario_probability=0.2,
        )
        endpoints = [
            WindowsEndpointState(
                slot=f"win-{index:04d}", index=index, hostname=f"win-{index:04d}",
                persona_id=persona.id, tenant="t", container_name=f"c{index}",
                container_id=str(index), root_pid=1000 + index, ip_address=f"172.30.0.{index}",
                state_dir=Path(f"s{index}"), identity_dir=Path(f"s{index}/identity"),
                database=Path(f"s{index}/neta.db"),
            ) for index in (1, 2)
        ]
        scheduler = WindowsScenarioScheduler(12345)
        first = scheduler.plan(endpoints, {persona.id: persona}, 2.0)
        second = scheduler.plan(endpoints, {persona.id: persona}, 2.0)
        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertTrue(all(item.endpoint_slot in {"win-0001", "win-0002"} for item in first))

    def test_docker_create_uses_process_isolation_and_named_pipe(self) -> None:
        runtime = CapturingDockerRuntime()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            agent = root / "agent" / "neta-agent.exe"
            agent.parent.mkdir()
            agent.write_text("placeholder", encoding="utf-8")
            repo = root / "repo"
            repo.mkdir()
            runtime.create_container(
                name="neta-win-0001", hostname="win-0001", network="neta-sim-win",
                image="servercore:test", state_dir=root / "state", repo_root=repo,
                agent_binary=agent, pipe_name="neta-sensor-broker", slot="win-0001",
                environment={"NETA_FLEET_STATE_DIR": "C:\\neta-state\\identity"},
            )
        command = runtime.commands[-1]
        self.assertIn("--isolation=process", " ".join(command))
        self.assertIn("type=npipe", " ".join(command))
        self.assertIn("NETA_SENSOR_MODE=broker", command)
        self.assertIn("NETA_ENDPOINT_SLOT=win-0001", command)

    def test_supervisor_channel_atomic_request_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            endpoint = Path(temp)
            channel = SupervisorChannel(endpoint)

            def responder() -> None:
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    files = list(channel.commands_dir.glob("*.json"))
                    if files:
                        command = json.loads(files[0].read_text(encoding="utf-8"))
                        response = channel.responses_dir / f"{command['id']}.json"
                        response.write_text(json.dumps({"id": command["id"], "status": "ok", "value": 7}), encoding="utf-8")
                        files[0].unlink()
                        return
                    time.sleep(0.01)

            worker = threading.Thread(target=responder)
            worker.start()
            result = channel.request("test", timeout_seconds=2.0)
            worker.join()
            self.assertEqual(result["value"], 7)


if __name__ == "__main__":
    unittest.main()
