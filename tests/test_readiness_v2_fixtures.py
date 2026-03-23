from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from ninjatradebuilder.readiness_v2 import run_operator_harness
from ninjatradebuilder.schemas.readiness_v2 import (
    ReadinessV2BootstrapArtifact,
    ReadinessV2ReplayArtifact,
    ReadinessV2UpdateArtifact,
    ReadinessWatchV1,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "readiness_v2"
FORBIDDEN_OPERATOR_PATTERNS = (
    re.compile(r"\bentry\b", re.IGNORECASE),
    re.compile(r"(?<!hard-)\bstop(?:\s+loss)?\b", re.IGNORECASE),
    re.compile(r"\btarget(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bsize(?:d|ing)?\b", re.IGNORECASE),
    re.compile(r"\bauthoriz(?:e|ation|ed|ing)\b", re.IGNORECASE),
    re.compile(r"\bapprove(?:d|s|al)?\b", re.IGNORECASE),
    re.compile(r"\breject(?:ed|ion|s)?\b", re.IGNORECASE),
)


def _load_fixture_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _run_harness(argv: list[str]) -> dict:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_operator_harness(argv, stdout=stdout, stderr=stderr)
    assert exit_code == 0, stderr.getvalue()
    assert stderr.getvalue() == ""
    return json.loads(stdout.getvalue())


def _assert_grounded_text(payload: dict) -> None:
    briefing_claims = {
        claim["claim_id"]: claim for claim in payload["briefing"]["thesis_claims"]
    }
    assert payload["briefing"]["narrative_feature_thesis"] == " ".join(
        briefing_claims[claim_id]["statement"]
        for claim_id in payload["briefing"]["narrative_feature_thesis_claim_ids"]
    )
    assert all(claim["provenance"] for claim in payload["briefing"]["thesis_claims"])
    assert all(summary["provenance"] for summary in payload["briefing"]["candidate_trigger_summaries"])
    assert all(rule["provenance"] for rule in payload["briefing"]["invalidation_conditions"])
    for trigger in payload["query_triggers"]:
        trigger_claims = {claim["claim_id"]: claim for claim in trigger["operator_claims"]}
        assert trigger["operator_explanation"] == " ".join(
            trigger_claims[claim_id]["statement"]
            for claim_id in trigger["operator_explanation_claim_ids"]
        )
        assert all(claim["provenance"] for claim in trigger["operator_claims"])


def _assert_grounded_watch(payload: dict) -> None:
    watch_claims = {claim["claim_id"]: claim for claim in payload["watch"]["operator_claims"]}
    assert payload["watch"]["operator_summary"] == " ".join(
        watch_claims[claim_id]["statement"]
        for claim_id in payload["watch"]["operator_summary_claim_ids"]
    )
    assert all(claim["provenance"] for claim in payload["watch"]["operator_claims"])


def _assert_grounded_watch_payload(watch: dict) -> None:
    watch_claims = {claim["claim_id"]: claim for claim in watch["operator_claims"]}
    assert watch["operator_summary"] == " ".join(
        watch_claims[claim_id]["statement"]
        for claim_id in watch["operator_summary_claim_ids"]
    )
    assert all(claim["provenance"] for claim in watch["operator_claims"])


def _assert_history_continuity(payload: dict) -> None:
    watch = payload["watch"]
    assert len(watch["history"]) == watch["revision"]
    assert watch["history"][-1]["revision"] == watch["revision"]
    assert watch["history"][-1]["state"] == watch["state"]
    assert watch["history"][-1]["routing_recommendation"] == watch["routing_recommendation"]
    assert watch["history"][-1]["trigger_truth_state"] == watch["last_observation"]["trigger_truth_state"]
    assert watch["history"][-1]["packet_timestamp"] == watch["context_snapshot"]["packet_timestamp"]
    assert watch["history"][-1]["detected_change_kinds"] == [
        change["kind"] for change in watch["detected_changes"]
    ]


def _assert_replay_continuity(payload: dict) -> None:
    final_watch = payload["final_watch"]
    assert payload["bootstrap"]["watch_id"] == final_watch["watch_id"]
    assert len(payload["steps"]) == final_watch["revision"]
    assert [step["revision"] for step in payload["steps"]] == list(
        range(1, final_watch["revision"] + 1)
    )
    assert payload["steps"][0]["phase"] == "bootstrap"
    assert all(step["phase"] == "update" for step in payload["steps"][1:])
    assert payload["steps"][-1]["state"] == final_watch["state"]
    assert payload["steps"][-1]["routing_recommendation"] == final_watch["routing_recommendation"]
    assert payload["invariants"] == {
        "watch_id_stable": True,
        "revisions_contiguous": True,
        "evaluation_timestamps_monotonic": True,
        "packet_timestamps_monotonic": True,
    }


def _assert_bounded_operator_surface(payload: dict) -> None:
    texts: list[str] = []

    if payload["mode"] == "bootstrap":
        briefing = payload["briefing"]
        texts.append(briefing["narrative_feature_thesis"])
        for summary in briefing["candidate_trigger_summaries"]:
            assert summary["supporting_claim_ids"]
            assert summary["provenance"]
            texts.append(summary["summary"])

        for trigger in payload["query_triggers"]:
            assert trigger["unlock_action"] == "ROUTE_STAGE_AB_REANALYSIS"
            assert trigger["validation_status"] == "EXECUTABLE"
            texts.append(trigger["operator_explanation"])

        watch = payload["watch"]
    elif payload["mode"] == "update":
        watch = payload["watch"]
    else:
        watch = payload["final_watch"]

    texts.append(watch["operator_summary"])
    assert watch["source_kind"] == "premarket_briefing"
    assert watch["source_refs"]["preserved_contract_analysis_ref"] is None
    assert watch["routing_target"] != "STAGE_C_REENTRY"
    assert watch["state"] != "READY_FOR_SETUP_REENTRY"
    assert watch["routing_recommendation"] in {"WAIT", "REQUERY_STAGE_B", "EXPIRE_WATCH"}

    for text in texts:
        for pattern in FORBIDDEN_OPERATOR_PATTERNS:
            assert pattern.search(text) is None, text


def test_readiness_v2_fixture_bootstrap_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("zn_bootstrap.expected.json")
    ReadinessV2BootstrapArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "bootstrap",
            "--packet",
            str(FIXTURES_DIR / "zn_bootstrap.packet.valid.json"),
        ]
    )

    ReadinessV2BootstrapArtifact.model_validate(actual)
    _assert_grounded_text(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_es_bootstrap_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("es_bootstrap.expected.json")
    ReadinessV2BootstrapArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "bootstrap",
            "--packet",
            str(FIXTURES_DIR / "es_bootstrap.packet.valid.json"),
        ]
    )

    ReadinessV2BootstrapArtifact.model_validate(actual)
    _assert_grounded_text(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_nq_bootstrap_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("nq_bootstrap.expected.json")
    ReadinessV2BootstrapArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "bootstrap",
            "--packet",
            str(FIXTURES_DIR / "nq_bootstrap.packet.valid.json"),
        ]
    )

    ReadinessV2BootstrapArtifact.model_validate(actual)
    _assert_grounded_text(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_cl_bootstrap_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("cl_bootstrap.expected.json")
    ReadinessV2BootstrapArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "bootstrap",
            "--packet",
            str(FIXTURES_DIR / "cl_bootstrap.packet.valid.json"),
        ]
    )

    ReadinessV2BootstrapArtifact.model_validate(actual)
    _assert_grounded_text(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_mgc_bootstrap_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("mgc_bootstrap.expected.json")
    ReadinessV2BootstrapArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "bootstrap",
            "--packet",
            str(FIXTURES_DIR / "mgc_bootstrap.packet.valid.json"),
        ]
    )

    ReadinessV2BootstrapArtifact.model_validate(actual)
    _assert_grounded_text(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_6e_bootstrap_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("6e_bootstrap.expected.json")
    ReadinessV2BootstrapArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "bootstrap",
            "--packet",
            str(FIXTURES_DIR / "6e_bootstrap.packet.valid.json"),
        ]
    )

    ReadinessV2BootstrapArtifact.model_validate(actual)
    _assert_grounded_text(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


@pytest.mark.parametrize(
    ("packet_name", "evaluation_timestamp", "expected_name"),
    [
        (
            "zn_update_wait.packet.valid.json",
            "2026-01-14T15:10:00Z",
            "zn_update_wait.expected.json",
        ),
        (
            "zn_update_requery.packet.valid.json",
            "2026-01-14T15:07:00Z",
            "zn_update_requery.expected.json",
        ),
        (
            "zn_update_invalidation.packet.valid.json",
            "2026-01-14T15:08:00Z",
            "zn_update_invalidation.expected.json",
        ),
    ],
)
def test_readiness_v2_fixture_update_artifacts_match_golden_output(
    packet_name: str,
    evaluation_timestamp: str,
    expected_name: str,
) -> None:
    prior_watch = _load_fixture_json("zn_initial_watch.valid.json")
    expected = _load_fixture_json(expected_name)
    ReadinessWatchV1.model_validate(prior_watch)
    ReadinessV2UpdateArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "update",
            "--prior-watch",
            str(FIXTURES_DIR / "zn_initial_watch.valid.json"),
            "--packet",
            str(FIXTURES_DIR / packet_name),
            "--evaluation-timestamp",
            evaluation_timestamp,
        ]
    )

    ReadinessV2UpdateArtifact.model_validate(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


@pytest.mark.parametrize(
    ("packet_name", "evaluation_timestamp", "expected_name"),
    [
        (
            "es_update_wait.packet.valid.json",
            "2026-01-14T15:10:00Z",
            "es_update_wait.expected.json",
        ),
        (
            "es_update_requery.packet.valid.json",
            "2026-01-14T15:12:00Z",
            "es_update_requery.expected.json",
        ),
    ],
)
def test_readiness_v2_fixture_es_update_artifacts_match_golden_output(
    packet_name: str,
    evaluation_timestamp: str,
    expected_name: str,
) -> None:
    prior_watch = _load_fixture_json("es_initial_watch.valid.json")
    expected = _load_fixture_json(expected_name)
    ReadinessWatchV1.model_validate(prior_watch)
    ReadinessV2UpdateArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "update",
            "--prior-watch",
            str(FIXTURES_DIR / "es_initial_watch.valid.json"),
            "--packet",
            str(FIXTURES_DIR / packet_name),
            "--evaluation-timestamp",
            evaluation_timestamp,
        ]
    )

    ReadinessV2UpdateArtifact.model_validate(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


@pytest.mark.parametrize(
    ("packet_name", "evaluation_timestamp", "expected_name"),
    [
        (
            "nq_update_wait.packet.valid.json",
            "2026-01-14T15:10:00Z",
            "nq_update_wait.expected.json",
        ),
        (
            "nq_update_requery.packet.valid.json",
            "2026-01-14T15:12:00Z",
            "nq_update_requery.expected.json",
        ),
    ],
)
def test_readiness_v2_fixture_nq_update_artifacts_match_golden_output(
    packet_name: str,
    evaluation_timestamp: str,
    expected_name: str,
) -> None:
    prior_watch = _load_fixture_json("nq_initial_watch.valid.json")
    expected = _load_fixture_json(expected_name)
    ReadinessWatchV1.model_validate(prior_watch)
    ReadinessV2UpdateArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "update",
            "--prior-watch",
            str(FIXTURES_DIR / "nq_initial_watch.valid.json"),
            "--packet",
            str(FIXTURES_DIR / packet_name),
            "--evaluation-timestamp",
            evaluation_timestamp,
        ]
    )

    ReadinessV2UpdateArtifact.model_validate(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


@pytest.mark.parametrize(
    ("packet_name", "evaluation_timestamp", "expected_name"),
    [
        (
            "cl_update_wait.packet.valid.json",
            "2026-01-14T15:10:00Z",
            "cl_update_wait.expected.json",
        ),
        (
            "cl_update_requery.packet.valid.json",
            "2026-01-14T15:12:00Z",
            "cl_update_requery.expected.json",
        ),
    ],
)
def test_readiness_v2_fixture_cl_update_artifacts_match_golden_output(
    packet_name: str,
    evaluation_timestamp: str,
    expected_name: str,
) -> None:
    prior_watch = _load_fixture_json("cl_initial_watch.valid.json")
    expected = _load_fixture_json(expected_name)
    ReadinessWatchV1.model_validate(prior_watch)
    ReadinessV2UpdateArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "update",
            "--prior-watch",
            str(FIXTURES_DIR / "cl_initial_watch.valid.json"),
            "--packet",
            str(FIXTURES_DIR / packet_name),
            "--evaluation-timestamp",
            evaluation_timestamp,
        ]
    )

    ReadinessV2UpdateArtifact.model_validate(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


@pytest.mark.parametrize(
    ("packet_name", "evaluation_timestamp", "expected_name"),
    [
        (
            "mgc_update_wait.packet.valid.json",
            "2026-01-14T15:10:00Z",
            "mgc_update_wait.expected.json",
        ),
        (
            "mgc_update_requery.packet.valid.json",
            "2026-01-14T15:12:00Z",
            "mgc_update_requery.expected.json",
        ),
    ],
)
def test_readiness_v2_fixture_mgc_update_artifacts_match_golden_output(
    packet_name: str,
    evaluation_timestamp: str,
    expected_name: str,
) -> None:
    prior_watch = _load_fixture_json("mgc_initial_watch.valid.json")
    expected = _load_fixture_json(expected_name)
    ReadinessWatchV1.model_validate(prior_watch)
    ReadinessV2UpdateArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "update",
            "--prior-watch",
            str(FIXTURES_DIR / "mgc_initial_watch.valid.json"),
            "--packet",
            str(FIXTURES_DIR / packet_name),
            "--evaluation-timestamp",
            evaluation_timestamp,
        ]
    )

    ReadinessV2UpdateArtifact.model_validate(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


@pytest.mark.parametrize(
    ("packet_name", "evaluation_timestamp", "expected_name"),
    [
        (
            "6e_update_wait.packet.valid.json",
            "2026-01-14T15:10:00Z",
            "6e_update_wait.expected.json",
        ),
        (
            "6e_update_requery.packet.valid.json",
            "2026-01-14T15:12:00Z",
            "6e_update_requery.expected.json",
        ),
    ],
)
def test_readiness_v2_fixture_6e_update_artifacts_match_golden_output(
    packet_name: str,
    evaluation_timestamp: str,
    expected_name: str,
) -> None:
    prior_watch = _load_fixture_json("6e_initial_watch.valid.json")
    expected = _load_fixture_json(expected_name)
    ReadinessWatchV1.model_validate(prior_watch)
    ReadinessV2UpdateArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "update",
            "--prior-watch",
            str(FIXTURES_DIR / "6e_initial_watch.valid.json"),
            "--packet",
            str(FIXTURES_DIR / packet_name),
            "--evaluation-timestamp",
            evaluation_timestamp,
        ]
    )

    ReadinessV2UpdateArtifact.model_validate(actual)
    _assert_grounded_watch(actual)
    _assert_history_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_replay_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("zn_replay.expected.json")
    ReadinessV2ReplayArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "replay",
            "--packet",
            str(FIXTURES_DIR / "zn_bootstrap.packet.valid.json"),
            "--updates",
            str(FIXTURES_DIR / "zn_replay.updates.valid.json"),
        ]
    )

    ReadinessV2ReplayArtifact.model_validate(actual)
    _assert_grounded_watch_payload(actual["final_watch"])
    _assert_replay_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_es_replay_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("es_replay.expected.json")
    ReadinessV2ReplayArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "replay",
            "--packet",
            str(FIXTURES_DIR / "es_bootstrap.packet.valid.json"),
            "--updates",
            str(FIXTURES_DIR / "es_replay.updates.valid.json"),
        ]
    )

    ReadinessV2ReplayArtifact.model_validate(actual)
    _assert_grounded_watch_payload(actual["final_watch"])
    _assert_replay_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_nq_replay_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("nq_replay.expected.json")
    ReadinessV2ReplayArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "replay",
            "--packet",
            str(FIXTURES_DIR / "nq_bootstrap.packet.valid.json"),
            "--updates",
            str(FIXTURES_DIR / "nq_replay.updates.valid.json"),
        ]
    )

    ReadinessV2ReplayArtifact.model_validate(actual)
    _assert_grounded_watch_payload(actual["final_watch"])
    _assert_replay_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_cl_replay_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("cl_replay.expected.json")
    ReadinessV2ReplayArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "replay",
            "--packet",
            str(FIXTURES_DIR / "cl_bootstrap.packet.valid.json"),
            "--updates",
            str(FIXTURES_DIR / "cl_replay.updates.valid.json"),
        ]
    )

    ReadinessV2ReplayArtifact.model_validate(actual)
    _assert_grounded_watch_payload(actual["final_watch"])
    _assert_replay_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_mgc_replay_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("mgc_replay.expected.json")
    ReadinessV2ReplayArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "replay",
            "--packet",
            str(FIXTURES_DIR / "mgc_bootstrap.packet.valid.json"),
            "--updates",
            str(FIXTURES_DIR / "mgc_replay.updates.valid.json"),
        ]
    )

    ReadinessV2ReplayArtifact.model_validate(actual)
    _assert_grounded_watch_payload(actual["final_watch"])
    _assert_replay_continuity(actual)
    assert actual == expected


def test_readiness_v2_fixture_6e_replay_artifact_matches_golden_output() -> None:
    expected = _load_fixture_json("6e_replay.expected.json")
    ReadinessV2ReplayArtifact.model_validate(expected)

    actual = _run_harness(
        [
            "replay",
            "--packet",
            str(FIXTURES_DIR / "6e_bootstrap.packet.valid.json"),
            "--updates",
            str(FIXTURES_DIR / "6e_replay.updates.valid.json"),
        ]
    )

    ReadinessV2ReplayArtifact.model_validate(actual)
    _assert_grounded_watch_payload(actual["final_watch"])
    _assert_replay_continuity(actual)
    assert actual == expected


@pytest.mark.parametrize(
    "artifact_name",
    [
        "zn_bootstrap.expected.json",
        "es_bootstrap.expected.json",
        "nq_bootstrap.expected.json",
        "cl_bootstrap.expected.json",
        "mgc_bootstrap.expected.json",
        "6e_bootstrap.expected.json",
        "zn_update_wait.expected.json",
        "zn_update_requery.expected.json",
        "zn_update_invalidation.expected.json",
        "es_update_wait.expected.json",
        "es_update_requery.expected.json",
        "nq_update_wait.expected.json",
        "nq_update_requery.expected.json",
        "cl_update_wait.expected.json",
        "cl_update_requery.expected.json",
        "mgc_update_wait.expected.json",
        "mgc_update_requery.expected.json",
        "6e_update_wait.expected.json",
        "6e_update_requery.expected.json",
        "zn_replay.expected.json",
        "es_replay.expected.json",
        "nq_replay.expected.json",
        "cl_replay.expected.json",
        "mgc_replay.expected.json",
        "6e_replay.expected.json",
    ],
)
def test_readiness_v2_expected_artifacts_preserve_bounded_operator_authority(
    artifact_name: str,
) -> None:
    payload = _load_fixture_json(artifact_name)
    _assert_bounded_operator_surface(payload)
