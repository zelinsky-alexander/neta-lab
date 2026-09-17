from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "common/linux/baseline_readiness.py"
SPEC = importlib.util.spec_from_file_location("baseline_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BaselineReadinessTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        temporary.close()
        self.path = Path(temporary.name)
        self.database = sqlite3.connect(self.path)
        self.database.row_factory = sqlite3.Row
        self.database.executescript("""
            CREATE TABLE connections(
              id INTEGER PRIMARY KEY,target_host TEXT,remote_ip TEXT,remote_port INTEGER,
              direction TEXT,lifecycle_state TEXT,last_seen_ns INTEGER);
            CREATE TABLE transport_samples(
              id INTEGER PRIMARY KEY,connection_id INTEGER,rtt_us INTEGER);
            CREATE TABLE connection_tls_session_evidence(
              connection_id INTEGER,relation TEXT,correlation_fidelity TEXT,
              observation_fidelity TEXT,peer_authenticated INTEGER,verify_result INTEGER,
              expected_peer_name TEXT,matched_peer_name TEXT,spki_sha256 TEXT);
        """)

    def tearDown(self) -> None:
        self.database.close()
        self.path.unlink(missing_ok=True)

    def add_connection(self, connection_id: int, address: str, state: str = "ACTIVE") -> None:
        self.database.execute(
            "INSERT INTO connections VALUES(?,?,?,?,?,?,?)",
            (connection_id, "", address, 18461, "OUTBOUND", state, time.monotonic_ns()),
        )

    def add_rtt_samples(self, connection_id: int, count: int) -> None:
        self.database.executemany(
            "INSERT INTO transport_samples(connection_id,rtt_us) VALUES(?,?)",
            [(connection_id, 1000 + index) for index in range(count)],
        )

    def add_exact_tls(self, connection_id: int) -> None:
        self.database.execute(
            "INSERT INTO connection_tls_session_evidence VALUES(?,?,?,?,?,?,?,?,?)",
            (connection_id, "OUTBOUND_SERVER_IDENTITY", "EXACT", "EXACT", 1, 0,
             "neta-lab.local", "neta-lab.local", "spki-a"),
        )

    def readiness(self, address: str = "127.0.0.1", require_tls: bool = True):
        self.database.commit()
        return MODULE.select_readiness(
            self.database, 18461, address, require_tls, time.monotonic_ns(), 10_000_000_000)

    def test_requires_five_target_rtt_samples_and_exact_tls(self) -> None:
        self.add_connection(1, "127.0.0.1")
        self.add_rtt_samples(1, 4)
        self.add_exact_tls(1)
        self.assertFalse(self.readiness().ready)
        self.add_rtt_samples(1, 1)
        result = self.readiness()
        self.assertTrue(result.ready)
        self.assertTrue(result.exact_tls)

    def test_ignores_closed_or_wrong_address_connection_on_same_port(self) -> None:
        self.add_connection(1, "127.0.0.1", "CLOSED")
        self.add_rtt_samples(1, 5)
        self.add_exact_tls(1)
        self.add_connection(2, "127.0.0.2")
        self.add_rtt_samples(2, 5)
        self.add_exact_tls(2)
        self.assertIsNone(self.readiness().connection_id)

    def test_rtt_count_matches_agent_target_semantics(self) -> None:
        self.add_connection(1, "127.0.0.1", "CLOSED")
        self.add_rtt_samples(1, 3)
        self.add_connection(2, "127.0.0.1")
        self.add_rtt_samples(2, 2)
        self.add_exact_tls(2)
        result = self.readiness()
        self.assertEqual(2, result.connection_id)
        self.assertEqual(5, result.rtt_samples)
        self.assertTrue(result.ready)


if __name__ == "__main__":
    unittest.main()
