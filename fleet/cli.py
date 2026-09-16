from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from fleet.model import FleetConfig
from fleet.orchestrator.fleet_manager import FleetManager
from fleet.orchestrator.identity_manager import EnrollmentConfig


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config(path: Path) -> FleetConfig:
    config = FleetConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if not config.agent_binary.is_absolute():
        config = replace(config, agent_binary=(repo_root() / config.agent_binary).resolve())
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neta-fleet-linux",
        description="NETA Phase-2 realistic Linux fleet orchestrator",
    )
    parser.add_argument("--config", type=Path, default=repo_root() / "fleet/config/linux-default.json")
    parser.add_argument("--agent", type=Path, help="override neta-agent binary")
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--cgroup-root", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--allow-unenrolled", action="store_true",
                        help="sensor/isolation development only; findings cannot be sent with real NAP/mTLS identity")
    parser.add_argument("--enable-nat", action="store_true",
                        help="opt in to dedicated iptables MASQUERADE/forward rules for endpoint Internet egress")

    sub = parser.add_subparsers(dest="command", required=True)

    def count_command(name: str, help_text: str):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--count", type=int, default=3)
        add_enrollment(p)
        return p

    def add_enrollment(p: argparse.ArgumentParser) -> None:
        p.add_argument("--coordinator")
        p.add_argument("--fleet-ca", type=Path)
        p.add_argument("--fleet-id", default="fleet-large-scale-lab")
        p.add_argument("--token-file", type=Path,
                       help="JSON object slot->one-time token or JSON array in endpoint order")

    count_command("up", "create/start the Linux fleet")
    count_command("recover", "recreate disposable kernel/runtime state from persistent endpoint state")
    count_command("acceptance", "run the 3-endpoint Phase-2 isolation acceptance test")

    down = sub.add_parser("down", help="stop fleet and remove disposable kernel objects")
    down.add_argument("--purge-state", action="store_true",
                      help="also delete persistent personas, leases, identities and endpoint databases")

    sub.add_parser("status", help="show broker/endpoint health")

    restart = sub.add_parser("restart", help="restart one real agent runtime")
    restart.add_argument("--slot", required=True)
    restart.add_argument("--rotate-ip", action="store_true",
                         help="allocate a new DHCP-like endpoint IP while preserving AgentId/certificate")

    scenario = sub.add_parser("scenario", help="run one existing NETA-LAB scenario inside one endpoint")
    scenario.add_argument("--slot", required=True)
    scenario.add_argument("--scenario", required=True)
    scenario.add_argument("--parameters", default="{}",
                          help="JSON object; auto-wired scenarios: 001,008,014,015")

    schedule = sub.add_parser("schedule", help="run deterministic persona-driven randomized scenarios")
    schedule.add_argument("--duration", type=float, required=True, help="scheduler window in seconds")
    return parser


def with_overrides(config: FleetConfig, args: argparse.Namespace) -> FleetConfig:
    updates = {}
    for attr in ("state_root", "runtime_root", "cgroup_root", "seed"):
        value = getattr(args, attr, None)
        if value is not None:
            updates[attr] = value
    if args.agent is not None:
        updates["agent_binary"] = args.agent.expanduser().resolve()
    if args.allow_unenrolled:
        updates["allow_unenrolled"] = True
    if args.enable_nat:
        updates["enable_nat"] = True
    return replace(config, **updates) if updates else config


def enrollment_for(args: argparse.Namespace, manager: FleetManager, count: int) -> EnrollmentConfig | None:
    values = [getattr(args, name, None) for name in ("coordinator", "fleet_ca", "token_file")]
    if not any(values):
        return None
    if not all(values):
        raise RuntimeError("--coordinator, --fleet-ca and --token-file must be provided together")
    slots = [manager.host.slot(index) for index in range(1, count + 1)]
    return EnrollmentConfig.from_token_file(
        coordinator=args.coordinator,
        fleet_ca=args.fleet_ca,
        fleet_id=args.fleet_id,
        token_file=args.token_file,
        slots=slots,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = with_overrides(load_config(args.config), args)
        manager = FleetManager(repo_root=repo_root(), config=config)
        if args.command in {"up", "recover", "acceptance"}:
            enrollment = enrollment_for(args, manager, args.count)
            if args.command == "up":
                endpoints = manager.up(args.count, enrollment)
                print(json.dumps({"started": [e.to_dict() for e in endpoints]}, indent=2))
            elif args.command == "recover":
                endpoints = manager.recover(args.count, enrollment)
                print(json.dumps({"recovered": [e.to_dict() for e in endpoints]}, indent=2))
            else:
                if args.count != 3:
                    raise RuntimeError("Phase-2 acceptance is intentionally fixed at exactly 3 endpoints")
                report = manager.acceptance(enrollment)
                print(json.dumps(report, indent=2, sort_keys=True))
        elif args.command == "down":
            manager.down(purge_state=args.purge_state)
            print("NETA Linux fleet stopped")
        elif args.command == "status":
            print(json.dumps(manager.status(), indent=2, sort_keys=True))
        elif args.command == "restart":
            state = manager.restart_endpoint(args.slot, rotate_ip=args.rotate_ip)
            print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
        elif args.command == "scenario":
            parameters = json.loads(args.parameters)
            if not isinstance(parameters, dict):
                raise RuntimeError("--parameters must decode to a JSON object")
            result = manager.run_scenario(args.slot, args.scenario, parameters)
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "schedule":
            results = manager.schedule(args.duration)
            print(json.dumps({"runs": results}, indent=2, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
