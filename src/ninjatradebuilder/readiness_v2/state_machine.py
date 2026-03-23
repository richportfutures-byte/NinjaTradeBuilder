from __future__ import annotations

from pydantic import AwareDatetime, Field

from ..schemas.inputs import StrictModel
from ..schemas.readiness_v2 import (
    ReadinessRoutingRecommendation,
    ReadinessRoutingTarget,
    ReadinessV2WatchNextAction,
    ReadinessV2WatchState,
)


STATE_ACTIONS: dict[ReadinessV2WatchState, tuple[ReadinessV2WatchNextAction, ...]] = {
    "UNARMED": ("BUILD_QUERY_TRIGGER", "ARM_WATCH"),
    "ARMED_WAITING": ("EVALUATE_TRIGGER", "DISARM_WATCH"),
    "TRIGGER_OBSERVED": (
        "CAPTURE_TRIGGER_OBSERVATION",
        "BEGIN_STRUCTURE_FORMATION",
    ),
    "STRUCTURE_FORMING": ("EVALUATE_TRIGGER", "DISARM_WATCH"),
    "READY_FOR_REANALYSIS": ("ROUTE_STAGE_AB_REANALYSIS", "ARCHIVE_WATCH"),
    "READY_FOR_SETUP_REENTRY": ("ARCHIVE_WATCH",),
    "CONTEXT_CONTAMINATED": (
        "REQUEST_FRESH_PACKET",
        "REBUILD_PREMARKET_BRIEFING",
    ),
    "THESIS_INVALIDATED": ("ARCHIVE_WATCH", "REBUILD_PREMARKET_BRIEFING"),
    "LOCKED_OUT": ("WAIT_FOR_LOCKOUT_CLEAR", "EVALUATE_TRIGGER"),
    "TERMINAL_EXPIRED": ("ARCHIVE_WATCH", "REBUILD_PREMARKET_BRIEFING"),
}


class WatchStateEvaluation(StrictModel):
    evaluated_at: AwareDatetime
    trigger_observed: bool = False
    requires_structure_confirmation: bool = False
    structure_confirmed: bool = False
    contamination_reasons: list[str] = Field(default_factory=list)
    thesis_invalidated: bool = False
    lockout_reasons: list[str] = Field(default_factory=list)
    expired: bool = False


class WatchStateDecision(StrictModel):
    next_state: ReadinessV2WatchState
    routing_target: ReadinessRoutingTarget
    routing_recommendation: ReadinessRoutingRecommendation
    allowed_next_actions: list[ReadinessV2WatchNextAction]
    terminal_reason: str | None = None


def transition_watch_state(
    current_state: ReadinessV2WatchState,
    evaluation: WatchStateEvaluation,
) -> WatchStateDecision:
    if current_state == "READY_FOR_SETUP_REENTRY":
        raise ValueError(
            "READY_FOR_SETUP_REENTRY is outside the readiness v2 first-slice boundary."
        )
    if evaluation.expired:
        return _decision("TERMINAL_EXPIRED", terminal_reason="explicit_expiry_reached")
    if evaluation.thesis_invalidated:
        return _decision(
            "THESIS_INVALIDATED",
            terminal_reason="deterministic_invalidation_condition_met",
        )
    if evaluation.contamination_reasons:
        return _decision("CONTEXT_CONTAMINATED")
    if evaluation.lockout_reasons:
        return _decision("LOCKED_OUT")

    if current_state == "LOCKED_OUT":
        if evaluation.trigger_observed:
            if not evaluation.requires_structure_confirmation or evaluation.structure_confirmed:
                return _decision("READY_FOR_REANALYSIS", routing_target="STAGE_AB_REANALYSIS")
            return _decision("TRIGGER_OBSERVED")
        return _decision("ARMED_WAITING")
    if current_state == "UNARMED":
        return _decision("ARMED_WAITING")
    if current_state == "ARMED_WAITING":
        if evaluation.trigger_observed:
            if not evaluation.requires_structure_confirmation or evaluation.structure_confirmed:
                return _decision("READY_FOR_REANALYSIS", routing_target="STAGE_AB_REANALYSIS")
            return _decision("TRIGGER_OBSERVED")
        return _decision("ARMED_WAITING")
    if current_state == "TRIGGER_OBSERVED":
        if evaluation.requires_structure_confirmation and not evaluation.structure_confirmed:
            return _decision("STRUCTURE_FORMING")
        return _decision("READY_FOR_REANALYSIS", routing_target="STAGE_AB_REANALYSIS")
    if current_state == "STRUCTURE_FORMING":
        if evaluation.structure_confirmed:
            return _decision("READY_FOR_REANALYSIS", routing_target="STAGE_AB_REANALYSIS")
        return _decision("STRUCTURE_FORMING")
    if current_state == "CONTEXT_CONTAMINATED":
        if evaluation.trigger_observed:
            if not evaluation.requires_structure_confirmation or evaluation.structure_confirmed:
                return _decision("READY_FOR_REANALYSIS", routing_target="STAGE_AB_REANALYSIS")
            return _decision("TRIGGER_OBSERVED")
        return _decision("ARMED_WAITING")
    if current_state in {"READY_FOR_REANALYSIS", "READY_FOR_SETUP_REENTRY"}:
        return _decision(current_state, routing_target=_routing_target_for_state(current_state))
    if current_state in {"THESIS_INVALIDATED", "TERMINAL_EXPIRED"}:
        return _decision(current_state, terminal_reason="terminal_state_retained")

    raise ValueError(f"Unsupported watch state transition input: {current_state}.")


def _decision(
    state: ReadinessV2WatchState,
    *,
    routing_target: ReadinessRoutingTarget | None = None,
    terminal_reason: str | None = None,
) -> WatchStateDecision:
    resolved_target = routing_target or _routing_target_for_state(state)
    return WatchStateDecision(
        next_state=state,
        routing_target=resolved_target,
        routing_recommendation=_routing_recommendation_for_state(state),
        allowed_next_actions=list(STATE_ACTIONS[state]),
        terminal_reason=terminal_reason,
    )


def _routing_target_for_state(state: ReadinessV2WatchState) -> ReadinessRoutingTarget:
    if state == "READY_FOR_REANALYSIS":
        return "STAGE_AB_REANALYSIS"
    return "NONE"


def _routing_recommendation_for_state(
    state: ReadinessV2WatchState,
) -> ReadinessRoutingRecommendation:
    if state == "READY_FOR_REANALYSIS":
        return "REQUERY_STAGE_B"
    if state in {"THESIS_INVALIDATED", "TERMINAL_EXPIRED"}:
        return "EXPIRE_WATCH"
    return "WAIT"
