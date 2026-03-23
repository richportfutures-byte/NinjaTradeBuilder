from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ..validation import validate_historical_packet
from ..schemas.packet import HistoricalPacket
from ..schemas.readiness_v2 import (
    ReadinessV2BootstrapArtifact,
    ReadinessV2ReplayArtifact,
    ReadinessV2UpdateArtifact,
    ReadinessWatchV1,
)
from .adapters import get_contract_adapter, supported_contracts


class HarnessArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _supported_contracts_text() -> str:
    return ", ".join(supported_contracts())


def build_parser() -> argparse.ArgumentParser:
    contracts = list(supported_contracts())
    parser = HarnessArgumentParser(
        prog="python -m ninjatradebuilder.readiness_v2",
        description=(
            "Run the internal readiness v2 operator harness for deterministic "
            "bootstrap, update, and replay artifacts."
        ),
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap",
        help=(
            "Validate a supported packet and emit premarket_briefing_v1, query_trigger_v1, "
            "and readiness_watch_v1 artifacts."
        ),
    )
    bootstrap.add_argument("--packet", required=True, help="Path to a packet JSON file.")
    bootstrap.add_argument(
        "--contract",
        choices=contracts,
        help="Required only for multi-contract bundle inputs.",
    )
    bootstrap.add_argument(
        "--evaluation-timestamp",
        help="Optional ISO-8601 timestamp. Defaults to market_packet.timestamp.",
    )
    bootstrap.add_argument(
        "--artifact-file",
        help="Optional path to write the emitted JSON artifact.",
    )

    update = subparsers.add_parser(
        "update",
        help="Advance an existing readiness_watch_v1 with a new supported packet snapshot.",
    )
    update.add_argument("--packet", required=True, help="Path to a packet JSON file.")
    update.add_argument(
        "--contract",
        choices=contracts,
        help="Required only for multi-contract bundle inputs.",
    )
    update.add_argument(
        "--prior-watch",
        required=True,
        help="Path to a readiness_watch_v1 JSON artifact.",
    )
    update.add_argument(
        "--evaluation-timestamp",
        required=True,
        help="Required ISO-8601 timestamp for deterministic watch advancement.",
    )
    update.add_argument(
        "--artifact-file",
        help="Optional path to write the emitted JSON artifact.",
    )

    replay = subparsers.add_parser(
        "replay",
        help=(
            "Replay a deterministic readiness watch sequence from bootstrap through "
            "ordered updates."
        ),
    )
    replay.add_argument("--packet", required=True, help="Path to the bootstrap packet JSON file.")
    replay.add_argument(
        "--contract",
        choices=contracts,
        help="Required only for multi-contract bundle inputs.",
    )
    replay.add_argument(
        "--updates",
        required=True,
        help="Path to a JSON file containing an ordered replay update list.",
    )
    replay.add_argument(
        "--evaluation-timestamp",
        help="Optional ISO-8601 timestamp for the bootstrap evaluation time.",
    )
    replay.add_argument(
        "--artifact-file",
        help="Optional path to write the emitted JSON artifact.",
    )

    return parser


def _load_json(path: Path, *, label: str) -> Any:
    if not path.is_file():
        raise ValueError(f"{label} file does not exist: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} file did not contain valid JSON: {path}") from exc


def _extract_bundle_packet(bundle: Mapping[str, Any], contract: str) -> dict[str, Any]:
    contracts = bundle.get("contracts", {})
    if contract not in contracts:
        raise ValueError(f"Bundle packet does not contain contract {contract}.")
    return {
        "$schema": "historical_packet_v1",
        "challenge_state": bundle["shared"]["challenge_state"],
        "attached_visuals": bundle["shared"]["attached_visuals"],
        "contract_metadata": contracts[contract]["contract_metadata"],
        "market_packet": contracts[contract]["market_packet"],
        "contract_specific_extension": contracts[contract]["contract_specific_extension"],
    }


def _load_packet_input(path: Path, *, contract: str | None) -> HistoricalPacket:
    payload = _load_json(path, label="Packet")
    if not isinstance(payload, Mapping):
        raise ValueError("Packet file must decode to a JSON object.")

    if payload.get("$schema") == "historical_packet_v1":
        return validate_historical_packet(payload)

    if "shared" in payload and "contracts" in payload:
        if contract is None:
            raise ValueError(
                "Multi-contract bundle inputs require --contract to select "
                f"{_supported_contracts_text()}."
            )
        selected_contract = contract
        return validate_historical_packet(_extract_bundle_packet(payload, selected_contract))

    raise ValueError(
        "Packet file must be a historical_packet_v1 object or a supported multi-contract bundle."
    )


def _load_prior_watch(path: Path) -> ReadinessWatchV1:
    payload = _load_json(path, label="Prior watch")
    if not isinstance(payload, Mapping):
        raise ValueError("Prior watch file must decode to a JSON object.")
    try:
        return ReadinessWatchV1.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Prior watch file did not contain a valid readiness_watch_v1 artifact: {path}") from exc


def _load_replay_updates(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path, label="Replay updates")
    if not isinstance(payload, list):
        raise ValueError("Replay updates file must decode to a JSON array.")
    updates: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"Replay update {index} must decode to a JSON object.")
        packet_payload = item.get("packet")
        evaluation_timestamp = item.get("evaluation_timestamp")
        if not isinstance(packet_payload, Mapping):
            raise ValueError(f"Replay update {index} requires a packet object.")
        if not isinstance(evaluation_timestamp, str):
            raise ValueError(f"Replay update {index} requires an evaluation_timestamp string.")
        updates.append(
            {
                "packet": dict(packet_payload),
                "evaluation_timestamp": evaluation_timestamp,
            }
        )
    return updates


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Timestamp must be a valid ISO-8601 datetime: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include timezone information: {value}")
    return parsed


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, Mapping):
        return {key: _normalize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_for_json(item) for item in value]
    return value


def _emit_artifact(
    artifact: ReadinessV2BootstrapArtifact | ReadinessV2ReplayArtifact | ReadinessV2UpdateArtifact,
    *,
    stdout: Any,
    artifact_file: str | None,
) -> None:
    rendered = json.dumps(_normalize_for_json(artifact), indent=2, sort_keys=True)
    stdout.write(rendered)
    stdout.write("\n")
    if artifact_file:
        Path(artifact_file).write_text(f"{rendered}\n")


def _run_bootstrap(args: argparse.Namespace) -> ReadinessV2BootstrapArtifact:
    packet = _load_packet_input(Path(args.packet), contract=args.contract)
    adapter = get_contract_adapter(packet.market_packet.contract)
    evaluation_timestamp = (
        _parse_timestamp(args.evaluation_timestamp) if args.evaluation_timestamp else None
    )
    return adapter.bootstrap(packet, evaluation_timestamp=evaluation_timestamp)


def _run_update(args: argparse.Namespace) -> ReadinessV2UpdateArtifact:
    prior_watch = _load_prior_watch(Path(args.prior_watch))
    packet = _load_packet_input(Path(args.packet), contract=args.contract)
    if packet.market_packet.contract != prior_watch.contract:
        raise ValueError("Packet contract must match prior watch contract.")
    adapter = get_contract_adapter(prior_watch.contract)
    evaluation_timestamp = _parse_timestamp(args.evaluation_timestamp)
    return adapter.update(
        prior_watch,
        packet,
        evaluation_timestamp=evaluation_timestamp,
    )


def _run_replay(args: argparse.Namespace) -> ReadinessV2ReplayArtifact:
    packet = _load_packet_input(Path(args.packet), contract=args.contract)
    adapter = get_contract_adapter(packet.market_packet.contract)
    updates = _load_replay_updates(Path(args.updates))
    bootstrap_evaluation_time = (
        _parse_timestamp(args.evaluation_timestamp) if args.evaluation_timestamp else None
    )
    return adapter.replay(
        packet,
        updates,
        bootstrap_evaluation_time=bootstrap_evaluation_time,
    )


def run_operator_harness(
    argv: list[str] | None = None,
    *,
    stdout: Any = None,
    stderr: Any = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        if args.mode == "bootstrap":
            artifact = _run_bootstrap(args)
        elif args.mode == "update":
            artifact = _run_update(args)
        else:
            artifact = _run_replay(args)
        _emit_artifact(artifact, stdout=stdout, artifact_file=args.artifact_file)
        return 0
    except (ValueError, ValidationError) as exc:
        stderr.write(f"ERROR: {exc}\n")
        return 2


def main() -> int:
    return run_operator_harness()


if __name__ == "__main__":
    raise SystemExit(main())
