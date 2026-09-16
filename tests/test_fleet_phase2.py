from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fleet.model import EndpointState, Persona
from fleet.linux.network import LinuxNetworkManager
from fleet.linux.egress import LinuxEgressManager
from fleet.orchestrator.command import CommandResult
from fleet.linux.process_launcher import NamespaceContext, ProcessLauncher
from fleet.orchestrator.ground_truth import GroundTruthRecorder
from fleet.orchestrator.identity_manager import EnrollmentConfig
from fleet.orchestrator.lease_manager import LeaseManager
from fleet.orchestrator.persona import PersonaStore
from fleet.orchestrator.scenario_scheduler import ScenarioScheduler


class LeaseManagerTests(unittest.TestCase):
    def test_lease_is_persistent_unique_and_rotates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = LeaseManager(Path(tmp) / "leases.json", "10.70.0.0/24", "10.70.0.1", 1234)
            first, prefix, generation = manager.allocate("lnx-0001")
            self.assertEqual(prefix, 24)
            self.assertEqual(generation, 0)
            self.assertEqual(manager.allocate("lnx-0001")[0], first)
            other = manager.allocate("lnx-0002")[0]
            self.assertNotEqual(first, other)
            rotated, _, generation = manager.allocate("lnx-0001", rotate=True)
            self.assertNotEqual(first, rotated)
            self.assertNotEqual(other, rotated)
            self.assertEqual(generation, 1)


class PersonaTests(unittest.TestCase):
    def test_persona_assignment_is_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = root / "catalog"
            catalog.mkdir()
            (catalog / "a.json").write_text(json.dumps({
                "id": "a", "role": "dev", "hostname_prefix": "dev", "platform": "linux",
                "activity": "medium", "working_hours": "always", "normal_apps": [],
                "scenario_rate_per_hour": 1, "scenario_weights": {"008": 1}
            }))
            (catalog / "b.json").write_text(json.dumps({
                "id": "b", "role": "server", "hostname_prefix": "srv", "platform": "linux",
                "activity": "low", "working_hours": "always", "normal_apps": [],
                "scenario_rate_per_hour": 1, "scenario_weights": {"008": 1}
            }))
            store = PersonaStore(catalog, 42)
            endpoint = root / "endpoint"
            endpoint.mkdir()
            first = store.assign(endpoint, "lnx-0001", 1)
            second = store.assign(endpoint, "lnx-0001", 1)
            self.assertEqual(first, second)
            self.assertTrue((endpoint / "persona.json").exists())


class NetworkNamingTests(unittest.TestCase):
    def test_interface_names_are_short_and_unique(self) -> None:
        names = [LinuxNetworkManager.names(f"lnx-{i:04d}", i) for i in range(1, 501)]
        self.assertEqual(500, len({n.host_veth for n in names}))
        self.assertEqual(500, len({n.peer_veth for n in names}))
        self.assertTrue(all(len(n.host_veth) <= 15 and len(n.peer_veth) <= 15 for n in names))


class ProcessLauncherTests(unittest.TestCase):
    def test_wrapper_uses_cgroup_uts_and_ip_netns_exec(self) -> None:
        command = ProcessLauncher._wrapped(
            ["echo", "ok"],
            NamespaceContext(netns_name="neta-lnx-0001", uts_keeper_pid=1234,
                             cgroup_path=Path("/sys/fs/cgroup/neta-lab/lnx-0001")),
        )
        text = " ".join(str(x) for x in command)
        self.assertIn("cgroup.procs", text)
        self.assertIn("nsenter", text)
        self.assertIn("--uts=/proc/1234/ns/uts", text)
        self.assertIn("ip netns exec neta-lnx-0001", text)


class FakeRunner:
    def __init__(self, *, link_exists: bool = False, fail_add_number: int | None = None) -> None:
        self.link_exists = link_exists
        self.fail_add_number = fail_add_number
        self.commands: list[list[str]] = []
        self.rules: set[tuple[str, ...]] = set()
        self.add_count = 0

    def require(self, *commands: str) -> None:
        return

    def run(self, argv, *, check=True, **kwargs):
        command = [str(x) for x in argv]
        self.commands.append(command)
        if command[:4] == ["ip", "link", "show", "dev"]:
            return CommandResult(0 if self.link_exists else 1)
        if command[:4] == ["ip", "link", "add", command[3] if len(command) > 3 else ""]:
            self.link_exists = True
            return CommandResult(0)
        if command and command[0] == "iptables":
            op_index = 3 if len(command) > 3 and command[1:3] == ["-t", "nat"] else 1
            op = command[op_index]
            key = tuple(command[:op_index] + command[op_index + 1:])
            if op == "-C":
                return CommandResult(0 if key in self.rules else 1)
            if op == "-A":
                self.add_count += 1
                if self.fail_add_number == self.add_count:
                    if check:
                        raise RuntimeError("injected iptables add failure")
                    return CommandResult(1)
                self.rules.add(key)
                return CommandResult(0)
            if op == "-D":
                self.rules.discard(key)
                return CommandResult(0)
        return CommandResult(0)


class HostNetworkSafetyTests(unittest.TestCase):
    def test_bridge_refuses_preexisting_unowned_interface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner(link_exists=True)
            manager = LinuxNetworkManager(
                runner, bridge="neta-sim0", gateway="10.70.0.1", prefix_length=16,
                dns_servers=(), ownership_file=Path(tmp) / "bridge.json",
            )
            with self.assertRaisesRegex(RuntimeError, "pre-existing bridge"):
                manager.ensure_bridge()

    def test_bridge_created_by_lab_is_tracked_and_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ownership = Path(tmp) / "bridge.json"
            runner = FakeRunner(link_exists=False)
            manager = LinuxNetworkManager(
                runner, bridge="neta-sim0", gateway="10.70.0.1", prefix_length=16,
                dns_servers=(), ownership_file=ownership,
            )
            manager.ensure_bridge()
            self.assertTrue(ownership.exists())
            manager.delete_bridge()
            self.assertFalse(ownership.exists())
            self.assertTrue(any(cmd[:4] == ["ip", "link", "del", "neta-sim0"] for cmd in runner.commands))

    def test_nat_partial_failure_restores_owned_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            forward = root / "ip_forward"
            forward.write_text("0\n", encoding="ascii")
            state = root / "egress.json"
            runner = FakeRunner(fail_add_number=2)
            manager = LinuxEgressManager(
                runner, state_file=state, fleet_name="test", subnet="10.70.0.0/16",
                bridge="neta-sim0", ip_forward_path=forward,
            )
            with self.assertRaisesRegex(RuntimeError, "injected"):
                manager.enable()
            self.assertFalse(state.exists())
            self.assertFalse(runner.rules)
            self.assertIn(["sysctl", "-w", "net.ipv4.ip_forward=0"], runner.commands)


class GroundTruthTests(unittest.TestCase):
    def test_required_ground_truth_fields_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = root / "expected.yaml"
            expected.write_text(
                "scenario:\n  id: NETA-LAB-001\n  version: 3\n"
                "expected_evidence:\n  process_attribution: required\n  tls: not_applicable\n"
                "expected_findings:\n  - type: PERIODIC_OUTBOUND_CONNECTION\n",
                encoding="utf-8",
            )
            recorder = GroundTruthRecorder(root / "fleet.jsonl")
            started = recorder.start_run(
                endpoint_file=root / "endpoint.jsonl", endpoint_slot="lnx-0002",
                agent_id="AGENT-2", tenant="lab", persona_id="dev", scenario_id="001",
                expected_path=expected, parameters={"count": 5},
            )
            self.assertEqual("3", started["scenario_version"])
            self.assertEqual("dev", started["persona_id"])
            self.assertEqual("required", started["expected_evidence_types"]["process_attribution"])
            self.assertEqual("PERIODIC_OUTBOUND_CONNECTION", started["expected_rule_finding"])
            self.assertIn("actual_observed_evidence", started)
            self.assertIn("actual_finding", started)
            finished = recorder.finish_run(root / "endpoint.jsonl", started, exit_code=0, result="PASS")
            self.assertEqual("PASS", finished["result"])
            self.assertIsNotNone(finished["end_timestamp"])


class SchedulerTests(unittest.TestCase):
    @staticmethod
    def endpoint(slot: str, index: int, persona: str) -> EndpointState:
        root = Path("/tmp") / slot
        return EndpointState(
            slot=slot, index=index, hostname=slot, persona_id=persona, tenant="lab",
            ip_address=f"10.70.0.{index + 10}", prefix_length=16,
            netns_name=f"neta-{slot}", host_veth=f"h{index}", peer_veth=f"e{index}",
            cgroup_path=root / "cgroup", state_dir=root, identity_dir=root / "identity",
            database=root / "neta.db",
        )

    def test_scheduler_is_seed_replayable(self) -> None:
        persona = Persona(
            id="dev", role="developer", platform="linux", hostname_prefix="dev",
            activity="noisy", working_hours="always", normal_apps=("git",),
            scenario_rate_per_hour=3600.0,
            scenario_weights={"008": 8.0, "001": 1.0},
            threat_scenario_probability=0.1,
        )
        endpoints = [self.endpoint("lnx-0001", 1, "dev"), self.endpoint("lnx-0002", 2, "dev")]
        personas = {"dev": persona}
        first = ScenarioScheduler(seed=999, max_concurrent=2).plan(endpoints, personas, 2.0)
        second = ScenarioScheduler(seed=999, max_concurrent=2).plan(endpoints, personas, 2.0)
        self.assertEqual(first, second)
        self.assertGreater(len(first), 0)


class EnrollmentConfigTests(unittest.TestCase):
    def test_token_file_never_changes_endpoint_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokens.json"
            path.write_text(json.dumps({"lnx-0001": "one", "lnx-0002": "two"}))
            config = EnrollmentConfig.from_token_file(
                coordinator="https://coordinator.example", fleet_ca=Path("ca.pem"),
                fleet_id="fleet", token_file=path, slots=["lnx-0001", "lnx-0002"])
            self.assertEqual("one", config.tokens["lnx-0001"])
            self.assertEqual("two", config.tokens["lnx-0002"])


if __name__ == "__main__":
    unittest.main()
