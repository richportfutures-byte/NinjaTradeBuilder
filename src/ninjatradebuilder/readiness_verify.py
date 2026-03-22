from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .cli import _build_client, _normalize_for_json, load_packet_input
from .config import DEFAULT_GEMINI_MODEL, ConfigError, GeminiStartupConfig, load_gemini_startup_config
from .gemini_adapter import GeminiAdapterError, GeminiResponsesAdapter
from .readiness_adapter import (
    SUPPORTED_PACKET_READINESS_CONTRACTS,
    build_readiness_runtime_inputs_from_packet,
)
from .runtime import StructuredGenerationRequest, StructuredModelAdapter, run_readiness

ClientFactory = Callable[[GeminiStartupConfig], Any]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_PACKET_BUNDLE = REPO_ROOT / "tests" / "fixtures" / "packets.valid.json"
DEFAULT_FIXTURE_TRIGGER = REPO_ROOT / "tests" / "fixtures" / "readiness" / "zn_recheck_trigger.valid.json"
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts"
RAW_RESPONSE_EXCERPT_LIMIT = 1200


@dataclass(frozen=True)
class VerificationCase:
    contract: str
    invocation_mode: str
    runtime_inputs: Mapping[str, Any]
    readiness_trigger: Mapping[str, Any]
    input_sources: dict[str, str]


@dataclass(frozen=True)
class VerificationOutcome:
    contract: str
    invocation_mode: str
    input_sources: dict[str, str]
    live_execution_success: bool
    schema_validation_success: bool
    success: bool
    status: str | None
    lockout_reason: str | None
    insufficient_data_reasons: list[str]
    missing_inputs: list[str]
    prompt_id: int | None
    prompt_hash: str | None
    error_type: str | None
    error_message: str | None
    raw_response_excerpt: str | None


class _RecordingAdapter(StructuredModelAdapter):
    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter
        self.last_request: StructuredGenerationRequest | None = None
        self.last_raw_output: Mapping[str, Any] | None = None

    def generate_structured(self, request: StructuredGenerationRequest) -> Mapping[str, Any]:
        self.last_request = request
        raw_output = self._adapter.generate_structured(request)
        if isinstance(raw_output, Mapping):
            self.last_raw_output = raw_output
        return raw_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ninjatradebuilder.readiness_verify",
        description=(
            "Operator-invoked live readiness verification harness for Prompt 10 against "
            "the frozen readiness_engine_output contract."
        ),
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--fixture-sweep",
        action="store_true",
        help=(
            "Run all supported readiness contracts using the canonical fixture packet bundle and "
            "canonical readiness trigger."
        ),
    )
    mode_group.add_argument(
        "--packet",
        help="Path to a historical_packet_v1 JSON file or supported multi-contract packet bundle.",
    )
    mode_group.add_argument(
        "--runtime-inputs",
        help="Path to a readiness runtime_inputs JSON object.",
    )
    parser.add_argument(
        "--contract",
        choices=SUPPORTED_PACKET_READINESS_CONTRACTS,
        help="Required when --packet points to a multi-contract bundle; ignored for --fixture-sweep.",
    )
    parser.add_argument(
        "--trigger",
        help=(
            "Path to a readiness trigger JSON object. Defaults to the canonical readiness trigger for "
            "--fixture-sweep."
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_GEMINI_MODEL,
        help=f"Gemini model identifier. Defaults to {DEFAULT_GEMINI_MODEL}.",
    )
    parser.add_argument(
        "--artifact-path",
        help="Optional path for the JSON verification artifact. Defaults to ./artifacts/readiness-live-verify-<timestamp>.json.",
    )
    return parser


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json_object(path: Path, *, label: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} file does not exist: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} file did not contain valid JSON: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} file must decode to a JSON object: {path}")
    return payload


def _default_artifact_path() -> Path:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_ARTIFACT_DIR / f"readiness-live-verify-{timestamp}.json"


def _raw_response_excerpt(raw_output: Mapping[str, Any] | None) -> str | None:
    if raw_output is None:
        return None
    serialized = json.dumps(_normalize_for_json(raw_output), sort_keys=True)
    if len(serialized) <= RAW_RESPONSE_EXCERPT_LIMIT:
        return serialized
    return serialized[: RAW_RESPONSE_EXCERPT_LIMIT - 3] + "..."


def _prompt_hash(request: StructuredGenerationRequest | None) -> str | None:
    if request is None:
        return None
    return hashlib.sha256(request.rendered_prompt.encode("utf-8")).hexdigest()


def _build_verification_cases(args: argparse.Namespace) -> list[VerificationCase]:
    trigger_path = Path(args.trigger) if args.trigger else DEFAULT_FIXTURE_TRIGGER
    readiness_trigger = _load_json_object(trigger_path, label="Trigger")

    if args.fixture_sweep:
        cases: list[VerificationCase] = []
        for contract in SUPPORTED_PACKET_READINESS_CONTRACTS:
            packet = load_packet_input(DEFAULT_FIXTURE_PACKET_BUNDLE, contract=contract)
            runtime_inputs = build_readiness_runtime_inputs_from_packet(
                packet.model_dump(mode="json", by_alias=True)
            )
            cases.append(
                VerificationCase(
                    contract=contract,
                    invocation_mode="fixture_packet_bundle",
                    runtime_inputs=runtime_inputs,
                    readiness_trigger=readiness_trigger,
                    input_sources={
                        "packet_path": str(DEFAULT_FIXTURE_PACKET_BUNDLE),
                        "trigger_path": str(trigger_path),
                    },
                )
            )
        return cases

    if args.packet:
        packet_path = Path(args.packet)
        packet = load_packet_input(packet_path, contract=args.contract)
        runtime_inputs = build_readiness_runtime_inputs_from_packet(
            packet.model_dump(mode="json", by_alias=True)
        )
        return [
            VerificationCase(
                contract=packet.market_packet.contract,
                invocation_mode="packet_file",
                runtime_inputs=runtime_inputs,
                readiness_trigger=readiness_trigger,
                input_sources={
                    "packet_path": str(packet_path),
                    "trigger_path": str(trigger_path),
                },
            )
        ]

    runtime_inputs_path = Path(args.runtime_inputs)
    runtime_inputs = _load_json_object(runtime_inputs_path, label="Runtime inputs")
    contract = runtime_inputs.get("contract_metadata_json", {}).get("contract")
    if contract not in SUPPORTED_PACKET_READINESS_CONTRACTS:
        raise ValueError(
            "runtime_inputs must include contract_metadata_json.contract for one of: "
            + ", ".join(SUPPORTED_PACKET_READINESS_CONTRACTS)
            + "."
        )
    return [
        VerificationCase(
            contract=contract,
            invocation_mode="runtime_inputs_file",
            runtime_inputs=runtime_inputs,
            readiness_trigger=readiness_trigger,
            input_sources={
                "runtime_inputs_path": str(runtime_inputs_path),
                "trigger_path": str(trigger_path),
            },
        )
    ]


def _verify_case(case: VerificationCase, adapter: _RecordingAdapter) -> VerificationOutcome:
    try:
        result = run_readiness(
            runtime_inputs=case.runtime_inputs,
            readiness_trigger=case.readiness_trigger,
            model_adapter=adapter,
        )
        validated_output = result.validated_output
        return VerificationOutcome(
            contract=case.contract,
            invocation_mode=case.invocation_mode,
            input_sources=case.input_sources,
            live_execution_success=True,
            schema_validation_success=True,
            success=True,
            status=getattr(validated_output, "status", None),
            lockout_reason=getattr(validated_output, "lockout_reason", None),
            insufficient_data_reasons=list(getattr(validated_output, "insufficient_data_reasons", [])),
            missing_inputs=list(getattr(validated_output, "missing_inputs", [])),
            prompt_id=result.prompt_id,
            prompt_hash=_prompt_hash(adapter.last_request),
            error_type=None,
            error_message=None,
            raw_response_excerpt=_raw_response_excerpt(adapter.last_raw_output),
        )
    except Exception as exc:
        return VerificationOutcome(
            contract=case.contract,
            invocation_mode=case.invocation_mode,
            input_sources=case.input_sources,
            live_execution_success=adapter.last_request is not None,
            schema_validation_success=False,
            success=False,
            status=None,
            lockout_reason=None,
            insufficient_data_reasons=[],
            missing_inputs=[],
            prompt_id=adapter.last_request.prompt_id if adapter.last_request is not None else None,
            prompt_hash=_prompt_hash(adapter.last_request),
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            raw_response_excerpt=_raw_response_excerpt(adapter.last_raw_output),
        )


def _render_console_summary(outcomes: list[VerificationOutcome], *, stdout: Any) -> None:
    for outcome in outcomes:
        lockout_summary = outcome.lockout_reason or "-"
        if outcome.insufficient_data_reasons:
            insufficiency_summary = ",".join(outcome.insufficient_data_reasons)
        elif outcome.missing_inputs:
            insufficiency_summary = "missing:" + ",".join(outcome.missing_inputs)
        else:
            insufficiency_summary = "-"
        stdout.write(
            f"[{ 'PASS' if outcome.success else 'FAIL' }] {outcome.contract:<3} "
            f"mode={outcome.invocation_mode:<20} live={'ok' if outcome.live_execution_success else 'fail':<4} "
            f"schema={'ok' if outcome.schema_validation_success else 'fail':<4} "
            f"status={outcome.status or '-':<18} lockout={lockout_summary:<24} insufficient={insufficiency_summary}\n"
        )


def _build_artifact(
    *,
    started_at: str,
    finished_at: str,
    config: GeminiStartupConfig | None,
    outcomes: list[VerificationOutcome],
    invocation_args: list[str],
) -> dict[str, Any]:
    return {
        "artifact_schema": "readiness_live_verification_v1",
        "timestamp": finished_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "provider": "gemini",
        "model_name": config.model if config is not None else None,
        "success": all(outcome.success for outcome in outcomes) and bool(outcomes),
        "contracts_verified": [outcome.contract for outcome in outcomes],
        "invocation_args": invocation_args,
        "results": [_normalize_for_json(outcome) for outcome in outcomes],
    }


def _write_artifact(path: Path, artifact: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")


def run_cli(
    argv: list[str] | None = None,
    *,
    stdout: Any = None,
    stderr: Any = None,
    client_factory: ClientFactory | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    started_at = _utc_now_iso()
    artifact_path = Path(args.artifact_path) if args.artifact_path else _default_artifact_path()
    outcomes: list[VerificationOutcome] = []
    config: GeminiStartupConfig | None = None

    try:
        cases = _build_verification_cases(args)
        config = load_gemini_startup_config(model=args.model)
        base_adapter = GeminiResponsesAdapter(
            client=_build_client(config, client_factory),
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
        for case in cases:
            recording_adapter = _RecordingAdapter(base_adapter)
            outcomes.append(_verify_case(case, recording_adapter))
    except (ConfigError, GeminiAdapterError, ImportError, ValueError) as exc:
        outcomes.append(
            VerificationOutcome(
                contract=args.contract or "-",
                invocation_mode="startup",
                input_sources={},
                live_execution_success=False,
                schema_validation_success=False,
                success=False,
                status=None,
                lockout_reason=None,
                insufficient_data_reasons=[],
                missing_inputs=[],
                prompt_id=None,
                prompt_hash=None,
                error_type=exc.__class__.__name__,
                error_message=str(exc),
                raw_response_excerpt=None,
            )
        )

    artifact = _build_artifact(
        started_at=started_at,
        finished_at=_utc_now_iso(),
        config=config,
        outcomes=outcomes,
        invocation_args=argv or sys.argv[1:],
    )
    _write_artifact(artifact_path, artifact)

    _render_console_summary(outcomes, stdout=stdout)
    passed = sum(1 for outcome in outcomes if outcome.success)
    stdout.write(
        f"Final summary: {passed}/{len(outcomes)} contract verification(s) passed.\n"
    )
    stdout.write(f"Verification artifact: {artifact_path}\n")

    if all(outcome.success for outcome in outcomes) and outcomes:
        return 0

    for outcome in outcomes:
        if outcome.error_message:
            stderr.write(f"ERROR[{outcome.contract}]: {outcome.error_message}\n")
    return 2


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
