#!/usr/bin/env python3
"""Validate and normalize the constrained acceptance_contract YAML section."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any

MAX_CONTRACT_FILE_BYTES = 256 * 1024
KEY = re.compile(r"^[a-z][a-z0-9_]*$")


class ContractError(ValueError):
    pass


def _scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized in {"true", "false"}:
        return normalized == "true"
    if re.fullmatch(r"[0-9]+", normalized):
        return int(normalized)
    if not normalized or normalized.startswith(("[", "{", "&", "*", "!")):
        raise ContractError("acceptance values must be non-empty plain scalars")
    return normalized


def parse_contract(path: pathlib.Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_CONTRACT_FILE_BYTES:
        raise ContractError(f"{path}: file exceeds {MAX_CONTRACT_FILE_BYTES} bytes")
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line == "acceptance_contract:")
    except StopIteration as error:
        raise ContractError(f"{path}: missing acceptance_contract") from error

    result: dict[str, Any] = {}
    section: dict[str, Any] | None = None
    for number, raw in enumerate(lines[start + 1 :], start=start + 2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw:
            raise ContractError(f"{path}:{number}: tabs are not allowed")
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            break
        if indent not in {2, 4}:
            raise ContractError(f"{path}:{number}: acceptance indentation must be 2 or 4 spaces")
        text = raw.strip()
        if ":" not in text:
            raise ContractError(f"{path}:{number}: expected key: value")
        key, value = (part.strip() for part in text.split(":", 1))
        if not KEY.fullmatch(key):
            raise ContractError(f"{path}:{number}: invalid key {key!r}")
        if indent == 2:
            if value:
                raise ContractError(f"{path}:{number}: top-level contract keys must be mappings")
            if key in result:
                raise ContractError(f"{path}:{number}: duplicate key {key}")
            section = {}
            result[key] = section
            continue
        if section is None:
            raise ContractError(f"{path}:{number}: property has no section")
        if not value:
            raise ContractError(f"{path}:{number}: nested mappings and lists are not allowed")
        if key in section:
            raise ContractError(f"{path}:{number}: duplicate key {key}")
        section[key] = _scalar(value)

    detector = result.get("detector")
    if not isinstance(detector, dict) or not isinstance(detector.get("required"), bool):
        raise ContractError(f"{path}: detector.required boolean is required")
    if detector["required"]:
        required = {"rule_id", "semantic_type", "minimum_severity", "allowed_statuses",
                    "evidence_root", "ruleset_provenance"}
        missing = sorted(required - detector.keys())
        if missing:
            raise ContractError(f"{path}: detector is missing {', '.join(missing)}")
    return result


def load_catalog(root: pathlib.Path) -> dict[str, Any]:
    catalog: dict[str, Any] = {}
    for path in sorted(root.glob("*/expected.yaml")):
        scenario_id = path.parent.name.split("-", 1)[0]
        if not re.fullmatch(r"[0-9]{3}", scenario_id):
            raise ContractError(f"{path}: scenario directory must start with a three-digit id")
        catalog[scenario_id] = parse_contract(path)
    if not catalog:
        raise ContractError(f"{root}: no expected.yaml files found")
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    catalog = load_catalog(args.scenarios_root)
    document = {"schema_version": 1, "contracts": catalog}
    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
