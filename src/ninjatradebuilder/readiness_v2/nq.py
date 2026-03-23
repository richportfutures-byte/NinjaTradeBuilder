from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ..schemas.contracts import NQContractSpecificExtension
from ..schemas.packet import HistoricalPacket
from ..schemas.inputs import EventCalendarEntry
from ..schemas.readiness_v2 import (
    BriefingTriggerSummary,
    DirectionalLean,
    ExpiryPolicy,
    NarrativeClaim,
    NarrativeProvenance,
    NQPremarketBriefingFeatureSnapshot,
    PremarketBriefingSessionSnapshot,
    PremarketBriefingV1,
    PriceLocationState,
    QueryTriggerDeterministicParameters,
    QueryTriggerV1,
    ReadinessEventRiskState,
    ReadinessInvalidationRule,
    ReadinessLockoutCondition,
    ReadinessV2ReplayArtifact,
    ReadinessV2ReplayBootstrapSummary,
    ReadinessV2ReplayInvariants,
    ReadinessV2ReplayStep,
    ReadinessWatchDetectedChange,
    NQReadinessWatchContextSnapshot,
    ReadinessWatchObservation,
    ReadinessWatchHistoryEntry,
    ReadinessWatchSourceRefs,
    ReadinessWatchV1,
)
from ..validation import validate_historical_packet
from .shared import (
    append_detected_change as shared_append_detected_change,
    build_replay_invariants as shared_build_replay_invariants,
    build_replay_step as shared_build_replay_step,
    coerce_replay_update as shared_coerce_replay_update,
)
from .state_machine import WatchStateEvaluation, transition_watch_state

ET_TZ = ZoneInfo("America/New_York")
READINESS_V2_PACKET_STALENESS_SECONDS = 300
READINESS_V2_RECHECK_MINUTES = 15
READINESS_V2_WATCH_TTL_MINUTES = 360
READINESS_V2_TOUCH_BUFFER_TICKS = 0
READINESS_V2_EVENT_ELEVATED_WINDOW_MINUTES = 30
READINESS_V2_AUCTION_ELEVATED_WINDOW_MINUTES = 60


def build_nq_premarket_briefing(
    packet: HistoricalPacket | Mapping[str, Any],
    *,
    created_at: datetime | None = None,
) -> PremarketBriefingV1:
    validated = _coerce_nq_packet(packet)
    evaluation_time = _as_utc(created_at or validated.market_packet.timestamp)
    packet_age_seconds = _packet_age_seconds(validated, evaluation_time)
    next_event = _next_upcoming_event(validated, evaluation_time)
    event_lockout_active = _event_lockout_active(validated, evaluation_time, next_event)
    governance_lock_reasons = _governance_lock_reasons(validated)
    feature_snapshot = _build_feature_snapshot(validated, evaluation_time)
    invalidation_rules = _build_invalidation_rules(validated, feature_snapshot, evaluation_time)
    lockout_conditions = _build_lockout_conditions(validated, evaluation_time, next_event)
    expires_at = _resolve_expiry(validated, evaluation_time, next_event)
    trigger_candidates = _build_trigger_summaries(
        validated,
        evaluation_time,
        expires_at,
        feature_snapshot,
    )
    thesis_claims = _build_thesis_claims(
        validated,
        next_event,
        feature_snapshot,
        evaluation_time,
    )
    thesis_claim_ids = _narrative_thesis_claim_ids(thesis_claims)
    session_snapshot = PremarketBriefingSessionSnapshot(
        session_type=validated.market_packet.session_type,
        evaluation_timestamp=evaluation_time,
        packet_timestamp=_as_utc(validated.market_packet.timestamp),
        session_access_state=_session_access_state(validated, evaluation_time),
        freshness_state=(
            "STALE"
            if packet_age_seconds > READINESS_V2_PACKET_STALENESS_SECONDS
            else "FRESH"
        ),
        packet_age_seconds=packet_age_seconds,
        next_event_name=next_event.name if next_event else None,
        next_event_time=_as_utc(next_event.time) if next_event else None,
        minutes_until_next_event=_minutes_until(next_event.time, evaluation_time) if next_event else None,
        event_lockout_active=event_lockout_active,
        governance_lockout_active=bool(governance_lock_reasons),
        data_quality_flags=list(validated.market_packet.data_quality_flags or []),
    )

    return PremarketBriefingV1(
        briefing_id=_artifact_id("briefing", evaluation_time),
        contract="NQ",
        created_at=evaluation_time,
        source_packet_ref=_source_packet_ref(validated),
        packet_timestamp=_as_utc(validated.market_packet.timestamp),
        session_snapshot=session_snapshot,
        feature_snapshot=feature_snapshot,
        narrative_feature_thesis=_join_claim_statements(thesis_claims, thesis_claim_ids),
        thesis_claims=thesis_claims,
        narrative_feature_thesis_claim_ids=thesis_claim_ids,
        monitor_posture=_monitor_posture(
            event_lockout_active=event_lockout_active,
            governance_lock_reasons=governance_lock_reasons,
            session_access_state=session_snapshot.session_access_state,
            freshness_state=session_snapshot.freshness_state,
            directional_lean=feature_snapshot.directional_lean,
        ),
        candidate_trigger_summaries=trigger_candidates,
        invalidation_conditions=invalidation_rules,
        lockout_conditions=lockout_conditions,
        expires_at=expires_at,
    )


def build_nq_initial_query_triggers(
    packet: HistoricalPacket | Mapping[str, Any],
    briefing: PremarketBriefingV1,
) -> list[QueryTriggerV1]:
    validated = _coerce_nq_packet(packet)
    if briefing.contract != "NQ":
        raise ValueError("NQ readiness v2 only accepts NQ briefings.")

    triggers: list[QueryTriggerV1] = []
    price_trigger = _build_price_touch_trigger(validated, briefing)
    if price_trigger is not None:
        triggers.append(price_trigger)
    triggers.append(_build_time_recheck_trigger(briefing))
    return triggers


def build_nq_initial_readiness_watch(
    packet: HistoricalPacket | Mapping[str, Any],
    briefing: PremarketBriefingV1,
    triggers: Sequence[QueryTriggerV1],
    *,
    evaluation_time: datetime | None = None,
) -> ReadinessWatchV1:
    validated = _coerce_nq_packet(packet)
    if briefing.contract != "NQ":
        raise ValueError("NQ readiness v2 only accepts NQ briefings.")
    _validate_watch_triggers(briefing, triggers)

    active_trigger = _select_active_trigger(triggers)
    as_of = _as_utc(evaluation_time or briefing.created_at)
    context_snapshot = _build_watch_context_snapshot(validated, as_of)
    trigger_truth_state = _derive_trigger_truth_state(validated, active_trigger, as_of)
    thesis_invalidated = _is_any_invalidation_met(
        briefing.invalidation_conditions,
        validated.market_packet.current_price,
        as_of,
    )
    structure_confirmed = _determine_structure_confirmation(
        active_trigger.post_trigger_policy,
        active_trigger,
        prior_value_location_state=context_snapshot.value_location_state,
        current_value_location_state=context_snapshot.value_location_state,
    )

    evaluation = WatchStateEvaluation(
        evaluated_at=as_of,
        trigger_observed=trigger_truth_state == "OBSERVED",
        requires_structure_confirmation=active_trigger.post_trigger_policy == "STRUCTURE_CONFIRMATION_REQUIRED",
        structure_confirmed=structure_confirmed,
        contamination_reasons=list(context_snapshot.contamination_reasons),
        thesis_invalidated=thesis_invalidated,
        lockout_reasons=list(context_snapshot.lockout_reasons),
        expired=as_of >= active_trigger.expiry_policy.expires_at,
    )
    decision = transition_watch_state("ARMED_WAITING", evaluation)
    observation = ReadinessWatchObservation(
        observed_at=as_of,
        trigger_truth_state=trigger_truth_state,
        context_change=decision.next_state,
        note=_watch_observation_note(active_trigger, decision.next_state),
    )
    operator_claims = _build_watch_operator_claims(
        validated,
        active_trigger,
        state=decision.next_state,
        routing_recommendation=decision.routing_recommendation,
        context_snapshot=context_snapshot,
        trigger_truth_state=trigger_truth_state,
        trigger_invalidated=thesis_invalidated,
        terminal_reason=decision.terminal_reason,
        prior_watch=None,
        evaluation_time=as_of,
    )
    operator_summary_claim_ids = [claim.claim_id for claim in operator_claims]
    history_entry = _build_history_entry(
        revision=1,
        prior_watch_id=None,
        prior_revision=None,
        evaluated_at=as_of,
        packet_timestamp=context_snapshot.packet_timestamp,
        state=decision.next_state,
        routing_recommendation=decision.routing_recommendation,
        trigger_truth_state=trigger_truth_state,
        detected_changes=[],
        terminal_reason=decision.terminal_reason,
    )

    return ReadinessWatchV1(
        watch_id=_artifact_id("watch", as_of),
        contract="NQ",
        revision=1,
        prior_watch_id=None,
        prior_revision=None,
        created_at=as_of,
        updated_at=as_of,
        source_kind="premarket_briefing",
        source_refs=ReadinessWatchSourceRefs(
            briefing_id=briefing.briefing_id,
            trigger_ids=[trigger.trigger_id for trigger in triggers],
            active_trigger_id=active_trigger.trigger_id,
        ),
        state=decision.next_state,
        active_trigger_family=active_trigger.family,
        trigger_payload=active_trigger.deterministic_parameters,
        post_trigger_policy=active_trigger.post_trigger_policy,
        context_snapshot=context_snapshot,
        routing_target=decision.routing_target,
        routing_recommendation=decision.routing_recommendation,
        invalidation_rules=list(active_trigger.invalidation_policy),
        expiry_policy=active_trigger.expiry_policy,
        last_evaluated_at=as_of,
        last_observation=observation,
        detected_changes=[],
        terminal_reason=decision.terminal_reason,
        allowed_next_actions=decision.allowed_next_actions,
        operator_summary=_join_claim_statements(operator_claims, operator_summary_claim_ids),
        operator_claims=operator_claims,
        operator_summary_claim_ids=operator_summary_claim_ids,
        history=[history_entry],
    )


def update_nq_readiness_watch(
    prior_watch: ReadinessWatchV1 | Mapping[str, Any],
    packet: HistoricalPacket | Mapping[str, Any],
    *,
    evaluation_timestamp: datetime,
) -> ReadinessWatchV1:
    prior = _coerce_nq_watch(prior_watch)
    validated = _coerce_nq_packet(packet)
    as_of = _as_utc(evaluation_timestamp)
    if as_of < prior.updated_at:
        raise ValueError("evaluation_timestamp must be at or after prior_watch.updated_at.")
    if prior.state in {"READY_FOR_REANALYSIS", "THESIS_INVALIDATED", "TERMINAL_EXPIRED"}:
        raise ValueError("Completed or terminal readiness watches cannot be advanced.")
    if _as_utc(validated.market_packet.timestamp) < prior.context_snapshot.packet_timestamp:
        raise ValueError(
            "new market packet timestamp must be at or after prior_watch.context_snapshot.packet_timestamp."
        )

    current_context = _build_watch_context_snapshot(validated, as_of)
    trigger_truth_state = _derive_trigger_truth_state_from_payload(
        validated,
        prior.trigger_payload,
        as_of,
    )
    thesis_invalidated = _is_any_invalidation_met(
        prior.invalidation_rules,
        validated.market_packet.current_price,
        as_of,
    )
    trigger_invalidated = thesis_invalidated or as_of >= prior.expiry_policy.expires_at
    structure_confirmed = _determine_structure_confirmation(
        prior.post_trigger_policy,
        prior.trigger_payload,
        prior_value_location_state=prior.context_snapshot.value_location_state,
        current_value_location_state=current_context.value_location_state,
    )

    evaluation = WatchStateEvaluation(
        evaluated_at=as_of,
        trigger_observed=trigger_truth_state == "OBSERVED",
        requires_structure_confirmation=prior.post_trigger_policy == "STRUCTURE_CONFIRMATION_REQUIRED",
        structure_confirmed=structure_confirmed,
        contamination_reasons=list(current_context.contamination_reasons),
        thesis_invalidated=thesis_invalidated,
        lockout_reasons=list(current_context.lockout_reasons),
        expired=as_of >= prior.expiry_policy.expires_at,
    )
    decision = transition_watch_state(prior.state, evaluation)
    detected_changes = _detect_watch_changes(
        prior,
        current_context,
        trigger_truth_state=trigger_truth_state,
        trigger_invalidated=trigger_invalidated,
        next_state=decision.next_state,
        next_routing_recommendation=decision.routing_recommendation,
    )
    observation = ReadinessWatchObservation(
        observed_at=as_of,
        trigger_truth_state=trigger_truth_state,
        context_change=decision.next_state,
        note=_update_observation_note(
            prior,
            decision.next_state,
            trigger_truth_state=trigger_truth_state,
            trigger_invalidated=trigger_invalidated,
            detected_changes=detected_changes,
        ),
    )
    operator_claims = _build_watch_operator_claims(
        validated,
        prior,
        state=decision.next_state,
        routing_recommendation=decision.routing_recommendation,
        context_snapshot=current_context,
        trigger_truth_state=trigger_truth_state,
        trigger_invalidated=trigger_invalidated,
        terminal_reason=decision.terminal_reason,
        prior_watch=prior,
        evaluation_time=as_of,
    )
    operator_summary_claim_ids = [claim.claim_id for claim in operator_claims]
    revision = prior.revision + 1
    history_entry = _build_history_entry(
        revision=revision,
        prior_watch_id=prior.watch_id,
        prior_revision=prior.revision,
        evaluated_at=as_of,
        packet_timestamp=current_context.packet_timestamp,
        state=decision.next_state,
        routing_recommendation=decision.routing_recommendation,
        trigger_truth_state=trigger_truth_state,
        detected_changes=detected_changes,
        terminal_reason=decision.terminal_reason,
    )

    return ReadinessWatchV1(
        watch_id=prior.watch_id,
        contract="NQ",
        revision=revision,
        prior_watch_id=prior.watch_id,
        prior_revision=prior.revision,
        created_at=prior.created_at,
        updated_at=as_of,
        source_kind=prior.source_kind,
        source_refs=prior.source_refs,
        state=decision.next_state,
        active_trigger_family=prior.active_trigger_family,
        trigger_payload=prior.trigger_payload,
        post_trigger_policy=prior.post_trigger_policy,
        context_snapshot=current_context,
        routing_target=decision.routing_target,
        routing_recommendation=decision.routing_recommendation,
        invalidation_rules=list(prior.invalidation_rules),
        expiry_policy=prior.expiry_policy,
        last_evaluated_at=as_of,
        last_observation=observation,
        detected_changes=detected_changes,
        terminal_reason=decision.terminal_reason,
        allowed_next_actions=decision.allowed_next_actions,
        operator_summary=_join_claim_statements(operator_claims, operator_summary_claim_ids),
        operator_claims=operator_claims,
        operator_summary_claim_ids=operator_summary_claim_ids,
        history=[*prior.history, history_entry],
    )


def replay_nq_readiness_sequence(
    packet: HistoricalPacket | Mapping[str, Any],
    updates: Sequence[Mapping[str, Any]],
    *,
    bootstrap_evaluation_time: datetime | None = None,
) -> ReadinessV2ReplayArtifact:
    validated = _coerce_nq_packet(packet)
    briefing = build_nq_premarket_briefing(validated, created_at=bootstrap_evaluation_time)
    query_triggers = build_nq_initial_query_triggers(validated, briefing)
    watch = build_nq_initial_readiness_watch(
        validated,
        briefing,
        query_triggers,
        evaluation_time=briefing.created_at,
    )
    steps = [_build_replay_step(watch, step_index=0, phase="bootstrap")]

    for step_index, update in enumerate(updates, start=1):
        update_packet, evaluation_timestamp = _coerce_replay_update(update)
        watch = update_nq_readiness_watch(
            watch,
            update_packet,
            evaluation_timestamp=evaluation_timestamp,
        )
        steps.append(_build_replay_step(watch, step_index=step_index, phase="update"))

    terminal_states = {"THESIS_INVALIDATED", "TERMINAL_EXPIRED"}
    return ReadinessV2ReplayArtifact(
        contract="NQ",
        bootstrap=ReadinessV2ReplayBootstrapSummary(
            briefing_id=briefing.briefing_id,
            watch_id=watch.watch_id,
            evaluation_timestamp=briefing.created_at,
            initial_revision=1,
            initial_state=steps[0].state,
            initial_routing_recommendation=steps[0].routing_recommendation,
            active_trigger_family=watch.active_trigger_family,
        ),
        steps=steps,
        final_watch=watch,
        invariants=_build_replay_invariants(steps, watch.watch_id),
        terminal_outcome_state=watch.state if watch.state in terminal_states else None,
        terminal_outcome_reason=watch.terminal_reason if watch.state in terminal_states else None,
    )


def _coerce_replay_update(
    update: Mapping[str, Any],
) -> tuple[HistoricalPacket, datetime]:
    return shared_coerce_replay_update(update, packet_coercer=_coerce_nq_packet)


def _build_replay_step(
    watch: ReadinessWatchV1,
    *,
    step_index: int,
    phase: str,
) -> ReadinessV2ReplayStep:
    return shared_build_replay_step(watch, step_index=step_index, phase=phase)


def _build_replay_invariants(
    steps: Sequence[ReadinessV2ReplayStep],
    watch_id: str,
) -> ReadinessV2ReplayInvariants:
    return shared_build_replay_invariants(steps, watch_id)


def _build_history_entry(
    *,
    revision: int,
    prior_watch_id: str | None,
    prior_revision: int | None,
    evaluated_at: datetime,
    packet_timestamp: datetime,
    state: str,
    routing_recommendation: str,
    trigger_truth_state: str,
    detected_changes: Sequence[ReadinessWatchDetectedChange],
    terminal_reason: str | None,
) -> ReadinessWatchHistoryEntry:
    transition_reason = _history_transition_reason(
        revision=revision,
        state=state,
        detected_changes=detected_changes,
    )
    return ReadinessWatchHistoryEntry(
        revision=revision,
        prior_watch_id=prior_watch_id,
        prior_revision=prior_revision,
        evaluated_at=evaluated_at,
        packet_timestamp=packet_timestamp,
        state=state,
        routing_recommendation=routing_recommendation,
        trigger_truth_state=trigger_truth_state,
        transition_reason=transition_reason,
        detected_change_kinds=[change.kind for change in detected_changes],
        change_summary=_history_change_summary(
            transition_reason=transition_reason,
            state=state,
            routing_recommendation=routing_recommendation,
        ),
        terminal_reason=terminal_reason,
    )


def _history_transition_reason(
    *,
    revision: int,
    state: str,
    detected_changes: Sequence[ReadinessWatchDetectedChange],
) -> str:
    if revision == 1:
        return "initialized"
    if state == "READY_FOR_REANALYSIS":
        return "trigger_requery_ready"
    if state == "CONTEXT_CONTAMINATED":
        return "context_contaminated"
    if state == "LOCKED_OUT":
        return "lockout_applied"
    if state == "THESIS_INVALIDATED":
        return "thesis_invalidated"
    if state == "TERMINAL_EXPIRED":
        return "watch_expired"
    if detected_changes:
        return "waiting_context_shift"
    return "no_material_change"


def _history_change_summary(
    *,
    transition_reason: str,
    state: str,
    routing_recommendation: str,
) -> str:
    if transition_reason == "initialized":
        return (
            f"Initialized watch at revision 1 in {state} with {routing_recommendation}."
        )
    if transition_reason == "no_material_change":
        return (
            f"No material change; watch remains {state} with {routing_recommendation}."
        )
    if transition_reason == "waiting_context_shift":
        return (
            f"Deterministic context changed while watch remains {state} with {routing_recommendation}."
        )
    if transition_reason == "trigger_requery_ready":
        return (
            f"Trigger conditions advanced the watch to {state} with {routing_recommendation}."
        )
    if transition_reason == "context_contaminated":
        return (
            f"Context contamination advanced the watch to {state} with {routing_recommendation}."
        )
    if transition_reason == "lockout_applied":
        return f"Deterministic lockout advanced the watch to {state} with {routing_recommendation}."
    if transition_reason == "thesis_invalidated":
        return (
            f"Deterministic invalidation advanced the watch to {state} with {routing_recommendation}."
        )
    return f"Expiry advanced the watch to {state} with {routing_recommendation}."


def _build_watch_context_snapshot(
    packet: HistoricalPacket,
    evaluation_time: datetime,
) -> NQReadinessWatchContextSnapshot:
    extension = packet.contract_specific_extension
    if not isinstance(extension, NQContractSpecificExtension):
        raise ValueError("NQ readiness v2 requires an NQ contract extension.")

    feature_snapshot = _build_feature_snapshot(packet, evaluation_time)
    packet_age_seconds = _packet_age_seconds(packet, evaluation_time)
    next_event = _next_upcoming_event(packet, evaluation_time)
    event_risk_state = _event_risk_state(packet, evaluation_time, next_event)
    governance_lock_reasons = _governance_lock_reasons(packet)
    session_access_state = _session_access_state(packet, evaluation_time)
    contamination_reasons = []
    if packet_age_seconds > READINESS_V2_PACKET_STALENESS_SECONDS:
        contamination_reasons.append("packet_stale")

    lockout_reasons = []
    if session_access_state == "OUTSIDE_ALLOWED_HOURS":
        lockout_reasons.append("outside_allowed_hours")
    if event_risk_state == "LOCKOUT_ACTIVE":
        lockout_reasons.append("event_lockout_active")
    lockout_reasons.extend(governance_lock_reasons)

    return NQReadinessWatchContextSnapshot(
        evaluation_timestamp=evaluation_time,
        packet_timestamp=_as_utc(packet.market_packet.timestamp),
        packet_age_seconds=packet_age_seconds,
        freshness_state="STALE" if contamination_reasons else "FRESH",
        session_access_state=session_access_state,
        event_lockout_active=event_risk_state == "LOCKOUT_ACTIVE",
        governance_lockout_active=bool(governance_lock_reasons),
        event_risk_state=event_risk_state,
        next_event_name=next_event.name if next_event else None,
        next_event_time=_as_utc(next_event.time) if next_event else None,
        minutes_until_next_event=_minutes_until(next_event.time, evaluation_time) if next_event else None,
        current_price=packet.market_packet.current_price,
        directional_lean=feature_snapshot.directional_lean,
        value_location_state=feature_snapshot.price_location_vs_value,
        macro_release_context=_macro_release_context(packet, evaluation_time),
        relative_strength_vs_es=extension.relative_strength_vs_es,
        megacap_leadership_posture=_megacap_leadership_posture(extension),
        bond_yield_context=_bond_yield_context(packet),
        active_data_quality_flags=list(packet.market_packet.data_quality_flags or []),
        lockout_reasons=lockout_reasons,
        contamination_reasons=contamination_reasons,
    )


def _build_feature_snapshot(
    packet: HistoricalPacket,
    evaluation_time: datetime,
) -> NQPremarketBriefingFeatureSnapshot:
    extension = packet.contract_specific_extension
    if not isinstance(extension, NQContractSpecificExtension):
        raise ValueError("NQ readiness v2 requires an NQ contract extension.")

    return NQPremarketBriefingFeatureSnapshot(
        current_price=packet.market_packet.current_price,
        session_open=packet.market_packet.session_open,
        vwap=packet.market_packet.vwap,
        current_session_vah=packet.market_packet.current_session_vah,
        current_session_val=packet.market_packet.current_session_val,
        current_session_poc=packet.market_packet.current_session_poc,
        prior_day_high=packet.market_packet.prior_day_high,
        prior_day_low=packet.market_packet.prior_day_low,
        session_range_ratio=packet.market_packet.session_range / packet.market_packet.avg_20d_session_range,
        cumulative_delta=packet.market_packet.cumulative_delta,
        current_volume_vs_average=packet.market_packet.current_volume_vs_average,
        opening_type=packet.market_packet.opening_type,
        relative_strength_vs_es=extension.relative_strength_vs_es,
        megacap_leadership_posture=_megacap_leadership_posture(extension),
        bond_yield_context=_bond_yield_context(packet),
        macro_release_context=_macro_release_context(packet, evaluation_time),
        directional_lean=_directional_lean(packet),
        price_location_vs_vwap=_price_location_vs_vwap(packet),
        price_location_vs_value=_price_location_vs_value(packet),
    )


def _build_thesis_claims(
    packet: HistoricalPacket,
    next_event: EventCalendarEntry | None,
    feature_snapshot: NQPremarketBriefingFeatureSnapshot,
    evaluation_time: datetime,
) -> list[NarrativeClaim]:
    extension = packet.contract_specific_extension
    if not isinstance(extension, NQContractSpecificExtension):
        raise ValueError("NQ readiness v2 requires an NQ contract extension.")

    event_statement = (
        f"The next scheduled event is {next_event.name} at {next_event.time.isoformat()}, which can hard-stop the NQ watch as the lockout window approaches."
        if next_event is not None
        else "No scheduled event is currently inside the deterministic lockout window."
    )

    claims = [
        NarrativeClaim(
            claim_id="value_support_or_resistance",
            category="structure",
            statement=_structure_claim_text(packet, feature_snapshot),
            evidence_fields=[
                "market_packet.current_price",
                "market_packet.vwap",
                "market_packet.current_session_vah",
                "market_packet.current_session_val",
                "market_packet.prior_day_high",
            ],
            provenance=[
                _field_provenance(
                    "current_price",
                    "market_packet.current_price",
                    _format_price(packet.market_packet.current_price),
                    "Current NQ price anchors the value-context portion of the thesis.",
                    observed_at=_as_utc(packet.market_packet.timestamp),
                ),
                _field_provenance(
                    "vwap",
                    "market_packet.vwap",
                    _format_price(packet.market_packet.vwap),
                    "VWAP anchors the directional structure reference.",
                    observed_at=_as_utc(packet.market_packet.timestamp),
                ),
                _field_provenance(
                    "current_session_vah",
                    "market_packet.current_session_vah",
                    _format_price(packet.market_packet.current_session_vah),
                    "Current session VAH anchors the NQ upside value boundary.",
                    observed_at=_as_utc(packet.market_packet.timestamp),
                ),
                _field_provenance(
                    "current_session_val",
                    "market_packet.current_session_val",
                    _format_price(packet.market_packet.current_session_val),
                    "Current session VAL anchors the NQ downside value boundary.",
                    observed_at=_as_utc(packet.market_packet.timestamp),
                ),
                _derived_provenance(
                    "directional_lean",
                    "derived.directional_lean",
                    feature_snapshot.directional_lean,
                    "Directional lean is derived from price vs session open, VWAP, and cumulative delta.",
                    observed_at=evaluation_time,
                ),
            ],
        ),
        NarrativeClaim(
            claim_id="flow_alignment",
            category="flow",
            statement=(
                f"Relative strength vs ES is {extension.relative_strength_vs_es:.2f}, "
                f"{_megacap_leadership_posture(extension)}, cumulative delta is "
                f"{packet.market_packet.cumulative_delta:.0f}, and volume is "
                f"{packet.market_packet.current_volume_vs_average:.2f}x average."
            ),
            evidence_fields=[
                "contract_specific_extension.relative_strength_vs_es",
                "contract_specific_extension.megacap_leadership_table",
                "market_packet.cumulative_delta",
                "market_packet.current_volume_vs_average",
            ],
            provenance=[
                _field_provenance(
                    "relative_strength_vs_es",
                    "contract_specific_extension.relative_strength_vs_es",
                    f"{extension.relative_strength_vs_es:.2f}",
                    "Relative strength vs ES is carried directly into the NQ flow alignment claim.",
                    observed_at=evaluation_time,
                ),
                _derived_provenance(
                    "megacap_leadership_posture",
                    "derived.megacap_leadership_posture",
                    _megacap_leadership_posture(extension),
                    "Megacap leadership posture is deterministically derived from the megacap leadership table.",
                    observed_at=evaluation_time,
                ),
                _field_provenance(
                    "cumulative_delta",
                    "market_packet.cumulative_delta",
                    f"{packet.market_packet.cumulative_delta:.0f}",
                    "Cumulative delta anchors the flow direction reference.",
                    observed_at=_as_utc(packet.market_packet.timestamp),
                ),
                _field_provenance(
                    "current_volume_vs_average",
                    "market_packet.current_volume_vs_average",
                    f"{packet.market_packet.current_volume_vs_average:.2f}",
                    "Relative volume anchors the participation reference.",
                    observed_at=_as_utc(packet.market_packet.timestamp),
                ),
            ],
        ),
        NarrativeClaim(
            claim_id="macro_context",
            category="risk",
            statement=(
                f"Event context is '{feature_snapshot.macro_release_context}' while bond yields are "
                f"'{feature_snapshot.bond_yield_context}' and {_megacap_leadership_posture(extension)}."
            ),
            evidence_fields=[
                "market_packet.event_calendar_remainder",
                "market_packet.cross_market_context.bond_yield_direction",
                "contract_specific_extension.megacap_leadership_table",
            ],
            provenance=[
                _derived_provenance(
                    "macro_release_context",
                    "derived.macro_release_context",
                    feature_snapshot.macro_release_context,
                    "Macro release context is deterministically derived from released and upcoming NQ event calendar entries.",
                    observed_at=evaluation_time,
                ),
                _field_provenance(
                    "bond_yield_direction",
                    "market_packet.cross_market_context.bond_yield_direction",
                    _bond_yield_context(packet),
                    "Bond yield direction is taken directly from the validated NQ cross-market context.",
                    observed_at=evaluation_time,
                ),
                _derived_provenance(
                    "megacap_leadership_posture",
                    "derived.megacap_leadership_posture",
                    _megacap_leadership_posture(extension),
                    "Megacap leadership posture is deterministically derived from the megacap leadership table.",
                    observed_at=evaluation_time,
                ),
            ],
        ),
        NarrativeClaim(
            claim_id="event_risk_window",
            category="risk",
            statement=event_statement,
            evidence_fields=[
                "market_packet.event_calendar_remainder",
                "challenge_state.event_lockout_minutes_before",
                "challenge_state.event_lockout_minutes_after",
            ],
            provenance=(
                [
                    _field_provenance(
                        "next_event_name",
                        "market_packet.event_calendar_remainder[0].name",
                        next_event.name,
                        "The next upcoming event name anchors the event-risk sentence.",
                        observed_at=evaluation_time,
                    ),
                    _field_provenance(
                        "next_event_time",
                        "market_packet.event_calendar_remainder[0].time",
                        _render_datetime(_as_utc(next_event.time)),
                        "The next upcoming event timestamp anchors the event-risk sentence.",
                        observed_at=evaluation_time,
                    ),
                    _field_provenance(
                        "event_lockout_minutes_before",
                        "challenge_state.event_lockout_minutes_before",
                        str(packet.challenge_state.event_lockout_minutes_before),
                        "The pre-event lockout window anchors the hard-stop reference.",
                        observed_at=evaluation_time,
                    ),
                    _field_provenance(
                        "event_lockout_minutes_after",
                        "challenge_state.event_lockout_minutes_after",
                        str(packet.challenge_state.event_lockout_minutes_after),
                        "The post-event lockout window anchors the hard-stop reference.",
                        observed_at=evaluation_time,
                    ),
                ]
                if next_event is not None
                else [
                    _derived_provenance(
                        "no_upcoming_event",
                        "derived.next_event_absent",
                        "true",
                        "No upcoming event remains after filtering the validated event calendar for future entries.",
                        observed_at=evaluation_time,
                    )
                ]
            ),
        ),
    ]
    return claims


def _build_trigger_summaries(
    packet: HistoricalPacket,
    evaluation_time: datetime,
    expires_at: datetime,
    feature_snapshot: PremarketBriefingFeatureSnapshot,
) -> list[BriefingTriggerSummary]:
    summaries: list[BriefingTriggerSummary] = []
    price_trigger = _candidate_price_trigger(packet, feature_snapshot.directional_lean)
    if price_trigger is not None:
        summaries.append(
            BriefingTriggerSummary(
                family="price_level_touch",
                label=f"Touch {_humanize_level_label(price_trigger[0])}",
                summary=(
                    f"Escalate only if NQ tags {_format_price(price_trigger[1])}, "
                    f"the next structural level in the current {feature_snapshot.directional_lean.lower()} framing."
                ),
                supporting_claim_ids=["value_support_or_resistance", "flow_alignment"],
                provenance=[
                    _field_provenance(
                        "trigger_level",
                        f"market_packet.{price_trigger[0]}",
                        _format_price(price_trigger[1]),
                        "The trigger level comes directly from the selected structural level on the packet.",
                        observed_at=_as_utc(packet.market_packet.timestamp),
                    ),
                    _derived_provenance(
                        "directional_lean",
                        "derived.directional_lean",
                        feature_snapshot.directional_lean,
                        "Directional lean determines which side of value can unlock reanalysis.",
                        observed_at=evaluation_time,
                    ),
                ],
                unlock_action="ROUTE_STAGE_AB_REANALYSIS",
                price_level=price_trigger[1],
            )
        )

    recheck_at = _resolve_recheck_time(evaluation_time, expires_at)
    summaries.append(
        BriefingTriggerSummary(
            family="recheck_at_time",
            label="Timed recheck",
            summary=(
                f"Re-evaluate the watch at {recheck_at.isoformat()} if the price trigger remains unobserved."
            ),
            supporting_claim_ids=["value_support_or_resistance"],
            provenance=[
                _field_provenance(
                    "recheck_at_time",
                    "derived.recheck_at_time",
                    _render_datetime(recheck_at),
                    "The timed recheck is deterministically resolved from the creation time and briefing expiry.",
                    observed_at=evaluation_time,
                ),
                _field_provenance(
                    "expires_at",
                    "derived.briefing_expires_at",
                    _render_datetime(expires_at),
                    "The timed recheck remains bounded by the briefing expiry.",
                    observed_at=evaluation_time,
                ),
            ],
            unlock_action="ROUTE_STAGE_AB_REANALYSIS",
            recheck_at_time=recheck_at,
        )
    )
    return summaries


def _build_invalidation_rules(
    packet: HistoricalPacket,
    feature_snapshot: PremarketBriefingFeatureSnapshot,
    evaluation_time: datetime,
) -> list[ReadinessInvalidationRule]:
    if feature_snapshot.directional_lean == "BEARISH":
        price_level = packet.market_packet.current_session_vah
        comparison = "GREATER_THAN_OR_EQUAL"
        description = (
            f"A reclaim above developing VAH {_format_price(price_level)} invalidates the bearish watch framing."
        )
    else:
        price_level = packet.market_packet.current_session_val
        comparison = "LESS_THAN_OR_EQUAL"
        description = (
            f"A break below developing VAL {_format_price(price_level)} invalidates the bullish or balanced watch framing."
        )

    return [
        ReadinessInvalidationRule(
            rule_id="price_structure_break",
            kind="PRICE_BREACH",
            description=description,
            provenance=[
                _field_provenance(
                    "price_level",
                    (
                        "market_packet.current_session_vah"
                        if comparison == "GREATER_THAN_OR_EQUAL"
                        else "market_packet.current_session_val"
                    ),
                    _format_price(price_level),
                    "The invalidation level is taken directly from the developing value boundary.",
                    observed_at=_as_utc(packet.market_packet.timestamp),
                ),
                _derived_provenance(
                    "comparison",
                    "derived.invalidation_comparison",
                    comparison,
                    "The comparison direction is selected from the deterministic directional lean.",
                    observed_at=evaluation_time,
                ),
            ],
            price_level=price_level,
            comparison=comparison,
        ),
    ]


def _build_lockout_conditions(
    packet: HistoricalPacket,
    evaluation_time: datetime,
    next_event: EventCalendarEntry | None,
) -> list[ReadinessLockoutCondition]:
    conditions = []
    if _session_access_state(packet, evaluation_time) == "OUTSIDE_ALLOWED_HOURS":
        conditions.append(
            ReadinessLockoutCondition(
                condition_id="outside_allowed_hours",
                kind="SESSION_LOCKOUT",
                description="The watch is outside the NQ allowed-hours session window.",
                provenance=[
                    _field_provenance(
                        "session_access_state",
                        "derived.session_access_state",
                        "OUTSIDE_ALLOWED_HOURS",
                        "Session access is derived from the ET evaluation time and the contract allowed-hours window.",
                        observed_at=evaluation_time,
                    )
                ],
                begins_at=evaluation_time,
                reason_code="outside_allowed_hours",
            )
        )

    conditions.append(
        ReadinessLockoutCondition(
            condition_id="session_end_lockout",
            kind="SESSION_LOCKOUT",
            description="The watch hard-stops at the NQ allowed-hours close.",
            provenance=[
                _field_provenance(
                    "allowed_hours_end_et",
                    "contract_metadata.allowed_hours_end_et",
                    packet.contract_metadata.allowed_hours_end_et,
                    "The session close lockout is anchored to the contract allowed-hours end.",
                    observed_at=evaluation_time,
                ),
                _field_provenance(
                    "session_end_time",
                    "derived.session_end_time",
                    _render_datetime(_session_end_time(packet, evaluation_time)),
                    "The ET session close is converted into the deterministic UTC lockout timestamp.",
                    observed_at=evaluation_time,
                ),
            ],
            begins_at=_session_end_time(packet, evaluation_time),
            reason_code="session_close",
        )
    )
    if next_event is not None:
        begins_at, ends_at = _event_lockout_window(packet, next_event)
        conditions.append(
            ReadinessLockoutCondition(
                condition_id="next_event_lockout",
                kind="EVENT_LOCKOUT",
                description=(
                    f"{next_event.name} activates a deterministic event lockout window around the scheduled release."
                ),
                provenance=[
                    _field_provenance(
                        "next_event_name",
                        "market_packet.event_calendar_remainder[0].name",
                        next_event.name,
                        "The next event name anchors the event lockout description.",
                        observed_at=evaluation_time,
                    ),
                    _field_provenance(
                        "begins_at",
                        "derived.event_lockout_window.begin",
                        _render_datetime(begins_at),
                        "The lockout start is derived from the event time and the pre-event lockout minutes.",
                        observed_at=evaluation_time,
                    ),
                    _field_provenance(
                        "ends_at",
                        "derived.event_lockout_window.end",
                        _render_datetime(ends_at),
                        "The lockout end is derived from the event time and the post-event lockout minutes.",
                        observed_at=evaluation_time,
                    ),
                ],
                begins_at=begins_at,
                ends_at=ends_at,
                reason_code=next_event.name.lower().replace(" ", "_"),
            )
        )

    for index, reason in enumerate(_governance_lock_reasons(packet), start=1):
        conditions.append(
            ReadinessLockoutCondition(
                condition_id=f"governance_lockout_{index}",
                kind="GOVERNANCE_LOCKOUT",
                description=f"Governance rule '{reason}' blocks readiness routing.",
                provenance=[
                    _field_provenance(
                        f"governance_reason_{index}",
                        "derived.governance_lock_reason",
                        reason,
                        "Governance lockouts are derived from deterministic challenge-state constraints.",
                        observed_at=evaluation_time,
                    )
                ],
                reason_code=reason,
            )
        )

    return conditions


def _build_price_touch_trigger(
    packet: HistoricalPacket,
    briefing: PremarketBriefingV1,
) -> QueryTriggerV1 | None:
    candidate = _candidate_price_trigger(packet, briefing.feature_snapshot.directional_lean)
    if candidate is None:
        return None

    level_label, level_price = candidate
    invalidation_rule = briefing.invalidation_conditions[0]
    guard_statement = (
        f"Keep the trigger active only while price holds above developing VAL "
        f"{_format_price(invalidation_rule.price_level or 0.0)}."
        if invalidation_rule.comparison == "LESS_THAN_OR_EQUAL"
        else f"Keep the trigger active only while price stays below developing VAH "
        f"{_format_price(invalidation_rule.price_level or 0.0)}."
    )
    operator_claims = [
        NarrativeClaim(
            claim_id="trigger_touch_level",
            category="trigger",
            statement=(
                f"Escalate for fresh Stage A+B reanalysis if NQ tags {_format_price(level_price)} "
                f"at {_humanize_level_label(level_label)}."
            ),
            evidence_fields=[
                f"feature_snapshot.{level_label}",
                "feature_snapshot.directional_lean",
            ],
            provenance=[
                _field_provenance(
                    "trigger_level",
                    f"market_packet.{level_label}",
                    _format_price(level_price),
                    "The trigger level comes directly from the selected structural level.",
                    observed_at=_as_utc(packet.market_packet.timestamp),
                ),
                _derived_provenance(
                    "directional_lean",
                    "derived.directional_lean",
                    briefing.feature_snapshot.directional_lean,
                    "Directional lean determines that a price-touch trigger can unlock reanalysis.",
                    observed_at=briefing.created_at,
                ),
            ],
        ),
        NarrativeClaim(
            claim_id="trigger_invalidation_guard",
            category="invalidation",
            statement=guard_statement,
            evidence_fields=[
                "invalidation_policy.price_level",
                "invalidation_policy.comparison",
            ],
            provenance=list(invalidation_rule.provenance),
        ),
    ]
    operator_explanation_claim_ids = [claim.claim_id for claim in operator_claims]
    return QueryTriggerV1(
        trigger_id=_artifact_id(f"trigger-{level_label}", briefing.created_at),
        source_briefing_id=briefing.briefing_id,
        contract="NQ",
        created_at=briefing.created_at,
        family="price_level_touch",
        mode="deterministic",
        label=f"Touch {_humanize_level_label(level_label)}",
        deterministic_parameters=QueryTriggerDeterministicParameters(
            family="price_level_touch",
            price_level=level_price,
            buffer_ticks=READINESS_V2_TOUCH_BUFFER_TICKS,
        ),
        supporting_claim_ids=["value_support_or_resistance", "flow_alignment"],
        unlock_action="ROUTE_STAGE_AB_REANALYSIS",
        post_trigger_policy="STRUCTURE_CONFIRMATION_REQUIRED",
        expiry_policy=ExpiryPolicy(
            expires_at=briefing.expires_at,
            reason="expires_with_briefing_window",
        ),
        invalidation_policy=list(briefing.invalidation_conditions),
        operator_explanation=_join_claim_statements(operator_claims, operator_explanation_claim_ids),
        operator_claims=operator_claims,
        operator_explanation_claim_ids=operator_explanation_claim_ids,
        validation_status="EXECUTABLE",
    )


def _build_time_recheck_trigger(briefing: PremarketBriefingV1) -> QueryTriggerV1:
    recheck_at = _resolve_recheck_time(briefing.created_at, briefing.expires_at)
    operator_claims = [
        NarrativeClaim(
            claim_id="timed_recheck_window",
            category="trigger",
            statement=(
                f"Force a bounded recheck at {recheck_at.isoformat()} if the price trigger does not fire first."
            ),
            evidence_fields=[
                "deterministic_parameters.recheck_at_time",
                "expiry_policy.expires_at",
            ],
            provenance=[
                _field_provenance(
                    "recheck_at_time",
                    "derived.recheck_at_time",
                    _render_datetime(recheck_at),
                    "The recheck time is deterministically resolved from the briefing creation time and expiry.",
                    observed_at=briefing.created_at,
                ),
                _field_provenance(
                    "expires_at",
                    "briefing.expires_at",
                    _render_datetime(briefing.expires_at),
                    "The bounded recheck remains inside the briefing expiry window.",
                    observed_at=briefing.created_at,
                ),
            ],
        )
    ]
    operator_explanation_claim_ids = [claim.claim_id for claim in operator_claims]
    return QueryTriggerV1(
        trigger_id=_artifact_id("trigger-recheck", briefing.created_at),
        source_briefing_id=briefing.briefing_id,
        contract="NQ",
        created_at=briefing.created_at,
        family="recheck_at_time",
        mode="deterministic",
        label="Timed recheck",
        deterministic_parameters=QueryTriggerDeterministicParameters(
            family="recheck_at_time",
            recheck_at_time=recheck_at,
        ),
        supporting_claim_ids=["value_support_or_resistance"],
        unlock_action="ROUTE_STAGE_AB_REANALYSIS",
        post_trigger_policy="DIRECT_REANALYSIS",
        expiry_policy=ExpiryPolicy(
            expires_at=briefing.expires_at,
            reason="expires_with_briefing_window",
        ),
        invalidation_policy=list(briefing.invalidation_conditions),
        operator_explanation=_join_claim_statements(operator_claims, operator_explanation_claim_ids),
        operator_claims=operator_claims,
        operator_explanation_claim_ids=operator_explanation_claim_ids,
        validation_status="EXECUTABLE",
    )


def _select_active_trigger(triggers: Sequence[QueryTriggerV1]) -> QueryTriggerV1:
    for family in ("price_level_touch", "recheck_at_time"):
        for trigger in triggers:
            if trigger.family == family and trigger.validation_status == "EXECUTABLE":
                return trigger
    raise ValueError("No executable readiness v2 trigger is available.")


def _coerce_nq_watch(watch: ReadinessWatchV1 | Mapping[str, Any]) -> ReadinessWatchV1:
    validated = watch if isinstance(watch, ReadinessWatchV1) else ReadinessWatchV1.model_validate(watch)
    if validated.contract != "NQ":
        raise ValueError("Readiness v2 NQ slice only supports NQ watches.")
    return validated


def _derive_trigger_truth_state(
    packet: HistoricalPacket,
    trigger: QueryTriggerV1,
    evaluation_time: datetime,
) -> str:
    return _derive_trigger_truth_state_from_payload(
        packet,
        trigger.deterministic_parameters,
        evaluation_time,
    )


def _derive_trigger_truth_state_from_payload(
    packet: HistoricalPacket,
    trigger_payload: QueryTriggerDeterministicParameters,
    evaluation_time: datetime,
) -> str:
    if trigger_payload.family == "recheck_at_time":
        if evaluation_time >= (trigger_payload.recheck_at_time or evaluation_time):
            return "OBSERVED"
        return "PENDING"

    level = trigger_payload.price_level or packet.market_packet.current_price
    threshold = packet.contract_metadata.tick_size / 2
    if abs(packet.market_packet.current_price - level) <= threshold:
        return "OBSERVED"
    return "NOT_OBSERVED"


def _determine_structure_confirmation(
    post_trigger_policy: str,
    trigger: QueryTriggerV1 | QueryTriggerDeterministicParameters,
    *,
    prior_value_location_state: PriceLocationState,
    current_value_location_state: PriceLocationState,
) -> bool:
    if post_trigger_policy != "STRUCTURE_CONFIRMATION_REQUIRED":
        return True

    if trigger.family != "price_level_touch":
        return False

    trigger_level = trigger.price_level if isinstance(trigger, QueryTriggerDeterministicParameters) else trigger.deterministic_parameters.price_level
    if trigger_level is None:
        return False

    if current_value_location_state == prior_value_location_state:
        return False
    return current_value_location_state in {"ABOVE_VAH", "BELOW_VAL"}


def _watch_observation_note(trigger: QueryTriggerV1, next_state: str) -> str:
    if next_state == "ARMED_WAITING":
        return f"Watch armed on {trigger.family}."
    if next_state == "TRIGGER_OBSERVED":
        return f"{trigger.family} observed; hold for deterministic transition."
    if next_state == "LOCKED_OUT":
        return "Watch is blocked by a deterministic lockout."
    if next_state == "CONTEXT_CONTAMINATED":
        return "Watch context is no longer fresh enough to trust."
    if next_state == "THESIS_INVALIDATED":
        return "A deterministic invalidation rule has been met."
    if next_state == "TERMINAL_EXPIRED":
        return "The watch expired before any further routing action."
    return f"Watch transitioned to {next_state}."


def _update_observation_note(
    prior_watch: ReadinessWatchV1,
    next_state: str,
    *,
    trigger_truth_state: str,
    trigger_invalidated: bool,
    detected_changes: Sequence[ReadinessWatchDetectedChange],
) -> str:
    if trigger_invalidated and next_state == "THESIS_INVALIDATED":
        return "The active trigger became unusable because the watch thesis was invalidated."
    if next_state == "TERMINAL_EXPIRED":
        return "The active watch expired before requery conditions completed."
    if next_state == "READY_FOR_REANALYSIS":
        return "Deterministic trigger and structure conditions now support a fresh Stage B requery."
    if next_state == "LOCKED_OUT":
        return "The watch is held by deterministic session, event, or governance lockout."
    if next_state == "CONTEXT_CONTAMINATED":
        return "The watch remains active but current packet freshness is no longer reliable."
    if detected_changes:
        return detected_changes[0].detail
    return (
        f"The watch remains in {prior_watch.state} with trigger truth {trigger_truth_state.lower()}."
    )


def _build_watch_operator_claims(
    packet: HistoricalPacket,
    watch_source: QueryTriggerV1 | ReadinessWatchV1,
    *,
    state: str,
    routing_recommendation: str,
    context_snapshot: ReadinessWatchContextSnapshot,
    trigger_truth_state: str,
    trigger_invalidated: bool,
    terminal_reason: str | None,
    prior_watch: ReadinessWatchV1 | None,
    evaluation_time: datetime,
) -> list[NarrativeClaim]:
    if isinstance(watch_source, QueryTriggerV1):
        active_trigger_family = watch_source.family
        price_level = watch_source.deterministic_parameters.price_level
        recheck_at_time = watch_source.deterministic_parameters.recheck_at_time
        invalidation_rules = watch_source.invalidation_policy
    else:
        active_trigger_family = watch_source.active_trigger_family
        price_level = watch_source.trigger_payload.price_level
        recheck_at_time = watch_source.trigger_payload.recheck_at_time
        invalidation_rules = watch_source.invalidation_rules

    claims = [
        _build_watch_state_claim(
            packet,
            state=state,
            active_trigger_family=active_trigger_family,
            price_level=price_level,
            recheck_at_time=recheck_at_time,
            context_snapshot=context_snapshot,
            trigger_truth_state=trigger_truth_state,
            terminal_reason=terminal_reason,
            prior_watch=prior_watch,
            evaluation_time=evaluation_time,
        ),
        _build_watch_routing_claim(
            state=state,
            routing_recommendation=routing_recommendation,
            context_snapshot=context_snapshot,
            trigger_truth_state=trigger_truth_state,
            evaluation_time=evaluation_time,
        ),
    ]
    invalidation_claim = _build_watch_invalidation_claim(
        state=state,
        trigger_invalidated=trigger_invalidated,
        invalidation_rules=invalidation_rules,
        current_price=packet.market_packet.current_price,
        evaluation_time=evaluation_time,
    )
    if invalidation_claim is not None:
        claims.append(invalidation_claim)
    return claims


def _build_watch_state_claim(
    packet: HistoricalPacket,
    *,
    state: str,
    active_trigger_family: str,
    price_level: float | None,
    recheck_at_time: datetime | None,
    context_snapshot: ReadinessWatchContextSnapshot,
    trigger_truth_state: str,
    terminal_reason: str | None,
    prior_watch: ReadinessWatchV1 | None,
    evaluation_time: datetime,
) -> NarrativeClaim:
    if state == "READY_FOR_REANALYSIS":
        statement = (
            f"NQ watch is ready_for_reanalysis after {active_trigger_family} observed at "
            f"{_format_price(price_level or packet.market_packet.current_price)} and value shifted from "
            f"{(prior_watch.context_snapshot.value_location_state if prior_watch else context_snapshot.value_location_state).lower()} "
            f"to {context_snapshot.value_location_state.lower()}."
        )
    elif state == "CONTEXT_CONTAMINATED":
        statement = (
            f"NQ watch is context_contaminated because packet freshness is {context_snapshot.freshness_state.lower()} "
            f"at age {context_snapshot.packet_age_seconds} seconds."
        )
    elif state == "LOCKED_OUT":
        statement = (
            f"NQ watch is locked_out because deterministic lockout reasons are "
            f"{', '.join(context_snapshot.lockout_reasons)}."
        )
    elif state == "THESIS_INVALIDATED":
        statement = (
            f"NQ watch is thesis_invalidated because current price {_format_price(packet.market_packet.current_price)} "
            f"breached the active invalidation level."
        )
    elif state == "TERMINAL_EXPIRED":
        statement = (
            f"NQ watch is terminal_expired because evaluation time {_render_datetime(evaluation_time)} "
            f"reached the watch expiry."
        )
    elif active_trigger_family == "price_level_touch":
        statement = (
            f"NQ watch is {state.lower()} with price-touch monitoring at {_format_price(price_level or 0.0)} "
            f"while current price is {_format_price(packet.market_packet.current_price)} and value remains "
            f"{context_snapshot.value_location_state.lower()}."
        )
    else:
        statement = (
            f"NQ watch is {state.lower()} with a timed recheck at {_render_datetime(recheck_at_time or evaluation_time)} "
            f"while event risk is {context_snapshot.event_risk_state.lower()}."
        )

    provenance = [
        _derived_provenance(
            "watch_state",
            "derived.watch_state",
            state,
            "The watch state is the deterministic lifecycle output at the current evaluation time.",
            observed_at=evaluation_time,
        ),
        _field_provenance(
            "current_price",
            "context_snapshot.current_price",
            _format_price(context_snapshot.current_price),
            "Current price anchors the operator-facing watch state summary.",
            observed_at=evaluation_time,
        ),
    ]
    if active_trigger_family == "price_level_touch" and price_level is not None:
        provenance.append(
            _field_provenance(
                "trigger_price_level",
                "trigger_payload.price_level",
                _format_price(price_level),
                "The active price-touch level anchors the watch monitoring statement.",
                observed_at=evaluation_time,
            )
        )
    if recheck_at_time is not None:
        provenance.append(
            _field_provenance(
                "recheck_at_time",
                "trigger_payload.recheck_at_time",
                _render_datetime(recheck_at_time),
                "The active timed recheck anchors the watch monitoring statement.",
                observed_at=evaluation_time,
            )
        )
    provenance.append(
        _field_provenance(
            "value_location_state",
            "context_snapshot.value_location_state",
            context_snapshot.value_location_state,
            "Value location anchors the current or changed value-context reference.",
            observed_at=evaluation_time,
        )
    )
    if prior_watch is not None and prior_watch.context_snapshot.value_location_state != context_snapshot.value_location_state:
        provenance.append(
            _field_provenance(
                "prior_value_location_state",
                "prior_watch.context_snapshot.value_location_state",
                prior_watch.context_snapshot.value_location_state,
                "Prior value location anchors the value-context transition reference.",
                observed_at=prior_watch.updated_at,
            )
        )
    if trigger_truth_state:
        provenance.append(
            _derived_provenance(
                "trigger_truth_state",
                "derived.trigger_truth_state",
                trigger_truth_state,
                "Trigger truth state anchors whether the watch is still waiting or observed.",
                observed_at=evaluation_time,
            )
        )
    if terminal_reason is not None:
        provenance.append(
            _derived_provenance(
                "terminal_reason",
                "derived.terminal_reason",
                terminal_reason,
                "Terminal reason anchors the deterministic terminal watch state.",
                observed_at=evaluation_time,
            )
        )

    return NarrativeClaim(
        claim_id="watch_state_reason",
        category="state",
        statement=statement,
        evidence_fields=[
            "context_snapshot.current_price",
            "context_snapshot.value_location_state",
            "trigger_payload.family",
        ],
        provenance=provenance,
    )


def _build_watch_routing_claim(
    *,
    state: str,
    routing_recommendation: str,
    context_snapshot: ReadinessWatchContextSnapshot,
    trigger_truth_state: str,
    evaluation_time: datetime,
) -> NarrativeClaim:
    if routing_recommendation == "REQUERY_STAGE_B":
        statement = (
            "Route the operator to REQUERY_STAGE_B because the trigger is observed and structure confirmation is satisfied."
        )
    elif routing_recommendation == "EXPIRE_WATCH":
        statement = "Expire the watch because deterministic invalidation or expiry conditions closed the watch."
    elif state == "CONTEXT_CONTAMINATED":
        statement = "Keep the operator in WAIT until a fresh packet rebuilds the deterministic context."
    elif state == "LOCKED_OUT":
        statement = "Keep the operator in WAIT until the deterministic lockout condition clears."
    else:
        statement = "Keep the operator in WAIT because the watch has not yet unlocked deterministic reanalysis."

    return NarrativeClaim(
        claim_id="watch_routing_reason",
        category="routing",
        statement=statement,
        evidence_fields=[
            "routing_recommendation",
            "context_snapshot.freshness_state",
            "context_snapshot.session_access_state",
        ],
        provenance=[
            _derived_provenance(
                "routing_recommendation",
                "derived.routing_recommendation",
                routing_recommendation,
                "Routing recommendation is the deterministic operator action output.",
                observed_at=evaluation_time,
            ),
            _derived_provenance(
                "trigger_truth_state",
                "derived.trigger_truth_state",
                trigger_truth_state,
                "Trigger truth state informs whether the operator must keep waiting or requery Stage B.",
                observed_at=evaluation_time,
            ),
            _field_provenance(
                "freshness_state",
                "context_snapshot.freshness_state",
                context_snapshot.freshness_state,
                "Freshness state constrains whether waiting is a contamination hold or a clean watch state.",
                observed_at=evaluation_time,
            ),
            _field_provenance(
                "session_access_state",
                "context_snapshot.session_access_state",
                context_snapshot.session_access_state,
                "Session access state constrains whether waiting is a lockout hold.",
                observed_at=evaluation_time,
            ),
        ],
    )


def _build_watch_invalidation_claim(
    *,
    state: str,
    trigger_invalidated: bool,
    invalidation_rules: Sequence[ReadinessInvalidationRule],
    current_price: float,
    evaluation_time: datetime,
) -> NarrativeClaim | None:
    if state != "THESIS_INVALIDATED" and not trigger_invalidated:
        return None

    price_rule = next((rule for rule in invalidation_rules if rule.kind == "PRICE_BREACH"), None)
    if state == "TERMINAL_EXPIRED":
        statement = "The watch expired because the bounded readiness window reached its deterministic end."
        provenance = [
            _derived_provenance(
                "trigger_invalidated",
                "derived.trigger_invalidated",
                str(trigger_invalidated).lower(),
                "Trigger invalidation marks the watch as no longer usable.",
                observed_at=evaluation_time,
            )
        ]
    elif price_rule is not None:
        statement = (
            f"The active invalidation guard is breached because current price {_format_price(current_price)} "
            f"is through {_format_price(price_rule.price_level or 0.0)}."
        )
        provenance = [
            _field_provenance(
                "current_price",
                "context_snapshot.current_price",
                _format_price(current_price),
                "Current price anchors the invalidation check.",
                observed_at=evaluation_time,
            )
        ] + list(price_rule.provenance)
    else:
        statement = "The active trigger can no longer be used without rebuilding the deterministic watch."
        provenance = [
            _derived_provenance(
                "trigger_invalidated",
                "derived.trigger_invalidated",
                str(trigger_invalidated).lower(),
                "Trigger invalidation marks the watch as no longer usable.",
                observed_at=evaluation_time,
            )
        ]

    return NarrativeClaim(
        claim_id="watch_invalidation_reason",
        category="invalidation",
        statement=statement,
        evidence_fields=["invalidation_rules", "context_snapshot.current_price"],
        provenance=provenance,
    )


def _detect_watch_changes(
    prior_watch: ReadinessWatchV1,
    current_context: ReadinessWatchContextSnapshot,
    *,
    trigger_truth_state: str,
    trigger_invalidated: bool,
    next_state: str,
    next_routing_recommendation: str,
) -> list[ReadinessWatchDetectedChange]:
    changes: list[ReadinessWatchDetectedChange] = []

    _append_change(
        changes,
        kind="freshness_state_change",
        from_value=prior_watch.context_snapshot.freshness_state,
        to_value=current_context.freshness_state,
        detail=(
            f"Freshness moved from {prior_watch.context_snapshot.freshness_state} to "
            f"{current_context.freshness_state}."
        ),
    )
    _append_change(
        changes,
        kind="session_access_change",
        from_value=prior_watch.context_snapshot.session_access_state,
        to_value=current_context.session_access_state,
        detail=(
            f"Session access moved from {prior_watch.context_snapshot.session_access_state} to "
            f"{current_context.session_access_state}."
        ),
    )
    _append_change(
        changes,
        kind="event_risk_change",
        from_value=prior_watch.context_snapshot.event_risk_state,
        to_value=current_context.event_risk_state,
        detail=(
            f"Event risk moved from {prior_watch.context_snapshot.event_risk_state} to "
            f"{current_context.event_risk_state}."
        ),
    )
    _append_change(
        changes,
        kind="macro_release_posture_change",
        from_value=(
            f"{prior_watch.context_snapshot.macro_release_context}|"
            f"{prior_watch.context_snapshot.relative_strength_vs_es:.2f}|"
            f"{prior_watch.context_snapshot.megacap_leadership_posture}|"
            f"{prior_watch.context_snapshot.bond_yield_context}"
        ),
        to_value=(
            f"{current_context.macro_release_context}|"
            f"{current_context.relative_strength_vs_es:.2f}|"
            f"{current_context.megacap_leadership_posture}|"
            f"{current_context.bond_yield_context}"
        ),
        detail="Macro release, yield, or megacap leadership posture changed on the validated packet.",
    )
    _append_change(
        changes,
        kind="value_location_change",
        from_value=prior_watch.context_snapshot.value_location_state,
        to_value=current_context.value_location_state,
        detail=(
            f"Value location moved from {prior_watch.context_snapshot.value_location_state} to "
            f"{current_context.value_location_state}."
        ),
    )
    _append_change(
        changes,
        kind="trigger_truth_change",
        from_value=prior_watch.last_observation.trigger_truth_state,
        to_value=trigger_truth_state,
        detail=(
            f"Trigger truth moved from {prior_watch.last_observation.trigger_truth_state} to "
            f"{trigger_truth_state}."
        ),
    )
    if trigger_invalidated:
        changes.append(
            ReadinessWatchDetectedChange(
                kind="trigger_invalidation",
                from_value="ACTIVE",
                to_value="INVALIDATED",
                detail="The active trigger can no longer be used without rebuilding the watch.",
            )
        )
    if next_state == "THESIS_INVALIDATED":
        changes.append(
            ReadinessWatchDetectedChange(
                kind="thesis_invalidation",
                from_value=prior_watch.state,
                to_value="THESIS_INVALIDATED",
                detail="Deterministic watch conditions now require the current watch to be retired.",
            )
        )
    _append_change(
        changes,
        kind="routing_recommendation_change",
        from_value=prior_watch.routing_recommendation,
        to_value=next_routing_recommendation,
        detail=(
            f"Operator routing changed from {prior_watch.routing_recommendation} to "
            f"{next_routing_recommendation}."
        ),
    )
    return changes


def _append_change(
    changes: list[ReadinessWatchDetectedChange],
    *,
    kind: str,
    from_value: str,
    to_value: str,
    detail: str,
) -> None:
    shared_append_detected_change(
        changes,
        kind=kind,
        from_value=from_value,
        to_value=to_value,
        detail=detail,
    )


def _structure_claim_text(
    packet: HistoricalPacket,
    feature_snapshot: PremarketBriefingFeatureSnapshot,
) -> str:
    market = packet.market_packet
    if feature_snapshot.directional_lean == "BEARISH":
        return (
            f"NQ is trading below VWAP {_format_price(market.vwap)} with negative directional posture "
            f"toward developing VAL at {_format_price(market.current_session_val)}."
        )
    if feature_snapshot.directional_lean == "TWO_WAY":
        return (
            f"NQ is rotating inside developing value between {_format_price(market.current_session_val)} "
            f"and {_format_price(market.current_session_vah)} with no clean directional edge yet."
        )
    return (
        f"NQ is holding above VWAP {_format_price(market.vwap)} and session POC "
        f"{_format_price(market.current_session_poc)} with positive flow, keeping the prior-day high "
        f"{_format_price(market.prior_day_high)} in play."
    )


def _narrative_thesis_claim_ids(claims: Sequence[NarrativeClaim]) -> list[str]:
    del claims
    return [
        "value_support_or_resistance",
        "macro_context",
        "event_risk_window",
    ]


def _join_claim_statements(
    claims: Sequence[NarrativeClaim],
    claim_ids: Sequence[str],
) -> str:
    claim_lookup = {claim.claim_id: claim for claim in claims}
    return " ".join(claim_lookup[claim_id].statement for claim_id in claim_ids)


def _field_provenance(
    provenance_id: str,
    source_path: str,
    value: str | None,
    detail: str,
    *,
    observed_at: datetime | None,
) -> NarrativeProvenance:
    return NarrativeProvenance(
        provenance_id=provenance_id,
        kind="field",
        source_path=source_path,
        value=value or "null",
        detail=detail,
        observed_at=observed_at,
    )


def _derived_provenance(
    provenance_id: str,
    source_path: str,
    value: str,
    detail: str,
    *,
    observed_at: datetime | None,
) -> NarrativeProvenance:
    return NarrativeProvenance(
        provenance_id=provenance_id,
        kind="derived_condition",
        source_path=source_path,
        value=value,
        detail=detail,
        observed_at=observed_at,
    )


def _render_datetime(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _candidate_price_trigger(
    packet: HistoricalPacket,
    directional_lean: DirectionalLean,
) -> tuple[str, float] | None:
    current_price = packet.market_packet.current_price
    min_gap = packet.contract_metadata.tick_size / 2

    if directional_lean == "TWO_WAY":
        return None
    if directional_lean == "BEARISH":
        candidates = [
            ("current_session_val", packet.market_packet.current_session_val),
            ("prior_day_low", packet.market_packet.prior_day_low),
            ("overnight_low", packet.market_packet.overnight_low),
        ]
        below = [
            (label, price)
            for label, price in candidates
            if current_price - price > min_gap
        ]
        if not below:
            return None
        return min(below, key=lambda item: current_price - item[1])

    candidates = [
        ("current_session_vah", packet.market_packet.current_session_vah),
        ("prior_day_high", packet.market_packet.prior_day_high),
        ("overnight_high", packet.market_packet.overnight_high),
    ]
    above = [(label, price) for label, price in candidates if price - current_price > min_gap]
    if not above:
        return None
    return min(above, key=lambda item: item[1] - current_price)


def _directional_lean(packet: HistoricalPacket) -> DirectionalLean:
    bullish_votes = 0
    bearish_votes = 0

    if packet.market_packet.current_price >= packet.market_packet.session_open:
        bullish_votes += 1
    else:
        bearish_votes += 1
    if packet.market_packet.current_price >= packet.market_packet.vwap:
        bullish_votes += 1
    else:
        bearish_votes += 1
    if packet.market_packet.cumulative_delta > 0:
        bullish_votes += 1
    elif packet.market_packet.cumulative_delta < 0:
        bearish_votes += 1

    if bullish_votes >= 2 and bullish_votes > bearish_votes:
        return "BULLISH"
    if bearish_votes >= 2 and bearish_votes > bullish_votes:
        return "BEARISH"
    return "TWO_WAY"


def _price_location_vs_vwap(packet: HistoricalPacket) -> str:
    delta = packet.market_packet.current_price - packet.market_packet.vwap
    threshold = packet.contract_metadata.tick_size / 2
    if abs(delta) <= threshold:
        return "AT"
    return "ABOVE" if delta > 0 else "BELOW"


def _price_location_vs_value(packet: HistoricalPacket) -> str:
    price = packet.market_packet.current_price
    if price > packet.market_packet.current_session_vah:
        return "ABOVE_VAH"
    if price < packet.market_packet.current_session_val:
        return "BELOW_VAL"
    return "INSIDE_VALUE"


def _monitor_posture(
    *,
    event_lockout_active: bool,
    governance_lock_reasons: list[str],
    session_access_state: str,
    freshness_state: str,
    directional_lean: DirectionalLean,
) -> str:
    if (
        event_lockout_active
        or governance_lock_reasons
        or session_access_state == "OUTSIDE_ALLOWED_HOURS"
    ):
        return "LOCKED_OUT"
    if freshness_state == "STALE" or directional_lean == "TWO_WAY":
        return "STAND_ASIDE"
    return "MONITOR"


def _coerce_nq_packet(packet: HistoricalPacket | Mapping[str, Any]) -> HistoricalPacket:
    validated = packet if isinstance(packet, HistoricalPacket) else validate_historical_packet(packet)
    if validated.market_packet.contract != "NQ":
        raise ValueError("Readiness v2 NQ slice only supports NQ packets.")
    if not isinstance(validated.contract_specific_extension, NQContractSpecificExtension):
        raise ValueError("Readiness v2 NQ slice requires an NQ contract extension.")
    return validated


def _source_packet_ref(packet: HistoricalPacket) -> str:
    return f"historical_packet:{packet.market_packet.contract}:{_as_utc(packet.market_packet.timestamp).isoformat()}"


def _artifact_id(kind: str, evaluation_time: datetime) -> str:
    return f"nq-{kind}-{evaluation_time.strftime('%Y%m%dT%H%M%SZ').lower()}"


def _format_price(price: float) -> str:
    return f"{price:.6f}".rstrip("0").rstrip(".")


def _humanize_level_label(label: str) -> str:
    return label.replace("_", " ")


def _macro_release_context(packet: HistoricalPacket, evaluation_time: datetime) -> str:
    released_events = [
        event
        for event in packet.market_packet.event_calendar_remainder
        if event.event_state == "released"
    ]
    latest_released = (
        None if not released_events else max(released_events, key=lambda event: _as_utc(event.time))
    )
    next_event = _next_upcoming_event(packet, evaluation_time)

    released_fragment = (
        f"{latest_released.name} released {latest_released.minutes_since} minutes ago"
        if latest_released is not None and latest_released.minutes_since is not None
        else "No released macro event is active on the packet"
    )
    next_fragment = (
        f"next {next_event.name} in {_minutes_until(next_event.time, evaluation_time)} minutes"
        if next_event is not None
        else "no upcoming scheduled event"
    )
    return f"{released_fragment}; {next_fragment}."


def _megacap_leadership_posture(extension: NQContractSpecificExtension) -> str:
    table = extension.megacap_leadership_table or {}
    if not table:
        return "megacap leadership posture is unavailable"

    up_count = sum(1 for status in table.values() if status == "up")
    down_count = sum(1 for status in table.values() if status == "down")
    flat_count = sum(1 for status in table.values() if status == "flat")
    if up_count > down_count and up_count >= 2:
        return f"megacap leadership is supportive ({up_count} up, {flat_count} flat)"
    if down_count > up_count and down_count >= 2:
        return f"megacap leadership is lagging ({down_count} down, {flat_count} flat)"
    return f"megacap leadership is mixed ({up_count} up, {down_count} down, {flat_count} flat)"


def _bond_yield_context(packet: HistoricalPacket) -> str:
    context = packet.market_packet.cross_market_context or {}
    bond_yield_direction = context.get("bond_yield_direction")
    if isinstance(bond_yield_direction, str) and bond_yield_direction:
        return bond_yield_direction
    return "unavailable"


def _packet_age_seconds(packet: HistoricalPacket, evaluation_time: datetime) -> int:
    delta_seconds = int((evaluation_time - _as_utc(packet.market_packet.timestamp)).total_seconds())
    if delta_seconds < 0:
        raise ValueError("evaluation_time must be at or after market_packet.timestamp.")
    return delta_seconds


def _resolve_recheck_time(created_at: datetime, expires_at: datetime) -> datetime:
    candidate = created_at + timedelta(minutes=READINESS_V2_RECHECK_MINUTES)
    return min(candidate, expires_at)


def _minutes_until(target_time: datetime, evaluation_time: datetime) -> int:
    return max(0, int((_as_utc(target_time) - evaluation_time).total_seconds() // 60))


def _next_upcoming_event(
    packet: HistoricalPacket,
    evaluation_time: datetime,
) -> EventCalendarEntry | None:
    upcoming = [
        event
        for event in packet.market_packet.event_calendar_remainder
        if event.event_state == "upcoming" and _as_utc(event.time) >= evaluation_time
    ]
    if not upcoming:
        return None
    return min(upcoming, key=lambda event: _as_utc(event.time))


def _event_risk_state(
    packet: HistoricalPacket,
    evaluation_time: datetime,
    next_event: EventCalendarEntry | None,
) -> ReadinessEventRiskState:
    if next_event is None:
        return "CLEAR"
    if _event_lockout_active(packet, evaluation_time, next_event):
        return "LOCKOUT_ACTIVE"
    if _minutes_until(next_event.time, evaluation_time) <= READINESS_V2_EVENT_ELEVATED_WINDOW_MINUTES:
        return "ELEVATED"
    return "CLEAR"


def _auction_proximity_state(
    packet: HistoricalPacket,
    evaluation_time: datetime,
    next_event: EventCalendarEntry | None,
) -> ReadinessAuctionProximityState:
    if next_event is None or "auction" not in next_event.name.lower():
        return "NONE"
    if _event_lockout_active(packet, evaluation_time, next_event):
        return "LOCKOUT_ACTIVE"
    if _minutes_until(next_event.time, evaluation_time) <= READINESS_V2_AUCTION_ELEVATED_WINDOW_MINUTES:
        return "ELEVATED"
    return "SCHEDULED"


def _event_lockout_window(
    packet: HistoricalPacket,
    event: EventCalendarEntry,
) -> tuple[datetime, datetime]:
    event_time = _as_utc(event.time)
    begins_at = event_time - timedelta(minutes=packet.challenge_state.event_lockout_minutes_before)
    ends_at = event_time + timedelta(minutes=packet.challenge_state.event_lockout_minutes_after)
    return _as_utc(begins_at), _as_utc(ends_at)


def _event_lockout_active(
    packet: HistoricalPacket,
    evaluation_time: datetime,
    next_event: EventCalendarEntry | None,
) -> bool:
    if next_event is None:
        return False
    begins_at, ends_at = _event_lockout_window(packet, next_event)
    return begins_at <= evaluation_time <= ends_at


def _session_access_state(packet: HistoricalPacket, evaluation_time: datetime) -> str:
    et_time = evaluation_time.astimezone(ET_TZ)
    session_start = _et_datetime(et_time, packet.contract_metadata.allowed_hours_start_et)
    session_end = _et_datetime(et_time, packet.contract_metadata.allowed_hours_end_et)
    if session_start <= et_time <= session_end:
        return "INSIDE_ALLOWED_HOURS"
    return "OUTSIDE_ALLOWED_HOURS"


def _session_end_time(packet: HistoricalPacket, evaluation_time: datetime) -> datetime:
    et_time = evaluation_time.astimezone(ET_TZ)
    return _as_utc(_et_datetime(et_time, packet.contract_metadata.allowed_hours_end_et))


def _validate_watch_triggers(
    briefing: PremarketBriefingV1,
    triggers: Sequence[QueryTriggerV1],
) -> None:
    if not triggers:
        raise ValueError("NQ readiness watch requires at least one query trigger.")

    seen_families: set[str] = set()
    for trigger in triggers:
        if trigger.contract != "NQ":
            raise ValueError("Readiness v2 NQ slice only supports NQ query triggers.")
        if trigger.source_briefing_id != briefing.briefing_id:
            raise ValueError("All query triggers must originate from the supplied briefing.")
        if trigger.expiry_policy.expires_at != briefing.expires_at:
            raise ValueError("Query trigger expiry must match briefing expiry in the first slice.")
        if trigger.family in seen_families:
            raise ValueError("Duplicate query trigger families are not supported in the first slice.")
        seen_families.add(trigger.family)


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _et_datetime(reference_time: datetime, hhmm: str) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":", 1))
    return reference_time.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _governance_lock_reasons(packet: HistoricalPacket) -> list[str]:
    reasons: list[str] = []
    trades_today = packet.challenge_state.trades_today_by_contract.model_dump(by_alias=True)["NQ"]
    if trades_today >= packet.challenge_state.max_trades_per_contract_per_day:
        reasons.append("max_trades_per_contract_reached")
    if packet.challenge_state.trades_today_all >= packet.challenge_state.max_trades_per_day:
        reasons.append("max_trades_per_day_reached")
    if packet.challenge_state.daily_realized_pnl <= -packet.challenge_state.daily_loss_stop_dollars:
        reasons.append("daily_loss_stop_reached")
    if any(position.contract == "NQ" for position in packet.challenge_state.current_open_positions):
        reasons.append("existing_nq_position_open")
    return reasons


def _resolve_expiry(
    packet: HistoricalPacket,
    evaluation_time: datetime,
    next_event: Any | None,
) -> datetime:
    del packet
    del next_event
    return evaluation_time + timedelta(minutes=READINESS_V2_WATCH_TTL_MINUTES)


def _is_trigger_observed(
    packet: HistoricalPacket,
    trigger: QueryTriggerV1,
    evaluation_time: datetime,
) -> bool:
    if trigger.family == "recheck_at_time":
        return evaluation_time >= (trigger.deterministic_parameters.recheck_at_time or evaluation_time)

    level = trigger.deterministic_parameters.price_level or packet.market_packet.current_price
    buffer_ticks = trigger.deterministic_parameters.buffer_ticks or 0
    threshold = (
        packet.contract_metadata.tick_size / 2
        if buffer_ticks == 0
        else packet.contract_metadata.tick_size * buffer_ticks
    )
    return abs(packet.market_packet.current_price - level) <= threshold


def _is_any_invalidation_met(
    rules: Sequence[ReadinessInvalidationRule],
    current_price: float,
    evaluation_time: datetime,
) -> bool:
    for rule in rules:
        if rule.kind == "PRICE_BREACH":
            if rule.comparison == "LESS_THAN_OR_EQUAL" and current_price <= (rule.price_level or current_price):
                return True
            if rule.comparison == "GREATER_THAN_OR_EQUAL" and current_price >= (rule.price_level or current_price):
                return True
        elif rule.kind in {"EVENT_LOCKOUT", "SESSION_CLOSE"} and rule.effective_at is not None:
            if evaluation_time >= rule.effective_at:
                return True
    return False

