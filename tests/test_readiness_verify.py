from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from ninjatradebuilder.readiness_verify import run_cli as run_readiness_verify_cli

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "readiness"
PACKETS_FIXTURE = Path(__file__).parent / "fixtures" / "packets.valid.json"
SUPPORTED_CONTRACTS = ("ES", "NQ", "CL", "ZN", "6E", "MGC")
TIMESTAMPS_BY_CONTRACT = {
    "ES": "2026-01-14T15:05:00Z",
    "NQ": "2026-01-14T15:05:00Z",
    "CL": "2026-01-14T14:05:00Z",
    "ZN": "2026-01-14T15:05:00Z",
    "6E": "2026-01-14T14:05:00Z",
    "MGC": "2026-01-14T15:05:00Z",
}
MACRO_STATE_BY_CONTRACT = {
    "ES": '"contract_specific_macro_state": "breadth_cash_delta_aligned"',
    "NQ": '"contract_specific_macro_state": "relative_strength_leader"',
    "CL": '"contract_specific_macro_state": "eia_sensitive"',
    "ZN": '"contract_specific_macro_state": "auction_sensitive"',
    "6E": '"contract_specific_macro_state": "dxy_supported_europe_drive"',
    "MGC": '"contract_specific_macro_state": "macro_supportive"',
}


def _valid_readiness_output(contract: str) -> dict[str, Any]:
    return {
        "$schema": "readiness_engine_output_v1",
        "stage": "readiness_engine",
        "authority": "ESCALATE_ONLY",
        "contract": contract,
        "timestamp": TIMESTAMPS_BY_CONTRACT[contract],
        "status": "WAIT_FOR_TRIGGER",
        "doctrine_gates": [
            {"gate": "data_sufficiency_gate", "state": "PASS", "rationale": "Inputs are complete."},
            {"gate": "context_alignment_gate", "state": "PASS", "rationale": "Context remains aligned."},
            {"gate": "structure_quality_gate", "state": "PASS", "rationale": "Structure remains acceptable."},
            {"gate": "trigger_gate", "state": "WAIT", "rationale": "Waiting for the recheck time."},
            {"gate": "risk_window_gate", "state": "PASS", "rationale": "Risk window remains open."},
            {"gate": "lockout_gate", "state": "PASS", "rationale": "No lockout is active."},
        ],
        "trigger_data": {
            "family": "recheck_at_time",
            "recheck_at_time": "2026-01-14T15:15:00Z",
            "price_level": None,
        },
        "wait_for_trigger_reason": "timing_window_not_open",
        "lockout_reason": None,
        "insufficient_data_reasons": [],
        "missing_inputs": [],
    }


def _contract_from_prompt(rendered_prompt: str) -> str:
    for contract, marker in MACRO_STATE_BY_CONTRACT.items():
        if marker in rendered_prompt:
            return contract
    raise AssertionError("Unable to determine contract from rendered prompt.")


class _FakeGeminiAdapter:
    def __init__(self, *, client, model, timeout_seconds=None, max_retries=0):
        self.client = client
        self.model = model

    def generate_structured(self, request):
        return _valid_readiness_output(_contract_from_prompt(request.rendered_prompt))


def test_readiness_verify_fixture_sweep_writes_summary_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("ninjatradebuilder.readiness_verify.GeminiResponsesAdapter", _FakeGeminiAdapter)
    stdout = io.StringIO()
    stderr = io.StringIO()
    artifact_path = tmp_path / "readiness-artifact.json"

    exit_code = run_readiness_verify_cli(
        ["--fixture-sweep", "--artifact-path", str(artifact_path)],
        stdout=stdout,
        stderr=stderr,
        client_factory=lambda config: config,
    )

    assert exit_code == 0
    output = stdout.getvalue()
    for contract in SUPPORTED_CONTRACTS:
        assert contract in output
    assert "Final summary: 6/6 contract verification(s) passed." in output
    assert str(artifact_path) in output
    assert stderr.getvalue() == ""

    artifact = json.loads(artifact_path.read_text())
    assert artifact["artifact_schema"] == "readiness_live_verification_v1"
    assert artifact["success"] is True
    assert artifact["model_name"] == "gemini-3.1-pro-preview"
    assert artifact["contracts_verified"] == list(SUPPORTED_CONTRACTS)
    assert len(artifact["results"]) == 6
    assert {result["contract"] for result in artifact["results"]} == set(SUPPORTED_CONTRACTS)
    assert all(result["prompt_hash"] for result in artifact["results"])


def test_readiness_verify_fails_closed_on_malformed_live_response(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class MalformedGeminiAdapter:
        def __init__(self, *, client, model, timeout_seconds=None, max_retries=0):
            self.client = client

        def generate_structured(self, request):
            contract = _contract_from_prompt(request.rendered_prompt)
            payload = _valid_readiness_output(contract)
            payload["stage"] = "contract_market_read"
            return payload

    monkeypatch.setattr(
        "ninjatradebuilder.readiness_verify.GeminiResponsesAdapter",
        MalformedGeminiAdapter,
    )
    stdout = io.StringIO()
    stderr = io.StringIO()
    artifact_path = tmp_path / "malformed-artifact.json"

    exit_code = run_readiness_verify_cli(
        [
            "--packet",
            str(PACKETS_FIXTURE),
            "--contract",
            "ES",
            "--trigger",
            str(FIXTURES_DIR / "zn_recheck_trigger.valid.json"),
            "--artifact-path",
            str(artifact_path),
        ],
        stdout=stdout,
        stderr=stderr,
        client_factory=lambda config: config,
    )

    assert exit_code == 2
    assert "schema=fail" in stdout.getvalue()
    assert "ERROR[ES]:" in stderr.getvalue()
    artifact = json.loads(artifact_path.read_text())
    assert artifact["success"] is False
    assert artifact["results"][0]["success"] is False
    assert artifact["results"][0]["error_type"] == "ValueError"
    assert artifact["results"][0]["raw_response_excerpt"] is not None


def test_readiness_verify_requires_gemini_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    stdout = io.StringIO()
    stderr = io.StringIO()
    artifact_path = tmp_path / "missing-key-artifact.json"

    exit_code = run_readiness_verify_cli(
        ["--fixture-sweep", "--artifact-path", str(artifact_path)],
        stdout=stdout,
        stderr=stderr,
        client_factory=lambda config: config,
    )

    assert exit_code == 2
    assert "Final summary: 0/1 contract verification(s) passed." in stdout.getvalue()
    assert "GEMINI_API_KEY is required for CLI execution." in stderr.getvalue()
    artifact = json.loads(artifact_path.read_text())
    assert artifact["success"] is False
    assert artifact["results"][0]["invocation_mode"] == "startup"


def test_readiness_verify_rejects_missing_input_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    stdout = io.StringIO()
    stderr = io.StringIO()
    artifact_path = tmp_path / "missing-input-artifact.json"

    exit_code = run_readiness_verify_cli(
        [
            "--runtime-inputs",
            str(tmp_path / "missing-runtime-inputs.json"),
            "--trigger",
            str(FIXTURES_DIR / "zn_recheck_trigger.valid.json"),
            "--artifact-path",
            str(artifact_path),
        ],
        stdout=stdout,
        stderr=stderr,
        client_factory=lambda config: config,
    )

    assert exit_code == 2
    assert "Runtime inputs file does not exist" in stderr.getvalue()
    artifact = json.loads(artifact_path.read_text())
    assert artifact["results"][0]["success"] is False
    assert artifact["results"][0]["error_type"] == "ValueError"
