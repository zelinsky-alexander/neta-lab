from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from fleet.windows.fleet_manager import WindowsFleetManager
from fleet.windows.model import EnrollmentConfig


def _count(database: Path, sql: str, parameters: tuple[Any, ...] = ()) -> int:
    if not database.exists():
        return 0
    with sqlite3.connect(database) as connection:
        try:
            row = connection.execute(sql, parameters).fetchone()
        except sqlite3.DatabaseError:
            return 0
    return int(row[0]) if row else 0


def run_acceptance(manager: WindowsFleetManager,
                   enrollment: EnrollmentConfig | None = None) -> dict[str, Any]:
    endpoints = manager.up(10, enrollment)
    prefix = manager.config.endpoint_prefix
    process_slot = f"{prefix}-0002"
    network_slot = f"{prefix}-0003"
    report: dict[str, Any] = {
        "endpoint_count": len(endpoints),
        "process_scenario_slot": process_slot,
        "network_scenario_slot": network_slot,
        "checks": {},
    }
    try:
        roots = {endpoint.root_pid for endpoint in endpoints}
        ips = {endpoint.ip_address for endpoint in endpoints}
        containers = {endpoint.container_id for endpoint in endpoints}
        report["checks"]["unique_root_pids"] = len(roots) == 10
        report["checks"]["unique_ips"] = len(ips) == 10
        report["checks"]["unique_container_ids"] = len(containers) == 10

        identities = [endpoint.agent_id for endpoint in endpoints if endpoint.agent_id]
        report["checks"]["unique_agent_ids"] = (
            len(set(identities)) == 10 if enrollment is not None else True
        )

        process_result = manager.run_scenario(process_slot, "006")
        network_result = manager.run_scenario(network_slot, "001", {"count": 6, "interval_seconds": 1})
        report["process_run_id"] = process_result.get("run_id")
        report["network_run_id"] = network_result.get("run_id")
        network_port = int(network_result.get("parameters", {}).get("port", 0))
        time.sleep(3.0)

        process_hits: dict[str, int] = {}
        network_hits: dict[str, int] = {}
        finding_hits: dict[str, int] = {}
        for endpoint in endpoints:
            process_hits[endpoint.slot] = _count(
                endpoint.database,
                "SELECT COUNT(*) FROM process_instances_ms5 WHERE lower(executable_path) LIKE ?",
                ("%windows-update-helper.exe",),
            )
            network_hits[endpoint.slot] = _count(
                endpoint.database,
                "SELECT COUNT(*) FROM connections WHERE remote_port=?",
                (network_port,),
            ) if network_port else 0
            finding_hits[endpoint.slot] = _count(
                endpoint.database,
                "SELECT COUNT(*) FROM process_findings_ms5 WHERE lower(process_image) LIKE ?",
                ("%windows-update-helper.exe",),
            )

        report["process_hits"] = process_hits
        report["network_hits"] = network_hits
        report["process_finding_hits"] = finding_hits
        report["checks"]["process_evidence_isolated"] = (
            process_hits.get(process_slot, 0) > 0 and
            all(count == 0 for slot, count in process_hits.items() if slot != process_slot)
        )
        report["checks"]["network_evidence_isolated"] = (
            network_hits.get(network_slot, 0) > 0 and
            all(count == 0 for slot, count in network_hits.items() if slot != network_slot)
        )
        report["checks"]["process_finding_not_cross_contaminated"] = all(
            count == 0 for slot, count in finding_hits.items() if slot != process_slot
        )
        status = manager.status()
        report["checks"]["broker_stable"] = bool(status.get("broker_running"))
        report["passed"] = all(report["checks"].values())
        return report
    finally:
        path = manager.config.state_root / "acceptance-phase3.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        report.setdefault("passed", False)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manager.down()
