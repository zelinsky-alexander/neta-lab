#!/usr/bin/env python3
"""Select a live connection that satisfies the agent's baseline prerequisites."""

from __future__ import annotations

import argparse
import dataclasses
import sqlite3
import time


MINIMUM_RTT_SAMPLES = 5


@dataclasses.dataclass(frozen=True)
class BaselineReadiness:
    connection_id: int | None
    target: str
    rtt_samples: int
    exact_tls: bool

    @property
    def ready(self) -> bool:
        return self.connection_id is not None and self.rtt_samples >= MINIMUM_RTT_SAMPLES


def normalize_address(value: str) -> str:
    return value.removeprefix("::ffff:")


def select_readiness(
    database: sqlite3.Connection,
    port: int,
    remote_address: str,
    require_exact_tls: bool,
    now_ns: int,
    maximum_idle_ns: int,
) -> BaselineReadiness:
    candidates = database.execute(
        """
        SELECT id,COALESCE(NULLIF(target_host,''),remote_ip) AS target,remote_ip
          FROM connections
         WHERE remote_port=? AND direction='OUTBOUND'
           AND lifecycle_state<>'CLOSED'
           AND last_seen_ns>=?
         ORDER BY last_seen_ns DESC,id DESC
        """,
        (port, max(0, now_ns - maximum_idle_ns)),
    ).fetchall()
    if remote_address:
        expected = normalize_address(remote_address)
        candidates = [
            row for row in candidates
            if normalize_address(str(row["remote_ip"])) == expected
            or normalize_address(str(row["target"])) == expected
        ]
    if not candidates:
        target = f"{remote_address or '<unresolved>'}:{port}"
        return BaselineReadiness(None, target, 0, False)

    candidate = candidates[0]
    connection_id = int(candidate["id"])
    target_host = str(candidate["target"])
    rtt_samples = int(database.execute(
        """
        SELECT count(*)
          FROM transport_samples s
          JOIN connections c ON c.id=s.connection_id
         WHERE c.direction='OUTBOUND' AND c.remote_port=?
           AND COALESCE(NULLIF(c.target_host,''),c.remote_ip)=?
           AND s.rtt_us>0
        """,
        (port, target_host),
    ).fetchone()[0])
    tls_table = database.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='connection_tls_session_evidence'"
    ).fetchone()
    tls_row = None
    if tls_table:
        tls_row = database.execute(
            """
            SELECT 1
              FROM connection_tls_session_evidence
             WHERE connection_id=?
               AND relation='OUTBOUND_SERVER_IDENTITY'
               AND correlation_fidelity='EXACT'
               AND observation_fidelity='EXACT'
               AND peer_authenticated=1
               AND (verify_result IS NULL OR verify_result=0)
               AND expected_peer_name IS NOT NULL
               AND expected_peer_name=matched_peer_name
               AND spki_sha256<>''
             LIMIT 1
            """,
            (connection_id,),
        ).fetchone()
    exact_tls = tls_row is not None
    if require_exact_tls and not exact_tls:
        return BaselineReadiness(connection_id, f"{target_host}:{port}", rtt_samples, False)
    return BaselineReadiness(connection_id, f"{target_host}:{port}", rtt_samples, exact_tls)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("port", type=int)
    parser.add_argument("require_exact_tls", choices=("true", "false"))
    parser.add_argument("remote_address", nargs="?", default="")
    parser.add_argument("--maximum-idle-seconds", type=int, default=10)
    args = parser.parse_args()
    uri = f"file:{args.database}?mode=ro"
    with sqlite3.connect(uri, uri=True) as database:
        database.row_factory = sqlite3.Row
        readiness = select_readiness(
            database,
            args.port,
            args.remote_address,
            args.require_exact_tls == "true",
            time.monotonic_ns(),
            args.maximum_idle_seconds * 1_000_000_000,
        )
    print(readiness.connection_id or "")
    print(readiness.target)
    print(readiness.rtt_samples)
    print("true" if readiness.exact_tls else "false")
    return 0 if readiness.ready and (args.require_exact_tls == "false" or readiness.exact_tls) else 1


if __name__ == "__main__":
    raise SystemExit(main())
