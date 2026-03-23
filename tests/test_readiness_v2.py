from __future__ import annotations

import copy
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import ninjatradebuilder.readiness_v2.harness as harness_module
from ninjatradebuilder.readiness_v2 import (
    get_contract_adapter,
    supported_contracts,
    WatchStateEvaluation,
    build_cl_premarket_briefing,
    build_cl_initial_query_triggers,
    build_cl_initial_readiness_watch,
    build_es_premarket_briefing,
    build_mgc_premarket_briefing,
    build_mgc_initial_query_triggers,
    build_mgc_initial_readiness_watch,
    build_nq_premarket_briefing,
    build_nq_initial_query_triggers,
    build_nq_initial_readiness_watch,
    build_sixe_premarket_briefing,
    build_sixe_initial_query_triggers,
    build_sixe_initial_readiness_watch,
    build_zn_initial_query_triggers,
    build_zn_initial_readiness_watch,
    build_zn_premarket_briefing,
    replay_cl_readiness_sequence,
    replay_es_readiness_sequence,
    replay_mgc_readiness_sequence,
    replay_nq_readiness_sequence,
    replay_sixe_readiness_sequence,
    replay_zn_readiness_sequence,
    run_operator_harness,
    transition_watch_state,
    update_cl_readiness_watch,
    update_es_readiness_watch,
    update_mgc_readiness_watch,
    update_nq_readiness_watch,
    update_sixe_readiness_watch,
    update_zn_readiness_watch,
)
from ninjatradebuilder.schemas.readiness_v2 import (
    PremarketBriefingV1,
    QueryTriggerV1,
    ReadinessV2BootstrapArtifact,
    ReadinessV2ReplayArtifact,
    ReadinessWatchV1,
)
from ninjatradebuilder.validation import validate_historical_packet

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_packet_bundle() -> dict:
    return json.loads((FIXTURES_DIR / "packets.valid.json").read_text())


def _historical_packet(contract: str) -> dict:
    bundle = _load_packet_bundle()
    return {
        "$schema": "historical_packet_v1",
        "challenge_state": copy.deepcopy(bundle["shared"]["challenge_state"]),
        "contract_metadata": copy.deepcopy(bundle["contracts"][contract]["contract_metadata"]),
        "market_packet": copy.deepcopy(bundle["contracts"][contract]["market_packet"]),
        "contract_specific_extension": copy.deepcopy(
            bundle["contracts"][contract]["contract_specific_extension"]
        ),
        "attached_visuals": copy.deepcopy(bundle["shared"]["attached_visuals"]),
    }


def _zn_packet():
    return validate_historical_packet(_historical_packet("ZN"))


def _es_bootstrap_packet_payload() -> dict:
    payload = _historical_packet("ES")
    payload["market_packet"]["current_price"] = 5030.5
    payload["market_packet"]["current_session_vah"] = 5030.5
    return payload


def _es_packet():
    return validate_historical_packet(_es_bootstrap_packet_payload())


def _nq_bootstrap_packet_payload() -> dict:
    payload = _historical_packet("NQ")
    payload["market_packet"]["current_price"] = 18120.0
    payload["market_packet"]["current_session_vah"] = 18128.0
    return payload


def _nq_packet():
    return validate_historical_packet(_nq_bootstrap_packet_payload())


def _cl_bootstrap_packet_payload() -> dict:
    payload = _historical_packet("CL")
    payload["market_packet"]["current_price"] = 73.30
    payload["market_packet"]["current_session_vah"] = 73.35
    return payload


def _cl_packet():
    return validate_historical_packet(_cl_bootstrap_packet_payload())


def _mgc_bootstrap_packet_payload() -> dict:
    payload = _historical_packet("MGC")
    payload["market_packet"]["current_price"] = 2053.2
    payload["market_packet"]["current_session_vah"] = 2053.8
    return payload


def _mgc_packet():
    return validate_historical_packet(_mgc_bootstrap_packet_payload())


def _sixe_bootstrap_packet_payload() -> dict:
    payload = _historical_packet("6E")
    payload["market_packet"]["current_price"] = 1.09115
    payload["market_packet"]["current_session_vah"] = 1.0914
    return payload


def _sixe_packet():
    return validate_historical_packet(_sixe_bootstrap_packet_payload())


def _build_watch() -> ReadinessWatchV1:
    packet = _zn_packet()
    briefing = build_zn_premarket_briefing(packet)
    triggers = build_zn_initial_query_triggers(packet, briefing)
    return build_zn_initial_readiness_watch(packet, briefing, triggers)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _joined_claim_text(claims: list[dict], claim_ids: list[str]) -> str:
    claim_lookup = {claim["claim_id"]: claim for claim in claims}
    return " ".join(claim_lookup[claim_id]["statement"] for claim_id in claim_ids)


def _zn_replay_updates() -> list[dict]:
    wait_packet_one = _historical_packet("ZN")
    wait_packet_one["market_packet"]["timestamp"] = "2026-01-14T15:10:00Z"

    wait_packet_two = _historical_packet("ZN")
    wait_packet_two["market_packet"]["timestamp"] = "2026-01-14T15:11:00Z"

    requery_packet = _historical_packet("ZN")
    requery_packet["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_packet["market_packet"]["current_price"] = 110.4296875

    return [
        {
            "packet": wait_packet_one,
            "evaluation_timestamp": "2026-01-14T15:10:00Z",
        },
        {
            "packet": wait_packet_two,
            "evaluation_timestamp": "2026-01-14T15:11:00Z",
        },
        {
            "packet": requery_packet,
            "evaluation_timestamp": "2026-01-14T15:12:00Z",
        },
    ]


def _es_replay_updates() -> list[dict]:
    wait_packet_one = _es_bootstrap_packet_payload()
    wait_packet_one["market_packet"]["timestamp"] = "2026-01-14T15:10:00Z"

    wait_packet_two = _es_bootstrap_packet_payload()
    wait_packet_two["market_packet"]["timestamp"] = "2026-01-14T15:11:00Z"

    requery_packet = _es_bootstrap_packet_payload()
    requery_packet["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_packet["market_packet"]["current_price"] = 5040.0

    return [
        {
            "packet": wait_packet_one,
            "evaluation_timestamp": "2026-01-14T15:10:00Z",
        },
        {
            "packet": wait_packet_two,
            "evaluation_timestamp": "2026-01-14T15:11:00Z",
        },
        {
            "packet": requery_packet,
            "evaluation_timestamp": "2026-01-14T15:12:00Z",
        },
    ]


def _nq_replay_updates() -> list[dict]:
    wait_packet_one = _nq_bootstrap_packet_payload()
    wait_packet_one["market_packet"]["timestamp"] = "2026-01-14T15:10:00Z"

    wait_packet_two = _nq_bootstrap_packet_payload()
    wait_packet_two["market_packet"]["timestamp"] = "2026-01-14T15:11:00Z"

    requery_packet = _nq_bootstrap_packet_payload()
    requery_packet["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_packet["market_packet"]["current_price"] = 18128.0
    requery_packet["market_packet"]["current_session_vah"] = 18127.75

    return [
        {
            "packet": wait_packet_one,
            "evaluation_timestamp": "2026-01-14T15:10:00Z",
        },
        {
            "packet": wait_packet_two,
            "evaluation_timestamp": "2026-01-14T15:11:00Z",
        },
        {
            "packet": requery_packet,
            "evaluation_timestamp": "2026-01-14T15:12:00Z",
        },
    ]


def _cl_replay_updates() -> list[dict]:
    wait_packet_one = _cl_bootstrap_packet_payload()
    wait_packet_one["market_packet"]["timestamp"] = "2026-01-14T15:10:00Z"
    wait_packet_one["market_packet"]["current_price"] = 73.31

    wait_packet_two = _cl_bootstrap_packet_payload()
    wait_packet_two["market_packet"]["timestamp"] = "2026-01-14T15:11:00Z"
    wait_packet_two["market_packet"]["current_price"] = 73.32

    requery_packet = _cl_bootstrap_packet_payload()
    requery_packet["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_packet["market_packet"]["current_price"] = 73.35
    requery_packet["market_packet"]["current_session_vah"] = 73.34

    return [
        {
            "packet": wait_packet_one,
            "evaluation_timestamp": "2026-01-14T15:10:00Z",
        },
        {
            "packet": wait_packet_two,
            "evaluation_timestamp": "2026-01-14T15:11:00Z",
        },
        {
            "packet": requery_packet,
            "evaluation_timestamp": "2026-01-14T15:12:00Z",
        },
    ]


def _mgc_replay_updates() -> list[dict]:
    wait_packet_one = _mgc_bootstrap_packet_payload()
    wait_packet_one["market_packet"]["timestamp"] = "2026-01-14T15:10:00Z"
    wait_packet_one["market_packet"]["current_price"] = 2053.3

    wait_packet_two = _mgc_bootstrap_packet_payload()
    wait_packet_two["market_packet"]["timestamp"] = "2026-01-14T15:11:00Z"
    wait_packet_two["market_packet"]["current_price"] = 2053.4

    requery_packet = _mgc_bootstrap_packet_payload()
    requery_packet["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_packet["market_packet"]["current_price"] = 2053.8
    requery_packet["market_packet"]["current_session_vah"] = 2053.7

    return [
        {
            "packet": wait_packet_one,
            "evaluation_timestamp": "2026-01-14T15:10:00Z",
        },
        {
            "packet": wait_packet_two,
            "evaluation_timestamp": "2026-01-14T15:11:00Z",
        },
        {
            "packet": requery_packet,
            "evaluation_timestamp": "2026-01-14T15:12:00Z",
        },
    ]


def _sixe_replay_updates() -> list[dict]:
    wait_packet_one = _sixe_bootstrap_packet_payload()
    wait_packet_one["market_packet"]["timestamp"] = "2026-01-14T15:10:00Z"
    wait_packet_one["market_packet"]["current_price"] = 1.09118

    wait_packet_two = _sixe_bootstrap_packet_payload()
    wait_packet_two["market_packet"]["timestamp"] = "2026-01-14T15:11:00Z"
    wait_packet_two["market_packet"]["current_price"] = 1.0912

    requery_packet = _sixe_bootstrap_packet_payload()
    requery_packet["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_packet["market_packet"]["current_price"] = 1.0914
    requery_packet["market_packet"]["current_session_vah"] = 1.09135

    return [
        {
            "packet": wait_packet_one,
            "evaluation_timestamp": "2026-01-14T15:10:00Z",
        },
        {
            "packet": wait_packet_two,
            "evaluation_timestamp": "2026-01-14T15:11:00Z",
        },
        {
            "packet": requery_packet,
            "evaluation_timestamp": "2026-01-14T15:12:00Z",
        },
    ]


def test_zn_v2_briefing_is_grounded_in_validated_packet_fields() -> None:
    briefing = build_zn_premarket_briefing(_zn_packet())

    assert isinstance(briefing, PremarketBriefingV1)
    assert briefing.model_dump(by_alias=True)["$schema"] == "premarket_briefing_v1"
    assert briefing.contract == "ZN"
    assert briefing.feature_snapshot.directional_lean == "BULLISH"
    assert briefing.feature_snapshot.cash_10y_yield == 4.12
    assert briefing.feature_snapshot.price_location_vs_vwap == "ABOVE"
    assert briefing.monitor_posture == "MONITOR"
    assert briefing.candidate_trigger_summaries[0].family == "price_level_touch"
    assert briefing.candidate_trigger_summaries[0].price_level == 110.421875
    assert briefing.candidate_trigger_summaries[1].family == "recheck_at_time"
    assert "prior-day high 110.5 in play" in briefing.narrative_feature_thesis
    assert "CPI slightly soft, yields initially down then stabilized." in briefing.narrative_feature_thesis
    assert {claim.claim_id for claim in briefing.thesis_claims} == {
        "value_support_or_resistance",
        "flow_alignment",
        "macro_context",
        "event_risk_window",
    }
    assert briefing.narrative_feature_thesis_claim_ids == [
        "value_support_or_resistance",
        "macro_context",
        "event_risk_window",
    ]
    assert all(claim.provenance for claim in briefing.thesis_claims)
    assert briefing.candidate_trigger_summaries[0].supporting_claim_ids == [
        "value_support_or_resistance",
        "flow_alignment",
    ]
    assert all(summary.provenance for summary in briefing.candidate_trigger_summaries)
    assert briefing.invalidation_conditions[0].price_level == 110.296875
    assert briefing.invalidation_conditions[0].provenance
    assert [rule.kind for rule in briefing.invalidation_conditions] == ["PRICE_BREACH"]


def test_es_v2_briefing_is_grounded_in_validated_packet_fields() -> None:
    briefing = build_es_premarket_briefing(_es_packet())

    assert isinstance(briefing, PremarketBriefingV1)
    assert briefing.model_dump(by_alias=True)["$schema"] == "premarket_briefing_v1"
    assert briefing.contract == "ES"
    assert briefing.feature_snapshot.directional_lean == "BULLISH"
    assert briefing.feature_snapshot.breadth == "positive +1120"
    assert briefing.feature_snapshot.index_cash_tone == "bullish"
    assert "CPI released 95 minutes ago" in briefing.feature_snapshot.macro_release_context
    assert briefing.monitor_posture == "MONITOR"
    assert briefing.candidate_trigger_summaries[0].family == "price_level_touch"
    assert briefing.candidate_trigger_summaries[0].price_level == 5040.0
    assert briefing.candidate_trigger_summaries[1].family == "recheck_at_time"
    assert "prior-day high 5040 in play" in briefing.narrative_feature_thesis
    assert all(claim.provenance for claim in briefing.thesis_claims)
    assert briefing.invalidation_conditions[0].price_level == 5019.0


def test_nq_v2_briefing_is_grounded_in_validated_packet_fields() -> None:
    briefing = build_nq_premarket_briefing(_nq_packet())

    assert isinstance(briefing, PremarketBriefingV1)
    assert briefing.model_dump(by_alias=True)["$schema"] == "premarket_briefing_v1"
    assert briefing.contract == "NQ"
    assert briefing.feature_snapshot.directional_lean == "BULLISH"
    assert briefing.feature_snapshot.relative_strength_vs_es == 1.18
    assert briefing.feature_snapshot.megacap_leadership_posture == "megacap leadership is supportive (2 up, 1 flat)"
    assert briefing.feature_snapshot.bond_yield_context == "rising"
    assert briefing.monitor_posture == "MONITOR"
    assert briefing.candidate_trigger_summaries[0].family == "price_level_touch"
    assert briefing.candidate_trigger_summaries[0].price_level == 18128.0
    assert briefing.candidate_trigger_summaries[1].family == "recheck_at_time"
    assert "Relative strength vs ES is 1.18" in briefing.thesis_claims[1].statement
    assert all(claim.provenance for claim in briefing.thesis_claims)
    assert briefing.invalidation_conditions[0].price_level == 18062.25


def test_cl_v2_briefing_is_grounded_in_validated_packet_fields() -> None:
    briefing = build_cl_premarket_briefing(_cl_packet())

    assert isinstance(briefing, PremarketBriefingV1)
    assert briefing.model_dump(by_alias=True)["$schema"] == "premarket_briefing_v1"
    assert briefing.contract == "CL"
    assert briefing.feature_snapshot.directional_lean == "BULLISH"
    assert briefing.feature_snapshot.eia_timing_context == (
        "EIA Petroleum Status Report is scheduled for 2026-01-14T15:30:00Z in 85 minutes."
    )
    assert briefing.feature_snapshot.realized_volatility_context == "normal"
    assert briefing.feature_snapshot.liquidity_sweep_summary == (
        "Sell-side sweep below the overnight low failed to continue."
    )
    assert briefing.feature_snapshot.dom_liquidity_summary == "Bid stack rebuilding near session VWAP."
    assert briefing.feature_snapshot.cross_market_context == "equity tone risk-on, dxy direction flat"
    assert briefing.monitor_posture == "MONITOR"
    assert briefing.candidate_trigger_summaries[0].family == "price_level_touch"
    assert briefing.candidate_trigger_summaries[0].price_level == 73.35
    assert briefing.candidate_trigger_summaries[1].family == "recheck_at_time"
    assert "CL is holding above VWAP 73.07" in briefing.narrative_feature_thesis
    assert "EIA timing is 'EIA Petroleum Status Report is scheduled for 2026-01-14T15:30:00Z in 85 minutes.'" in briefing.thesis_claims[2].statement
    assert all(claim.provenance for claim in briefing.thesis_claims)
    assert briefing.invalidation_conditions[0].price_level == 72.9


def test_mgc_v2_briefing_is_grounded_in_validated_packet_fields() -> None:
    briefing = build_mgc_premarket_briefing(_mgc_packet())

    assert isinstance(briefing, PremarketBriefingV1)
    assert briefing.model_dump(by_alias=True)["$schema"] == "premarket_briefing_v1"
    assert briefing.contract == "MGC"
    assert briefing.feature_snapshot.directional_lean == "BULLISH"
    assert briefing.feature_snapshot.dxy_context == "weakening"
    assert briefing.feature_snapshot.yield_context == "falling"
    assert briefing.feature_snapshot.macro_fear_catalyst_summary == "none"
    assert briefing.feature_snapshot.swing_penetration_volume_summary == (
        "High volume acceptance above the weekly pivot."
    )
    assert briefing.feature_snapshot.cross_market_context == "equity tone risk-off, silver direction up"
    assert briefing.monitor_posture == "MONITOR"
    assert briefing.candidate_trigger_summaries[0].family == "price_level_touch"
    assert briefing.candidate_trigger_summaries[0].price_level == 2053.8
    assert briefing.candidate_trigger_summaries[1].family == "recheck_at_time"
    assert "MGC is holding above VWAP 2050.9" in briefing.narrative_feature_thesis
    assert "DXY is 'weakening', yields are 'falling'" in briefing.thesis_claims[2].statement
    assert all(claim.provenance for claim in briefing.thesis_claims)
    assert briefing.invalidation_conditions[0].price_level == 2049.6


def test_6e_v2_briefing_is_grounded_in_validated_packet_fields() -> None:
    briefing = build_sixe_premarket_briefing(_sixe_packet())

    assert isinstance(briefing, PremarketBriefingV1)
    assert briefing.model_dump(by_alias=True)["$schema"] == "premarket_briefing_v1"
    assert briefing.contract == "6E"
    assert briefing.feature_snapshot.directional_lean == "BULLISH"
    assert briefing.feature_snapshot.dxy_context == "weakening"
    assert briefing.feature_snapshot.europe_initiative_status == "Europe drove higher"
    assert briefing.feature_snapshot.asia_high_low.high == 1.0892
    assert briefing.feature_snapshot.london_high_low.high == 1.0914
    assert briefing.feature_snapshot.ny_high_low_so_far.high == 1.0916
    assert briefing.feature_snapshot.cross_market_context == "dxy direction weakening"
    assert briefing.monitor_posture == "MONITOR"
    assert briefing.candidate_trigger_summaries[0].family == "price_level_touch"
    assert briefing.candidate_trigger_summaries[0].price_level == 1.0914
    assert briefing.candidate_trigger_summaries[1].family == "recheck_at_time"
    assert "Europe drove higher" in briefing.thesis_claims[1].statement
    assert "DXY is 'weakening'" in briefing.thesis_claims[2].statement
    assert all(claim.provenance for claim in briefing.thesis_claims)
    assert briefing.invalidation_conditions[0].price_level == 1.0899


def test_zn_v2_builders_reject_non_zn_packets() -> None:
    with pytest.raises(ValueError, match="only supports ZN"):
        build_zn_premarket_briefing(validate_historical_packet(_historical_packet("ES")))


def test_readiness_v2_contract_adapter_registry_resolves_supported_contracts() -> None:
    sixe_adapter = get_contract_adapter("6E")
    cl_adapter = get_contract_adapter("CL")
    zn_adapter = get_contract_adapter("ZN")
    es_adapter = get_contract_adapter("ES")
    mgc_adapter = get_contract_adapter("MGC")
    nq_adapter = get_contract_adapter("NQ")

    assert sixe_adapter.contract == "6E"
    assert cl_adapter.contract == "CL"
    assert zn_adapter.contract == "ZN"
    assert es_adapter.contract == "ES"
    assert mgc_adapter.contract == "MGC"
    assert nq_adapter.contract == "NQ"
    assert supported_contracts() == ("6E", "CL", "ES", "MGC", "NQ", "ZN")


def test_readiness_v2_contract_adapter_registry_rejects_unknown_contract() -> None:
    with pytest.raises(ValueError, match="Unsupported readiness v2 contract: GC"):
        get_contract_adapter("GC")


@pytest.mark.parametrize(
    ("contract", "expected_contract"),
    [("ZN", "ZN"), ("ES", "ES"), ("NQ", "NQ"), ("CL", "CL"), ("MGC", "MGC"), ("6E", "6E")],
)
def test_readiness_v2_harness_requires_explicit_contract_for_bundle_inputs(
    tmp_path: Path,
    contract: str,
    expected_contract: str,
) -> None:
    bundle_path = tmp_path / "packets.bundle.json"
    _write_json(bundle_path, _load_packet_bundle())

    stdout = io.StringIO()
    stderr = io.StringIO()
    missing_contract_exit_code = run_operator_harness(
        [
            "bootstrap",
            "--packet",
            str(bundle_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert missing_contract_exit_code == 2
    assert stdout.getvalue() == ""
    assert "Multi-contract bundle inputs require --contract to select 6E, CL, ES, MGC, NQ, ZN." in stderr.getvalue()

    stdout = io.StringIO()
    stderr = io.StringIO()
    explicit_contract_exit_code = run_operator_harness(
        [
            "bootstrap",
            "--packet",
            str(bundle_path),
            "--contract",
            contract,
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert explicit_contract_exit_code == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue())["contract"] == expected_contract


def test_zn_v2_query_triggers_keep_canonical_trigger_families() -> None:
    packet = _zn_packet()
    briefing = build_zn_premarket_briefing(packet)
    triggers = build_zn_initial_query_triggers(packet, briefing)

    assert [trigger.family for trigger in triggers] == [
        "price_level_touch",
        "recheck_at_time",
    ]
    assert all(isinstance(trigger, QueryTriggerV1) for trigger in triggers)
    assert triggers[0].deterministic_parameters.price_level == 110.421875
    assert triggers[0].deterministic_parameters.buffer_ticks == 0
    assert triggers[0].post_trigger_policy == "STRUCTURE_CONFIRMATION_REQUIRED"
    assert triggers[0].operator_explanation_claim_ids == [
        "trigger_touch_level",
        "trigger_invalidation_guard",
    ]
    assert all(trigger.operator_claims for trigger in triggers)
    assert triggers[1].deterministic_parameters.recheck_at_time == datetime.fromisoformat(
        "2026-01-14T15:20:00+00:00"
    )
    assert triggers[1].operator_explanation_claim_ids == ["timed_recheck_window"]
    assert all(trigger.unlock_action == "ROUTE_STAGE_AB_REANALYSIS" for trigger in triggers)


def test_readiness_v2_contract_specific_context_snapshots_remain_distinct() -> None:
    zn_briefing = build_zn_premarket_briefing(_zn_packet())
    zn_watch = build_zn_initial_readiness_watch(
        _zn_packet(),
        zn_briefing,
        build_zn_initial_query_triggers(_zn_packet(), zn_briefing),
    )
    es_briefing = build_es_premarket_briefing(_es_packet())
    es_watch = get_contract_adapter("ES").bootstrap(_es_packet()).watch
    nq_briefing = build_nq_premarket_briefing(_nq_packet())
    nq_watch = build_nq_initial_readiness_watch(
        _nq_packet(),
        nq_briefing,
        build_nq_initial_query_triggers(_nq_packet(), nq_briefing),
    )
    cl_briefing = build_cl_premarket_briefing(_cl_packet())
    cl_watch = build_cl_initial_readiness_watch(
        _cl_packet(),
        cl_briefing,
        build_cl_initial_query_triggers(_cl_packet(), cl_briefing),
    )
    mgc_briefing = build_mgc_premarket_briefing(_mgc_packet())
    mgc_watch = build_mgc_initial_readiness_watch(
        _mgc_packet(),
        mgc_briefing,
        build_mgc_initial_query_triggers(_mgc_packet(), mgc_briefing),
    )
    sixe_briefing = build_sixe_premarket_briefing(_sixe_packet())
    sixe_watch = build_sixe_initial_readiness_watch(
        _sixe_packet(),
        sixe_briefing,
        build_sixe_initial_query_triggers(_sixe_packet(), sixe_briefing),
    )

    zn_context = zn_watch.context_snapshot.model_dump(mode="json")
    es_context = es_watch.context_snapshot.model_dump(mode="json")
    nq_context = nq_watch.context_snapshot.model_dump(mode="json")
    cl_context = cl_watch.context_snapshot.model_dump(mode="json")
    mgc_context = mgc_watch.context_snapshot.model_dump(mode="json")
    sixe_context = sixe_watch.context_snapshot.model_dump(mode="json")

    assert "treasury_auction_schedule" in zn_context
    assert "auction_proximity_state" in zn_context
    assert "breadth" not in zn_context
    assert "index_cash_tone" not in zn_context

    assert "breadth" in es_context
    assert "index_cash_tone" in es_context
    assert "treasury_auction_schedule" not in es_context
    assert "auction_proximity_state" not in es_context

    assert "relative_strength_vs_es" in nq_context
    assert "megacap_leadership_posture" in nq_context
    assert "bond_yield_context" in nq_context
    assert "breadth" not in nq_context
    assert "index_cash_tone" not in nq_context
    assert "treasury_auction_schedule" not in nq_context

    assert "eia_timing_context" in cl_context
    assert "realized_volatility_context" in cl_context
    assert "liquidity_sweep_summary" in cl_context
    assert "dom_liquidity_summary" in cl_context
    assert "cross_market_context" in cl_context
    assert "breadth" not in cl_context
    assert "relative_strength_vs_es" not in cl_context
    assert "treasury_auction_schedule" not in cl_context

    assert "dxy_context" in mgc_context
    assert "yield_context" in mgc_context
    assert "macro_fear_catalyst_summary" in mgc_context
    assert "swing_penetration_volume_summary" in mgc_context
    assert "cross_market_context" in mgc_context
    assert "relative_strength_vs_es" not in mgc_context
    assert "eia_timing_context" not in mgc_context
    assert "treasury_auction_schedule" not in mgc_context

    assert "asia_high_low" in sixe_context
    assert "london_high_low" in sixe_context
    assert "ny_high_low_so_far" in sixe_context
    assert "dxy_context" in sixe_context
    assert "europe_initiative_status" in sixe_context
    assert "cross_market_context" in sixe_context
    assert "yield_context" not in sixe_context
    assert "relative_strength_vs_es" not in sixe_context
    assert "treasury_auction_schedule" not in sixe_context


def test_zn_v2_watch_initializes_as_armed_waiting_with_stage_ab_boundary_preserved() -> None:
    packet = _zn_packet()
    briefing = build_zn_premarket_briefing(packet)
    triggers = build_zn_initial_query_triggers(packet, briefing)
    watch = build_zn_initial_readiness_watch(packet, briefing, triggers)

    assert isinstance(watch, ReadinessWatchV1)
    assert watch.model_dump(by_alias=True)["$schema"] == "readiness_watch_v1"
    assert watch.state == "ARMED_WAITING"
    assert watch.routing_target == "NONE"
    assert watch.routing_recommendation == "WAIT"
    assert watch.active_trigger_family == "price_level_touch"
    assert watch.post_trigger_policy == "STRUCTURE_CONFIRMATION_REQUIRED"
    assert watch.source_refs.active_trigger_id == triggers[0].trigger_id
    assert watch.allowed_next_actions == ["EVALUATE_TRIGGER", "DISARM_WATCH"]
    assert watch.context_snapshot.freshness_state == "FRESH"
    assert watch.context_snapshot.lockout_reasons == []
    assert watch.context_snapshot.event_risk_state == "CLEAR"
    assert watch.context_snapshot.auction_proximity_state == "SCHEDULED"
    assert watch.context_snapshot.value_location_state == "INSIDE_VALUE"
    assert [rule.kind for rule in watch.invalidation_rules] == ["PRICE_BREACH"]
    assert watch.detected_changes == []
    assert watch.revision == 1
    assert watch.prior_watch_id is None
    assert watch.prior_revision is None
    assert len(watch.history) == 1
    assert watch.history[0].transition_reason == "initialized"
    assert watch.history[0].change_summary == "Initialized watch at revision 1 in ARMED_WAITING with WAIT."
    assert watch.operator_summary_claim_ids == [
        "watch_state_reason",
        "watch_routing_reason",
    ]
    assert all(claim.provenance for claim in watch.operator_claims)


@pytest.mark.parametrize("contract", ["ZN", "ES", "NQ", "CL", "MGC", "6E"])
def test_readiness_v2_bootstrap_artifact_enforces_shared_timestamp_alignment(
    contract: str,
) -> None:
    adapter = get_contract_adapter(contract)
    if contract == "ZN":
        packet = _zn_packet()
    elif contract == "ES":
        packet = _es_packet()
    elif contract == "NQ":
        packet = _nq_packet()
    elif contract == "CL":
        packet = _cl_packet()
    elif contract == "6E":
        packet = _sixe_packet()
    else:
        packet = _mgc_packet()
    artifact = adapter.bootstrap(packet)
    invalid_payload = artifact.model_dump(by_alias=True, mode="json")
    invalid_payload["query_triggers"][0]["created_at"] = "2026-01-14T15:21:00Z"

    with pytest.raises(
        ValidationError,
        match="query_triggers.created_at must match evaluation_timestamp",
    ):
        ReadinessV2BootstrapArtifact.model_validate(invalid_payload)


@pytest.mark.parametrize("contract", ["ZN", "ES", "NQ", "CL", "MGC", "6E"])
def test_readiness_v2_replay_artifact_enforces_contract_alignment(contract: str) -> None:
    if contract == "ZN":
        artifact = replay_zn_readiness_sequence(_zn_packet(), _zn_replay_updates())
        invalid_contract = "ES"
    elif contract == "ES":
        artifact = replay_es_readiness_sequence(_es_packet(), _es_replay_updates())
        invalid_contract = "ZN"
    elif contract == "NQ":
        artifact = replay_nq_readiness_sequence(_nq_packet(), _nq_replay_updates())
        invalid_contract = "ES"
    elif contract == "CL":
        artifact = replay_cl_readiness_sequence(_cl_packet(), _cl_replay_updates())
        invalid_contract = "ZN"
    elif contract == "6E":
        artifact = replay_sixe_readiness_sequence(_sixe_packet(), _sixe_replay_updates())
        invalid_contract = "ZN"
    else:
        artifact = replay_mgc_readiness_sequence(_mgc_packet(), _mgc_replay_updates())
        invalid_contract = "ZN"

    invalid_payload = artifact.model_dump(by_alias=True, mode="json")
    invalid_payload["contract"] = invalid_contract

    with pytest.raises(
        ValidationError,
        match="Replay artifact contract must match final_watch.contract",
    ):
        ReadinessV2ReplayArtifact.model_validate(invalid_payload)


def test_zn_v2_briefing_stale_packet_stands_aside() -> None:
    packet = _zn_packet()
    briefing = build_zn_premarket_briefing(
        packet,
        created_at=datetime.fromisoformat("2026-01-14T15:11:00+00:00"),
    )

    assert briefing.session_snapshot.freshness_state == "STALE"
    assert briefing.monitor_posture == "STAND_ASIDE"


def test_zn_v2_watch_rejects_trigger_sets_from_other_briefings() -> None:
    packet = _zn_packet()
    briefing = build_zn_premarket_briefing(packet)
    triggers = build_zn_initial_query_triggers(packet, briefing)
    invalid_trigger_payload = triggers[0].model_dump(by_alias=True)
    invalid_trigger_payload["source_briefing_id"] = "zn-briefing-foreign"
    invalid_trigger = QueryTriggerV1.model_validate(invalid_trigger_payload)

    with pytest.raises(ValueError, match="originate from the supplied briefing"):
        build_zn_initial_readiness_watch(packet, briefing, [invalid_trigger, triggers[1]])


def test_zn_v2_watch_schema_rejects_stage_c_reentry_boundary_break() -> None:
    packet = _zn_packet()
    briefing = build_zn_premarket_briefing(packet)
    triggers = build_zn_initial_query_triggers(packet, briefing)
    watch = build_zn_initial_readiness_watch(packet, briefing, triggers)
    invalid_watch_payload = watch.model_dump(by_alias=True)
    invalid_watch_payload["routing_target"] = "STAGE_C_REENTRY"

    with pytest.raises(ValidationError, match="does not support STAGE_C_REENTRY"):
        ReadinessWatchV1.model_validate(invalid_watch_payload)


def test_zn_v2_schema_rejects_narrative_text_without_matching_claim_support() -> None:
    packet = _zn_packet()
    briefing = build_zn_premarket_briefing(packet)
    invalid_briefing_payload = briefing.model_dump(by_alias=True, mode="json")
    invalid_briefing_payload["narrative_feature_thesis"] += " Ungrounded addition."

    with pytest.raises(ValidationError, match="ordered join"):
        PremarketBriefingV1.model_validate(invalid_briefing_payload)

    trigger = build_zn_initial_query_triggers(packet, briefing)[0]
    invalid_trigger_payload = trigger.model_dump(by_alias=True, mode="json")
    invalid_trigger_payload["operator_explanation"] = "Ungrounded trigger explanation."

    with pytest.raises(ValidationError, match="ordered join"):
        QueryTriggerV1.model_validate(invalid_trigger_payload)

    watch = build_zn_initial_readiness_watch(packet, briefing, build_zn_initial_query_triggers(packet, briefing))
    invalid_watch_payload = watch.model_dump(by_alias=True, mode="json")
    invalid_watch_payload["operator_summary"] = "Ungrounded watch summary."

    with pytest.raises(ValidationError, match="ordered join"):
        ReadinessWatchV1.model_validate(invalid_watch_payload)


def test_zn_v2_watch_schema_rejects_incoherent_history_continuity() -> None:
    watch = _build_watch()
    invalid_watch_payload = watch.model_dump(by_alias=True, mode="json")
    invalid_watch_payload["revision"] = 2

    with pytest.raises(ValidationError, match="prior_watch_id = watch_id"):
        ReadinessWatchV1.model_validate(invalid_watch_payload)


def test_zn_v2_watch_update_stays_waiting_when_trigger_is_not_satisfied() -> None:
    watch = _build_watch()
    updated = update_zn_readiness_watch(
        watch,
        _zn_packet(),
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:10:00+00:00"),
    )

    assert updated.state == "ARMED_WAITING"
    assert updated.routing_recommendation == "WAIT"
    assert updated.routing_target == "NONE"
    assert updated.context_snapshot.freshness_state == "FRESH"
    assert updated.detected_changes == []
    assert updated.revision == 2
    assert updated.prior_watch_id == watch.watch_id
    assert updated.prior_revision == 1
    assert len(updated.history) == 2
    assert updated.history[-1].transition_reason == "no_material_change"


def test_zn_v2_watch_update_transitions_to_requery_on_price_touch_and_value_shift() -> None:
    watch = _build_watch()
    packet_payload = _historical_packet("ZN")
    packet_payload["market_packet"]["timestamp"] = "2026-01-14T15:07:00Z"
    packet_payload["market_packet"]["current_price"] = 110.4296875
    updated_packet = validate_historical_packet(packet_payload)

    updated = update_zn_readiness_watch(
        watch,
        updated_packet,
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:07:00+00:00"),
    )

    assert updated.state == "READY_FOR_REANALYSIS"
    assert updated.routing_recommendation == "REQUERY_STAGE_B"
    assert updated.routing_target == "STAGE_AB_REANALYSIS"
    assert updated.last_observation.trigger_truth_state == "OBSERVED"
    assert updated.context_snapshot.value_location_state == "ABOVE_VAH"
    assert updated.revision == 2
    assert updated.history[-1].transition_reason == "trigger_requery_ready"
    assert updated.operator_summary_claim_ids == [
        "watch_state_reason",
        "watch_routing_reason",
    ]
    assert {change.kind for change in updated.detected_changes} == {
        "value_location_change",
        "trigger_truth_change",
        "routing_recommendation_change",
    }


def test_zn_v2_watch_update_marks_stale_packet_as_context_contaminated() -> None:
    watch = _build_watch()
    packet_payload = _historical_packet("ZN")
    packet_payload["market_packet"]["timestamp"] = "2026-01-14T15:05:00Z"
    updated_packet = validate_historical_packet(packet_payload)

    updated = update_zn_readiness_watch(
        watch,
        updated_packet,
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:11:00+00:00"),
    )

    assert updated.state == "CONTEXT_CONTAMINATED"
    assert updated.routing_recommendation == "WAIT"
    assert updated.context_snapshot.freshness_state == "STALE"
    assert "packet_stale" in updated.context_snapshot.contamination_reasons
    assert updated.history[-1].transition_reason == "context_contaminated"
    assert {change.kind for change in updated.detected_changes} == {"freshness_state_change"}


def test_zn_v2_watch_update_enters_lockout_when_session_closes() -> None:
    watch = _build_watch()
    packet_payload = _historical_packet("ZN")
    packet_payload["market_packet"]["timestamp"] = "2026-01-14T19:50:00Z"
    updated_packet = validate_historical_packet(packet_payload)

    updated = update_zn_readiness_watch(
        watch,
        updated_packet,
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T19:50:00+00:00"),
    )

    assert updated.state == "LOCKED_OUT"
    assert updated.routing_recommendation == "WAIT"
    assert updated.context_snapshot.session_access_state == "OUTSIDE_ALLOWED_HOURS"
    assert "outside_allowed_hours" in updated.context_snapshot.lockout_reasons
    assert updated.history[-1].transition_reason == "lockout_applied"
    assert {change.kind for change in updated.detected_changes} == {
        "session_access_change",
        "auction_proximity_change",
    }


def test_zn_v2_watch_update_expires_on_thesis_invalidation() -> None:
    watch = _build_watch()
    packet_payload = _historical_packet("ZN")
    packet_payload["market_packet"]["timestamp"] = "2026-01-14T15:08:00Z"
    packet_payload["market_packet"]["current_price"] = 110.28125
    updated_packet = validate_historical_packet(packet_payload)

    updated = update_zn_readiness_watch(
        watch,
        updated_packet,
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:08:00+00:00"),
    )

    assert updated.state == "THESIS_INVALIDATED"
    assert updated.routing_recommendation == "EXPIRE_WATCH"
    assert updated.routing_target == "NONE"
    assert updated.terminal_reason == "deterministic_invalidation_condition_met"
    assert updated.history[-1].transition_reason == "thesis_invalidated"
    assert updated.operator_summary_claim_ids == [
        "watch_state_reason",
        "watch_routing_reason",
        "watch_invalidation_reason",
    ]
    assert {change.kind for change in updated.detected_changes} == {
        "value_location_change",
        "trigger_invalidation",
        "thesis_invalidation",
        "routing_recommendation_change",
    }


def test_zn_v2_watch_update_expires_when_ttl_is_reached() -> None:
    watch = _build_watch()
    packet_payload = _historical_packet("ZN")
    packet_payload["market_packet"]["timestamp"] = watch.expiry_policy.expires_at.isoformat().replace(
        "+00:00", "Z"
    )
    updated_packet = validate_historical_packet(packet_payload)

    updated = update_zn_readiness_watch(
        watch,
        updated_packet,
        evaluation_timestamp=watch.expiry_policy.expires_at,
    )

    assert updated.state == "TERMINAL_EXPIRED"
    assert updated.routing_recommendation == "EXPIRE_WATCH"
    assert updated.terminal_reason == "explicit_expiry_reached"
    assert updated.history[-1].transition_reason == "watch_expired"
    assert {change.kind for change in updated.detected_changes} == {
        "session_access_change",
        "auction_proximity_change",
        "trigger_invalidation",
        "routing_recommendation_change",
    }


def test_zn_v2_watch_update_fails_closed_on_incoherent_terminal_or_time_regression() -> None:
    watch = _build_watch()
    invalid_watch_payload = watch.model_dump(by_alias=True)
    invalid_watch_payload["state"] = "TERMINAL_EXPIRED"
    invalid_watch_payload["routing_recommendation"] = "EXPIRE_WATCH"
    invalid_watch_payload["terminal_reason"] = "already_expired"
    invalid_watch_payload["last_observation"]["context_change"] = "TERMINAL_EXPIRED"
    invalid_watch_payload["history"][-1]["state"] = "TERMINAL_EXPIRED"
    invalid_watch_payload["history"][-1]["routing_recommendation"] = "EXPIRE_WATCH"
    invalid_watch_payload["history"][-1]["transition_reason"] = "watch_expired"
    invalid_watch_payload["history"][-1]["change_summary"] = (
        "Expiry advanced the watch to TERMINAL_EXPIRED with EXPIRE_WATCH."
    )
    invalid_watch_payload["history"][-1]["terminal_reason"] = "already_expired"
    terminal_watch = ReadinessWatchV1.model_validate(invalid_watch_payload)

    with pytest.raises(ValueError, match="Completed or terminal readiness watches cannot be advanced"):
        update_zn_readiness_watch(
            terminal_watch,
            _zn_packet(),
            evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:06:00+00:00"),
        )

    with pytest.raises(ValueError, match="at or after prior_watch.updated_at"):
        update_zn_readiness_watch(
            watch,
            _zn_packet(),
            evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:04:00+00:00"),
        )

    packet_payload = _historical_packet("ZN")
    packet_payload["market_packet"]["timestamp"] = "2026-01-14T15:04:00Z"
    with pytest.raises(ValueError, match="packet timestamp must be at or after"):
        update_zn_readiness_watch(
            watch,
            validate_historical_packet(packet_payload),
            evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:06:00+00:00"),
        )


def test_zn_v2_watch_sequence_progresses_with_revision_continuity() -> None:
    packet = _zn_packet()
    briefing = build_zn_premarket_briefing(packet)
    triggers = build_zn_initial_query_triggers(packet, briefing)
    bootstrap_watch = build_zn_initial_readiness_watch(packet, briefing, triggers)

    wait_watch = update_zn_readiness_watch(
        bootstrap_watch,
        packet,
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:10:00+00:00"),
    )
    assert wait_watch.revision == 2
    assert wait_watch.history[-1].transition_reason == "no_material_change"

    requery_payload = _historical_packet("ZN")
    requery_payload["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_payload["market_packet"]["current_price"] = 110.4296875
    requery_watch = update_zn_readiness_watch(
        wait_watch,
        validate_historical_packet(requery_payload),
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:12:00+00:00"),
    )

    assert requery_watch.revision == 3
    assert requery_watch.prior_revision == 2
    assert [entry.revision for entry in requery_watch.history] == [1, 2, 3]
    assert requery_watch.history[-1].transition_reason == "trigger_requery_ready"

    with pytest.raises(ValueError, match="Completed or terminal readiness watches cannot be advanced"):
        update_zn_readiness_watch(
            requery_watch,
            validate_historical_packet(requery_payload),
            evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:13:00+00:00"),
        )


def test_zn_v2_replay_sequence_advances_bootstrap_wait_wait_requery() -> None:
    replay = replay_zn_readiness_sequence(_zn_packet(), _zn_replay_updates())

    assert isinstance(replay, ReadinessV2ReplayArtifact)
    assert replay.model_dump(by_alias=True)["$schema"] == "readiness_v2_replay_artifact_v1"
    assert replay.mode == "replay"
    assert [step.revision for step in replay.steps] == [1, 2, 3, 4]
    assert [step.phase for step in replay.steps] == ["bootstrap", "update", "update", "update"]
    assert [step.state for step in replay.steps] == [
        "ARMED_WAITING",
        "ARMED_WAITING",
        "ARMED_WAITING",
        "READY_FOR_REANALYSIS",
    ]
    assert [step.routing_recommendation for step in replay.steps] == [
        "WAIT",
        "WAIT",
        "WAIT",
        "REQUERY_STAGE_B",
    ]
    assert replay.final_watch.revision == 4
    assert replay.final_watch.state == "READY_FOR_REANALYSIS"
    assert replay.final_watch.routing_recommendation == "REQUERY_STAGE_B"
    assert replay.invariants.watch_id_stable is True
    assert replay.invariants.revisions_contiguous is True
    assert replay.invariants.evaluation_timestamps_monotonic is True
    assert replay.invariants.packet_timestamps_monotonic is True


def test_zn_v2_replay_rejects_non_monotonic_timestamps() -> None:
    invalid_updates = _zn_replay_updates()
    invalid_updates[1]["evaluation_timestamp"] = "2026-01-14T15:09:00Z"

    with pytest.raises(ValueError, match="at or after prior_watch.updated_at"):
        replay_zn_readiness_sequence(_zn_packet(), invalid_updates)


def test_zn_v2_replay_rejects_follow_on_update_after_terminal_watch() -> None:
    invalidation_packet = _historical_packet("ZN")
    invalidation_packet["market_packet"]["timestamp"] = "2026-01-14T15:08:00Z"
    invalidation_packet["market_packet"]["current_price"] = 110.28125
    updates = [
        {
            "packet": invalidation_packet,
            "evaluation_timestamp": "2026-01-14T15:08:00Z",
        },
        {
            "packet": _historical_packet("ZN"),
            "evaluation_timestamp": "2026-01-14T15:10:00Z",
        },
    ]

    with pytest.raises(ValueError, match="Completed or terminal readiness watches cannot be advanced"):
        replay_zn_readiness_sequence(_zn_packet(), updates)


def test_es_v2_adapter_bootstrap_update_and_replay_succeed() -> None:
    adapter = get_contract_adapter("ES")
    bootstrap_artifact = adapter.bootstrap(_es_packet())

    assert bootstrap_artifact.contract == "ES"
    assert bootstrap_artifact.watch.contract == "ES"
    assert bootstrap_artifact.watch.state == "ARMED_WAITING"
    assert bootstrap_artifact.watch.context_snapshot.value_location_state == "INSIDE_VALUE"

    requery_payload = _es_bootstrap_packet_payload()
    requery_payload["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_payload["market_packet"]["current_price"] = 5040.0
    updated_watch_artifact = adapter.update(
        bootstrap_artifact.watch,
        validate_historical_packet(requery_payload),
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:12:00+00:00"),
    )

    assert updated_watch_artifact.contract == "ES"
    assert updated_watch_artifact.watch.state == "READY_FOR_REANALYSIS"
    assert updated_watch_artifact.watch.routing_recommendation == "REQUERY_STAGE_B"

    replay_artifact = adapter.replay(_es_packet(), _es_replay_updates())
    assert replay_artifact.contract == "ES"
    assert replay_artifact.final_watch.contract == "ES"
    assert replay_artifact.final_watch.state == "READY_FOR_REANALYSIS"
    assert [step.revision for step in replay_artifact.steps] == [1, 2, 3, 4]


def test_nq_v2_adapter_bootstrap_update_and_replay_succeed() -> None:
    adapter = get_contract_adapter("NQ")
    bootstrap_artifact = adapter.bootstrap(_nq_packet())

    assert bootstrap_artifact.contract == "NQ"
    assert bootstrap_artifact.watch.contract == "NQ"
    assert bootstrap_artifact.watch.state == "ARMED_WAITING"
    assert bootstrap_artifact.watch.context_snapshot.value_location_state == "INSIDE_VALUE"

    requery_payload = _nq_bootstrap_packet_payload()
    requery_payload["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_payload["market_packet"]["current_price"] = 18128.0
    requery_payload["market_packet"]["current_session_vah"] = 18127.75
    updated_watch_artifact = adapter.update(
        bootstrap_artifact.watch,
        validate_historical_packet(requery_payload),
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:12:00+00:00"),
    )

    assert updated_watch_artifact.contract == "NQ"
    assert updated_watch_artifact.watch.state == "READY_FOR_REANALYSIS"
    assert updated_watch_artifact.watch.routing_recommendation == "REQUERY_STAGE_B"

    replay_artifact = adapter.replay(_nq_packet(), _nq_replay_updates())
    assert replay_artifact.contract == "NQ"
    assert replay_artifact.final_watch.contract == "NQ"
    assert replay_artifact.final_watch.state == "READY_FOR_REANALYSIS"
    assert [step.revision for step in replay_artifact.steps] == [1, 2, 3, 4]


def test_cl_v2_adapter_bootstrap_update_and_replay_succeed() -> None:
    adapter = get_contract_adapter("CL")
    bootstrap_artifact = adapter.bootstrap(_cl_packet())

    assert bootstrap_artifact.contract == "CL"
    assert bootstrap_artifact.watch.contract == "CL"
    assert bootstrap_artifact.watch.state == "ARMED_WAITING"
    assert bootstrap_artifact.watch.context_snapshot.value_location_state == "INSIDE_VALUE"

    requery_payload = _cl_bootstrap_packet_payload()
    requery_payload["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_payload["market_packet"]["current_price"] = 73.35
    requery_payload["market_packet"]["current_session_vah"] = 73.34
    updated_watch_artifact = adapter.update(
        bootstrap_artifact.watch,
        validate_historical_packet(requery_payload),
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:12:00+00:00"),
    )

    assert updated_watch_artifact.contract == "CL"
    assert updated_watch_artifact.watch.state == "READY_FOR_REANALYSIS"
    assert updated_watch_artifact.watch.routing_recommendation == "REQUERY_STAGE_B"

    replay_artifact = adapter.replay(_cl_packet(), _cl_replay_updates())
    assert replay_artifact.contract == "CL"
    assert replay_artifact.final_watch.contract == "CL"
    assert replay_artifact.final_watch.state == "READY_FOR_REANALYSIS"
    assert [step.revision for step in replay_artifact.steps] == [1, 2, 3, 4]


def test_mgc_v2_adapter_bootstrap_update_and_replay_succeed() -> None:
    adapter = get_contract_adapter("MGC")
    bootstrap_artifact = adapter.bootstrap(_mgc_packet())

    assert bootstrap_artifact.contract == "MGC"
    assert bootstrap_artifact.watch.contract == "MGC"
    assert bootstrap_artifact.watch.state == "ARMED_WAITING"
    assert bootstrap_artifact.watch.context_snapshot.value_location_state == "INSIDE_VALUE"

    requery_payload = _mgc_bootstrap_packet_payload()
    requery_payload["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_payload["market_packet"]["current_price"] = 2053.8
    requery_payload["market_packet"]["current_session_vah"] = 2053.7
    updated_watch_artifact = adapter.update(
        bootstrap_artifact.watch,
        validate_historical_packet(requery_payload),
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:12:00+00:00"),
    )

    assert updated_watch_artifact.contract == "MGC"
    assert updated_watch_artifact.watch.state == "READY_FOR_REANALYSIS"
    assert updated_watch_artifact.watch.routing_recommendation == "REQUERY_STAGE_B"

    replay_artifact = adapter.replay(_mgc_packet(), _mgc_replay_updates())
    assert replay_artifact.contract == "MGC"
    assert replay_artifact.final_watch.contract == "MGC"
    assert replay_artifact.final_watch.state == "READY_FOR_REANALYSIS"
    assert [step.revision for step in replay_artifact.steps] == [1, 2, 3, 4]


def test_6e_v2_adapter_bootstrap_update_and_replay_succeed() -> None:
    adapter = get_contract_adapter("6E")
    bootstrap_artifact = adapter.bootstrap(_sixe_packet())

    assert bootstrap_artifact.contract == "6E"
    assert bootstrap_artifact.watch.contract == "6E"
    assert bootstrap_artifact.watch.state == "ARMED_WAITING"
    assert bootstrap_artifact.watch.context_snapshot.value_location_state == "INSIDE_VALUE"

    requery_payload = _sixe_bootstrap_packet_payload()
    requery_payload["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_payload["market_packet"]["current_price"] = 1.0914
    requery_payload["market_packet"]["current_session_vah"] = 1.09135
    updated_watch_artifact = adapter.update(
        bootstrap_artifact.watch,
        validate_historical_packet(requery_payload),
        evaluation_timestamp=datetime.fromisoformat("2026-01-14T15:12:00+00:00"),
    )

    assert updated_watch_artifact.contract == "6E"
    assert updated_watch_artifact.watch.state == "READY_FOR_REANALYSIS"
    assert updated_watch_artifact.watch.routing_recommendation == "REQUERY_STAGE_B"

    replay_artifact = adapter.replay(_sixe_packet(), _sixe_replay_updates())
    assert replay_artifact.contract == "6E"
    assert replay_artifact.final_watch.contract == "6E"
    assert replay_artifact.final_watch.state == "READY_FOR_REANALYSIS"
    assert [step.revision for step in replay_artifact.steps] == [1, 2, 3, 4]


def test_readiness_v2_state_machine_handles_trigger_lockout_and_terminal_paths() -> None:
    now = datetime.fromisoformat("2026-01-14T15:05:00+00:00")

    observed = transition_watch_state(
        "ARMED_WAITING",
        WatchStateEvaluation(
            evaluated_at=now,
            trigger_observed=True,
            requires_structure_confirmation=True,
        ),
    )
    assert observed.next_state == "TRIGGER_OBSERVED"

    forming = transition_watch_state(
        "TRIGGER_OBSERVED",
        WatchStateEvaluation(
            evaluated_at=now,
            trigger_observed=True,
            requires_structure_confirmation=True,
        ),
    )
    assert forming.next_state == "STRUCTURE_FORMING"

    ready = transition_watch_state(
        "STRUCTURE_FORMING",
        WatchStateEvaluation(
            evaluated_at=now,
            requires_structure_confirmation=True,
            structure_confirmed=True,
        ),
    )
    assert ready.next_state == "READY_FOR_REANALYSIS"
    assert ready.routing_target == "STAGE_AB_REANALYSIS"
    assert ready.routing_recommendation == "REQUERY_STAGE_B"

    lockout = transition_watch_state(
        "ARMED_WAITING",
        WatchStateEvaluation(
            evaluated_at=now,
            lockout_reasons=["event_lockout_active"],
        ),
    )
    assert lockout.next_state == "LOCKED_OUT"
    assert lockout.routing_recommendation == "WAIT"

    contaminated = transition_watch_state(
        "ARMED_WAITING",
        WatchStateEvaluation(
            evaluated_at=now,
            contamination_reasons=["packet_stale"],
        ),
    )
    assert contaminated.next_state == "CONTEXT_CONTAMINATED"
    assert contaminated.routing_recommendation == "WAIT"

    terminal = transition_watch_state(
        "LOCKED_OUT",
        WatchStateEvaluation(
            evaluated_at=now,
            expired=True,
        ),
    )
    assert terminal.next_state == "TERMINAL_EXPIRED"
    assert terminal.terminal_reason == "explicit_expiry_reached"
    assert terminal.routing_recommendation == "EXPIRE_WATCH"


def test_readiness_v2_state_machine_rejects_stage_c_reentry_state() -> None:
    now = datetime.fromisoformat("2026-01-14T15:05:00+00:00")

    with pytest.raises(ValueError, match="outside the readiness v2 first-slice boundary"):
        transition_watch_state(
            "READY_FOR_SETUP_REENTRY",
            WatchStateEvaluation(
                evaluated_at=now,
            ),
        )


def test_readiness_v2_operator_harness_bootstrap_outputs_json_artifact(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "zn.packet.json"
    artifact_path = tmp_path / "bootstrap.artifact.json"
    _write_json(packet_path, _historical_packet("ZN"))
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_operator_harness(
        [
            "bootstrap",
            "--packet",
            str(packet_path),
            "--artifact-file",
            str(artifact_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["$schema"] == "readiness_v2_bootstrap_artifact_v1"
    assert payload["mode"] == "bootstrap"
    assert payload["contract"] == "ZN"
    assert payload["briefing"]["narrative_feature_thesis"] == _joined_claim_text(
        payload["briefing"]["thesis_claims"],
        payload["briefing"]["narrative_feature_thesis_claim_ids"],
    )
    assert [trigger["family"] for trigger in payload["query_triggers"]] == [
        "price_level_touch",
        "recheck_at_time",
    ]
    assert payload["query_triggers"][0]["operator_explanation"] == _joined_claim_text(
        payload["query_triggers"][0]["operator_claims"],
        payload["query_triggers"][0]["operator_explanation_claim_ids"],
    )
    assert payload["watch"]["$schema"] == "readiness_watch_v1"
    assert payload["watch"]["operator_summary"] == _joined_claim_text(
        payload["watch"]["operator_claims"],
        payload["watch"]["operator_summary_claim_ids"],
    )
    assert json.loads(artifact_path.read_text()) == payload


def test_readiness_v2_operator_harness_update_outputs_json_artifact(tmp_path: Path) -> None:
    watch = _build_watch()
    watch_path = tmp_path / "prior.watch.json"
    packet_path = tmp_path / "updated.packet.json"
    _write_json(watch_path, watch.model_dump(by_alias=True, mode="json"))

    packet_payload = _historical_packet("ZN")
    packet_payload["market_packet"]["timestamp"] = "2026-01-14T15:07:00Z"
    packet_payload["market_packet"]["current_price"] = 110.4296875
    _write_json(packet_path, packet_payload)

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_operator_harness(
        [
            "update",
            "--prior-watch",
            str(watch_path),
            "--packet",
            str(packet_path),
            "--evaluation-timestamp",
            "2026-01-14T15:07:00Z",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["$schema"] == "readiness_v2_watch_update_artifact_v1"
    assert payload["mode"] == "update"
    assert payload["prior_watch_id"] == watch.watch_id
    assert payload["watch"]["state"] == "READY_FOR_REANALYSIS"
    assert payload["watch"]["routing_recommendation"] == "REQUERY_STAGE_B"


def test_readiness_v2_operator_harness_replay_outputs_json_artifact(tmp_path: Path) -> None:
    packet_path = tmp_path / "zn.packet.json"
    updates_path = tmp_path / "replay.updates.json"
    artifact_path = tmp_path / "replay.artifact.json"
    _write_json(packet_path, _historical_packet("ZN"))
    _write_json(updates_path, _zn_replay_updates())

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_operator_harness(
        [
            "replay",
            "--packet",
            str(packet_path),
            "--updates",
            str(updates_path),
            "--artifact-file",
            str(artifact_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["$schema"] == "readiness_v2_replay_artifact_v1"
    assert payload["mode"] == "replay"
    assert [step["revision"] for step in payload["steps"]] == [1, 2, 3, 4]
    assert payload["steps"][-1]["state"] == "READY_FOR_REANALYSIS"
    assert payload["final_watch"]["state"] == "READY_FOR_REANALYSIS"
    assert payload["validation_status"] == "VALID"
    assert payload["invariants"] == {
        "watch_id_stable": True,
        "revisions_contiguous": True,
        "evaluation_timestamps_monotonic": True,
        "packet_timestamps_monotonic": True,
    }
    assert json.loads(artifact_path.read_text()) == payload


def test_readiness_v2_operator_harness_routes_through_contract_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_adapter = get_contract_adapter("ZN")
    calls: list[str] = []

    class RecordingAdapter:
        contract = "ZN"

        def bootstrap(
            self,
            packet: Any,
            *,
            evaluation_timestamp: datetime | None = None,
        ):
            calls.append("bootstrap")
            return real_adapter.bootstrap(packet, evaluation_timestamp=evaluation_timestamp)

        def update(
            self,
            prior_watch: ReadinessWatchV1,
            packet: Any,
            *,
            evaluation_timestamp: datetime,
        ):
            calls.append("update")
            return real_adapter.update(
                prior_watch,
                packet,
                evaluation_timestamp=evaluation_timestamp,
            )

        def replay(
            self,
            packet: Any,
            updates: list[dict[str, Any]],
            *,
            bootstrap_evaluation_time: datetime | None = None,
        ):
            calls.append("replay")
            return real_adapter.replay(
                packet,
                updates,
                bootstrap_evaluation_time=bootstrap_evaluation_time,
            )

    monkeypatch.setattr(harness_module, "get_contract_adapter", lambda contract: RecordingAdapter())

    bootstrap_packet_path = tmp_path / "bootstrap.packet.json"
    update_packet_path = tmp_path / "update.packet.json"
    replay_updates_path = tmp_path / "replay.updates.json"
    watch_path = tmp_path / "watch.json"

    _write_json(bootstrap_packet_path, _historical_packet("ZN"))
    update_packet_payload = _historical_packet("ZN")
    update_packet_payload["market_packet"]["timestamp"] = "2026-01-14T15:07:00Z"
    update_packet_payload["market_packet"]["current_price"] = 110.4296875
    _write_json(update_packet_path, update_packet_payload)
    _write_json(replay_updates_path, _zn_replay_updates())

    stdout = io.StringIO()
    stderr = io.StringIO()
    bootstrap_exit_code = run_operator_harness(
        ["bootstrap", "--packet", str(bootstrap_packet_path)],
        stdout=stdout,
        stderr=stderr,
    )
    assert bootstrap_exit_code == 0
    _write_json(watch_path, json.loads(stdout.getvalue())["watch"])

    stdout = io.StringIO()
    stderr = io.StringIO()
    update_exit_code = run_operator_harness(
        [
            "update",
            "--prior-watch",
            str(watch_path),
            "--packet",
            str(update_packet_path),
            "--evaluation-timestamp",
            "2026-01-14T15:07:00Z",
        ],
        stdout=stdout,
        stderr=stderr,
    )
    assert update_exit_code == 0

    stdout = io.StringIO()
    stderr = io.StringIO()
    replay_exit_code = run_operator_harness(
        [
            "replay",
            "--packet",
            str(bootstrap_packet_path),
            "--updates",
            str(replay_updates_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )
    assert replay_exit_code == 0
    assert calls == ["bootstrap", "update", "replay"]


def test_readiness_v2_operator_harness_sequence_preserves_watch_continuity(
    tmp_path: Path,
) -> None:
    bootstrap_packet_path = tmp_path / "bootstrap.packet.json"
    wait_packet_path = tmp_path / "wait.packet.json"
    requery_packet_path = tmp_path / "requery.packet.json"
    watch_path = tmp_path / "watch.json"
    _write_json(bootstrap_packet_path, _historical_packet("ZN"))
    _write_json(wait_packet_path, _historical_packet("ZN"))
    requery_packet_payload = _historical_packet("ZN")
    requery_packet_payload["market_packet"]["timestamp"] = "2026-01-14T15:12:00Z"
    requery_packet_payload["market_packet"]["current_price"] = 110.4296875
    _write_json(requery_packet_path, requery_packet_payload)

    stdout = io.StringIO()
    stderr = io.StringIO()
    bootstrap_exit_code = run_operator_harness(
        [
            "bootstrap",
            "--packet",
            str(bootstrap_packet_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )
    assert bootstrap_exit_code == 0
    bootstrap_payload = json.loads(stdout.getvalue())
    assert bootstrap_payload["watch"]["revision"] == 1
    _write_json(watch_path, bootstrap_payload["watch"])

    stdout = io.StringIO()
    stderr = io.StringIO()
    wait_exit_code = run_operator_harness(
        [
            "update",
            "--prior-watch",
            str(watch_path),
            "--packet",
            str(wait_packet_path),
            "--evaluation-timestamp",
            "2026-01-14T15:10:00Z",
        ],
        stdout=stdout,
        stderr=stderr,
    )
    assert wait_exit_code == 0
    wait_payload = json.loads(stdout.getvalue())
    assert wait_payload["watch"]["revision"] == 2
    assert wait_payload["watch"]["history"][-1]["transition_reason"] == "no_material_change"
    _write_json(watch_path, wait_payload["watch"])

    stdout = io.StringIO()
    stderr = io.StringIO()
    requery_exit_code = run_operator_harness(
        [
            "update",
            "--prior-watch",
            str(watch_path),
            "--packet",
            str(requery_packet_path),
            "--evaluation-timestamp",
            "2026-01-14T15:12:00Z",
        ],
        stdout=stdout,
        stderr=stderr,
    )
    assert requery_exit_code == 0
    requery_payload = json.loads(stdout.getvalue())
    assert requery_payload["watch"]["revision"] == 3
    assert requery_payload["watch"]["history"][-1]["transition_reason"] == "trigger_requery_ready"
    _write_json(watch_path, requery_payload["watch"])

    stdout = io.StringIO()
    stderr = io.StringIO()
    reject_exit_code = run_operator_harness(
        [
            "update",
            "--prior-watch",
            str(watch_path),
            "--packet",
            str(requery_packet_path),
            "--evaluation-timestamp",
            "2026-01-14T15:13:00Z",
        ],
        stdout=stdout,
        stderr=stderr,
    )
    assert reject_exit_code == 2
    assert stdout.getvalue() == ""
    assert "Completed or terminal readiness watches cannot be advanced" in stderr.getvalue()


def test_readiness_v2_operator_harness_rejects_invalid_mode_and_missing_args() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    invalid_mode_exit_code = run_operator_harness(
        ["inspect"],
        stdout=stdout,
        stderr=stderr,
    )

    assert invalid_mode_exit_code == 2
    assert stdout.getvalue() == ""
    assert "invalid choice" in stderr.getvalue()

    stdout = io.StringIO()
    stderr = io.StringIO()
    missing_args_exit_code = run_operator_harness(
        ["bootstrap"],
        stdout=stdout,
        stderr=stderr,
    )

    assert missing_args_exit_code == 2
    assert stdout.getvalue() == ""
    assert "the following arguments are required: --packet" in stderr.getvalue()


def test_readiness_v2_operator_harness_rejects_unsupported_contract_packet(tmp_path: Path) -> None:
    bundle_path = tmp_path / "packets.bundle.json"
    _write_json(bundle_path, _load_packet_bundle())
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_operator_harness(
        [
            "bootstrap",
            "--packet",
            str(bundle_path),
            "--contract",
            "GC",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "invalid choice" in stderr.getvalue()


def test_readiness_v2_operator_harness_rejects_malformed_prior_watch(tmp_path: Path) -> None:
    watch_path = tmp_path / "invalid.watch.json"
    packet_path = tmp_path / "zn.packet.json"
    watch_path.write_text('{"$schema":"readiness_watch_v1","watch_id":"bad"}')
    _write_json(packet_path, _historical_packet("ZN"))
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_operator_harness(
        [
            "update",
            "--prior-watch",
            str(watch_path),
            "--packet",
            str(packet_path),
            "--evaluation-timestamp",
            "2026-01-14T15:07:00Z",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "did not contain a valid readiness_watch_v1 artifact" in stderr.getvalue()


def test_readiness_v2_operator_harness_replay_rejects_unsupported_contract_or_malformed_input(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "zn.packet.json"
    updates_path = tmp_path / "replay.updates.json"
    _write_json(packet_path, _historical_packet("ZN"))
    updates_path.write_text('{"bad":"shape"}')

    stdout = io.StringIO()
    stderr = io.StringIO()
    malformed_exit_code = run_operator_harness(
        [
            "replay",
            "--packet",
            str(packet_path),
            "--updates",
            str(updates_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert malformed_exit_code == 2
    assert stdout.getvalue() == ""
    assert "Replay updates file must decode to a JSON array" in stderr.getvalue()

    unsupported_updates = _zn_replay_updates()
    unsupported_packet = _historical_packet("ZN")
    unsupported_packet["market_packet"]["contract"] = "GC"
    unsupported_packet["contract_metadata"]["contract"] = "GC"
    unsupported_packet["contract_specific_extension"]["contract"] = "GC"
    unsupported_updates[0]["packet"] = unsupported_packet
    _write_json(updates_path, unsupported_updates)
    stdout = io.StringIO()
    stderr = io.StringIO()
    unsupported_exit_code = run_operator_harness(
        [
            "replay",
            "--packet",
            str(packet_path),
            "--updates",
            str(updates_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert unsupported_exit_code == 2
    assert stdout.getvalue() == ""
    assert "contract_metadata" in stderr.getvalue()
