from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]


class ScenarioContractTests(unittest.TestCase):
    def test_024_passes_its_own_identity_to_shared_runner(self) -> None:
        runner = (ROOT / "scenarios/024-tls-identity-change-only/linux/run.sh").read_text()
        self.assertIn("NETA-LAB-024", runner)
        self.assertNotIn("exec \"$ROOT/scenarios/022-tls-identity-rotation/linux/run.sh\" \"${1:-18464}\"\n", runner)

    def test_resolver_connection_uses_already_resolved_numeric_address(self) -> None:
        helper = (ROOT / "common/resolver/resolver_lab.py").read_text()
        self.assertIn("socket.socket(family,socket.SOCK_STREAM)", helper)
        self.assertNotIn("socket.create_connection", helper)

    def test_suite_preserves_real_per_scenario_log_paths(self) -> None:
        suite = (ROOT / "automation/run-linux-suite.sh").read_text()
        self.assertIn('log="$OUTPUT_DIR/logs/$id.log"', suite)
        self.assertIn('"see logs/$id.log"', suite)
        self.assertIn('dst.parent / "logs" / f"{row[\'scenario\']}.log"', suite)

    def test_large_ingress_transfer_is_paced_for_live_agent_sampling(self) -> None:
        server = (ROOT / "scenarios/003-large-download/server/large_download_server.py").read_text()
        self.assertIn("minimum_duration_seconds = 8.0", server)
        self.assertIn("target_elapsed = self.minimum_duration_seconds * sent / total", server)


if __name__ == "__main__":
    unittest.main()
