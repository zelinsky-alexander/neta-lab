from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from fleet.windows.acceptance import run_acceptance
from fleet.windows.fleet_manager import WindowsFleetManager
from fleet.windows.model import EnrollmentConfig, WindowsFleetConfig


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config(path: Path, args: argparse.Namespace) -> WindowsFleetConfig:
    config = WindowsFleetConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
    agent = args.agent if args.agent is not None else config.agent_binary
    if not agent.is_absolute():
        agent = (repo_root() / agent).resolve()
    state_root = args.state_root or config.state_root
    runtime_root = args.runtime_root or config.runtime_root
    return replace(
        config,
        agent_binary=agent,
        state_root=state_root,
        runtime_root=runtime_root,
        allow_unenrolled=bool(args.allow_unenrolled or config.allow_unenrolled),
        seed=args.seed if args.seed is not None else config.seed,
    )


def load_tokens(path: Path, prefix: str) -> dict[str, str]:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return {str(key): str(value) for key, value in data.items()}
    if isinstance(data, list):
        return {f"{prefix}-{index:04d}": str(value) for index, value in enumerate(data, start=1)}
    raise RuntimeError("token file must contain an object keyed by slot or an array")


def enrollment_from_args(args: argparse.Namespace, config: WindowsFleetConfig) -> EnrollmentConfig | None:
    provided = [args.coordinator, args.fleet_ca, args.token_file]
    if not any(provided):
        return None
    if not all(provided):
        raise RuntimeError("--coordinator, --fleet-ca and --token-file must be supplied together")
    return EnrollmentConfig(
        coordinator=str(args.coordinator),
        fleet_ca=Path(args.fleet_ca).resolve(),
        fleet_id=str(args.fleet_id),
        tokens=load_tokens(Path(args.token_file), config.endpoint_prefix),
    )


def add_enrollment_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--coordinator")
    parser.add_argument("--fleet-ca", type=Path)
    parser.add_argument("--fleet-id", default="fleet-large-scale-windows")
    parser.add_argument("--token-file", type=Path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neta-fleet-windows",
        description="NETA Phase-3 realistic Windows fleet orchestrator",
    )
    parser.add_argument("--config", type=Path, default=repo_root() / "fleet/config/windows-default.json")
    parser.add_argument("--agent", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--allow-unenrolled", action="store_true")

    subcommands = parser.add_subparsers(dest="command", required=True)
    up = subcommands.add_parser("up")
    up.add_argument("--count", type=int, default=10)
    add_enrollment_options(up)

    down = subcommands.add_parser("down")
    down.add_argument("--purge-state", action="store_true")

    subcommands.add_parser("status")

    scenario = subcommands.add_parser("scenario")
    scenario.add_argument("--slot", required=True)
    scenario.add_argument("--scenario", required=True)
    scenario.add_argument("--parameters", default="{}")

    schedule = subcommands.add_parser("schedule")
    schedule.add_argument("--duration", type=float, required=True)

    acceptance = subcommands.add_parser("acceptance")
    add_enrollment_options(acceptance)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config, args)
        manager = WindowsFleetManager(config=config, repo_root=repo_root())
        if args.command == "up":
            endpoints = manager.up(args.count, enrollment_from_args(args, config))
            print(json.dumps({"endpoints": [endpoint.to_dict() for endpoint in endpoints]}, indent=2))
        elif args.command == "down":
            manager.down(purge_state=args.purge_state)
            print("Windows fleet stopped")
        elif args.command == "status":
            print(json.dumps(manager.status(), indent=2, sort_keys=True))
        elif args.command == "scenario":
            parameters = json.loads(args.parameters)
            if not isinstance(parameters, dict):
                raise RuntimeError("--parameters must decode to a JSON object")
            print(json.dumps(manager.run_scenario(args.slot, args.scenario, parameters), indent=2))
        elif args.command == "schedule":
            print(json.dumps(manager.schedule(args.duration), indent=2))
        elif args.command == "acceptance":
            report = run_acceptance(manager, enrollment_from_args(args, config))
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if report.get("passed") else 1
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
