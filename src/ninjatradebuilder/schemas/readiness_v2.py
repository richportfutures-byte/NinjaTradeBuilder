from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from .cl import RealizedVolatilityContext
from .contracts import DxyContext, IndexCashTone, PriceRange, YieldContext
from .inputs import OpeningType, SessionType, StrictModel
from .outputs import ReadinessTriggerFamily

ReadinessV2Contract = Literal["ZN", "ES", "NQ", "CL", "MGC", "6E"]
BriefingMonitorPosture = Literal["MONITOR", "STAND_ASIDE", "LOCKED_OUT"]
DirectionalLean = Literal["BULLISH", "BEARISH", "TWO_WAY"]
FreshnessState = Literal["FRESH", "STALE"]
NarrativeClaimCategory = Literal[
    "structure",
    "flow",
    "risk",
    "trigger",
    "state",
    "routing",
    "invalidation",
]
NarrativeProvenanceKind = Literal["field", "derived_condition"]
PriceLocationState = Literal["ABOVE_VAH", "INSIDE_VALUE", "BELOW_VAL"]
QueryTriggerMode = Literal["deterministic", "hybrid", "llm_assisted"]
QueryTriggerPostTriggerPolicy = Literal[
    "DIRECT_REANALYSIS",
    "STRUCTURE_CONFIRMATION_REQUIRED",
]
QueryTriggerValidationStatus = Literal["EXECUTABLE", "REJECTED"]
ReadinessAuctionProximityState = Literal["NONE", "SCHEDULED", "ELEVATED", "LOCKOUT_ACTIVE"]
ReadinessEventRiskState = Literal["CLEAR", "ELEVATED", "LOCKOUT_ACTIVE"]
ReadinessInvalidationKind = Literal[
    "PRICE_BREACH",
    "STALENESS",
    "EVENT_LOCKOUT",
    "SESSION_CLOSE",
    "GOVERNANCE_LOCKOUT",
]
ReadinessInvalidationComparison = Literal[
    "LESS_THAN_OR_EQUAL",
    "GREATER_THAN_OR_EQUAL",
]
ReadinessLockoutKind = Literal[
    "EVENT_LOCKOUT",
    "SESSION_LOCKOUT",
    "GOVERNANCE_LOCKOUT",
]
ReadinessRoutingTarget = Literal["NONE", "STAGE_AB_REANALYSIS", "STAGE_C_REENTRY"]
ReadinessRoutingRecommendation = Literal["WAIT", "REQUERY_STAGE_B", "EXPIRE_WATCH"]
ReadinessSourceKind = Literal["premarket_briefing", "query_trigger", "contract_analysis"]
ReadinessTriggerTruthState = Literal["PENDING", "OBSERVED", "NOT_OBSERVED"]
ReadinessUnlockAction = Literal[
    "ROUTE_STAGE_AB_REANALYSIS",
    "ROUTE_STAGE_C_REENTRY",
    "CLEAR_LOCKOUT",
    "MARK_INVALIDATED",
]
ReadinessV2WatchNextAction = Literal[
    "BUILD_QUERY_TRIGGER",
    "ARM_WATCH",
    "EVALUATE_TRIGGER",
    "DISARM_WATCH",
    "CAPTURE_TRIGGER_OBSERVATION",
    "BEGIN_STRUCTURE_FORMATION",
    "ROUTE_STAGE_AB_REANALYSIS",
    "ROUTE_STAGE_C_REENTRY",
    "REQUEST_FRESH_PACKET",
    "REBUILD_PREMARKET_BRIEFING",
    "WAIT_FOR_LOCKOUT_CLEAR",
    "ARCHIVE_WATCH",
]
ReadinessWatchDetectedChangeKind = Literal[
    "freshness_state_change",
    "session_access_change",
    "event_risk_change",
    "auction_proximity_change",
    "macro_release_posture_change",
    "value_location_change",
    "trigger_truth_change",
    "trigger_invalidation",
    "thesis_invalidation",
    "routing_recommendation_change",
]
ReadinessWatchTransitionReason = Literal[
    "initialized",
    "no_material_change",
    "waiting_context_shift",
    "trigger_requery_ready",
    "context_contaminated",
    "lockout_applied",
    "thesis_invalidated",
    "watch_expired",
]
ReadinessV2ReplayPhase = Literal["bootstrap", "update"]
ReadinessV2ReplayValidationStatus = Literal["VALID"]
ReadinessV2WatchState = Literal[
    "UNARMED",
    "ARMED_WAITING",
    "TRIGGER_OBSERVED",
    "STRUCTURE_FORMING",
    "READY_FOR_REANALYSIS",
    "READY_FOR_SETUP_REENTRY",
    "CONTEXT_CONTAMINATED",
    "THESIS_INVALIDATED",
    "LOCKED_OUT",
    "TERMINAL_EXPIRED",
]
SessionAccessState = Literal["INSIDE_ALLOWED_HOURS", "OUTSIDE_ALLOWED_HOURS"]
VwapLocationState = Literal["ABOVE", "AT", "BELOW"]


class NarrativeProvenance(StrictModel):
    provenance_id: str
    kind: NarrativeProvenanceKind
    source_path: str
    value: str
    detail: str
    observed_at: AwareDatetime | None = None


class NarrativeClaim(StrictModel):
    claim_id: str
    category: NarrativeClaimCategory
    statement: str
    evidence_fields: list[str] = Field(min_length=1, max_length=6)
    provenance: list[NarrativeProvenance] = Field(min_length=1, max_length=8)


class PremarketBriefingSessionSnapshot(StrictModel):
    session_type: SessionType
    evaluation_timestamp: AwareDatetime
    packet_timestamp: AwareDatetime
    session_access_state: SessionAccessState
    freshness_state: FreshnessState
    packet_age_seconds: int = Field(ge=0)
    next_event_name: str | None = None
    next_event_time: AwareDatetime | None = None
    minutes_until_next_event: int | None = Field(default=None, ge=0)
    event_lockout_active: bool
    governance_lockout_active: bool
    data_quality_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_shape(self) -> "PremarketBriefingSessionSnapshot":
        if self.next_event_name is None:
            if self.next_event_time is not None or self.minutes_until_next_event is not None:
                raise ValueError(
                    "next_event_time and minutes_until_next_event require next_event_name."
                )
        elif self.next_event_time is None or self.minutes_until_next_event is None:
            raise ValueError(
                "next_event_name requires next_event_time and minutes_until_next_event."
            )
        return self


class ZNPremarketBriefingFeatureSnapshot(StrictModel):
    current_price: float
    session_open: float
    vwap: float
    current_session_vah: float
    current_session_val: float
    current_session_poc: float
    prior_day_high: float
    prior_day_low: float
    session_range_ratio: float
    cumulative_delta: float
    current_volume_vs_average: float
    opening_type: OpeningType
    cash_10y_yield: float
    treasury_auction_schedule: str
    macro_release_context: str
    absorption_summary: str | None = None
    directional_lean: DirectionalLean
    price_location_vs_vwap: VwapLocationState
    price_location_vs_value: PriceLocationState


class ESPremarketBriefingFeatureSnapshot(StrictModel):
    current_price: float
    session_open: float
    vwap: float
    current_session_vah: float
    current_session_val: float
    current_session_poc: float
    prior_day_high: float
    prior_day_low: float
    session_range_ratio: float
    cumulative_delta: float
    current_volume_vs_average: float
    opening_type: OpeningType
    breadth: str
    index_cash_tone: IndexCashTone
    macro_release_context: str
    market_internals_context: str
    directional_lean: DirectionalLean
    price_location_vs_vwap: VwapLocationState
    price_location_vs_value: PriceLocationState


class NQPremarketBriefingFeatureSnapshot(StrictModel):
    current_price: float
    session_open: float
    vwap: float
    current_session_vah: float
    current_session_val: float
    current_session_poc: float
    prior_day_high: float
    prior_day_low: float
    session_range_ratio: float
    cumulative_delta: float
    current_volume_vs_average: float
    opening_type: OpeningType
    relative_strength_vs_es: float
    megacap_leadership_posture: str
    bond_yield_context: str
    macro_release_context: str
    directional_lean: DirectionalLean
    price_location_vs_vwap: VwapLocationState
    price_location_vs_value: PriceLocationState


class CLPremarketBriefingFeatureSnapshot(StrictModel):
    current_price: float
    session_open: float
    vwap: float
    current_session_vah: float
    current_session_val: float
    current_session_poc: float
    prior_day_high: float
    prior_day_low: float
    session_range_ratio: float
    cumulative_delta: float
    current_volume_vs_average: float
    opening_type: OpeningType
    eia_timing_context: str
    realized_volatility_context: RealizedVolatilityContext
    liquidity_sweep_summary: str
    dom_liquidity_summary: str
    cross_market_context: str
    directional_lean: DirectionalLean
    price_location_vs_vwap: VwapLocationState
    price_location_vs_value: PriceLocationState


class MGCPremarketBriefingFeatureSnapshot(StrictModel):
    current_price: float
    session_open: float
    vwap: float
    current_session_vah: float
    current_session_val: float
    current_session_poc: float
    prior_day_high: float
    prior_day_low: float
    session_range_ratio: float
    cumulative_delta: float
    current_volume_vs_average: float
    opening_type: OpeningType
    dxy_context: DxyContext
    yield_context: YieldContext
    macro_fear_catalyst_summary: str
    swing_penetration_volume_summary: str
    cross_market_context: str
    directional_lean: DirectionalLean
    price_location_vs_vwap: VwapLocationState
    price_location_vs_value: PriceLocationState


class SixEPremarketBriefingFeatureSnapshot(StrictModel):
    current_price: float
    session_open: float
    vwap: float
    current_session_vah: float
    current_session_val: float
    current_session_poc: float
    prior_day_high: float
    prior_day_low: float
    session_range_ratio: float
    cumulative_delta: float
    current_volume_vs_average: float
    opening_type: OpeningType
    asia_high_low: PriceRange
    london_high_low: PriceRange
    ny_high_low_so_far: PriceRange
    dxy_context: DxyContext
    europe_initiative_status: str
    cross_market_context: str
    directional_lean: DirectionalLean
    price_location_vs_vwap: VwapLocationState
    price_location_vs_value: PriceLocationState


PremarketBriefingFeatureSnapshot = (
    ZNPremarketBriefingFeatureSnapshot
    | ESPremarketBriefingFeatureSnapshot
    | NQPremarketBriefingFeatureSnapshot
    | CLPremarketBriefingFeatureSnapshot
    | MGCPremarketBriefingFeatureSnapshot
    | SixEPremarketBriefingFeatureSnapshot
)


class ReadinessInvalidationRule(StrictModel):
    rule_id: str
    kind: ReadinessInvalidationKind
    description: str
    provenance: list[NarrativeProvenance] = Field(min_length=1, max_length=6)
    price_level: float | None = None
    comparison: ReadinessInvalidationComparison | None = None
    effective_at: AwareDatetime | None = None
    flag: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "ReadinessInvalidationRule":
        if self.kind == "PRICE_BREACH":
            if self.price_level is None or self.comparison is None:
                raise ValueError(
                    "PRICE_BREACH invalidation requires price_level and comparison."
                )
            if self.effective_at is not None or self.flag is not None:
                raise ValueError(
                    "PRICE_BREACH invalidation must not include effective_at or flag."
                )
            return self

        if self.kind == "STALENESS":
            if self.flag is None:
                raise ValueError("STALENESS invalidation requires flag.")
            if self.price_level is not None or self.comparison is not None:
                raise ValueError(
                    "STALENESS invalidation must not include price_level or comparison."
                )
            return self

        if self.kind in {"EVENT_LOCKOUT", "SESSION_CLOSE"} and self.effective_at is None:
            raise ValueError(f"{self.kind} invalidation requires effective_at.")
        if self.kind == "GOVERNANCE_LOCKOUT" and self.flag is None:
            raise ValueError("GOVERNANCE_LOCKOUT invalidation requires flag.")
        if self.price_level is not None or self.comparison is not None:
            raise ValueError(
                f"{self.kind} invalidation must not include price_level or comparison."
            )
        return self


class ReadinessLockoutCondition(StrictModel):
    condition_id: str
    kind: ReadinessLockoutKind
    description: str
    provenance: list[NarrativeProvenance] = Field(min_length=1, max_length=6)
    begins_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    reason_code: str

    @model_validator(mode="after")
    def validate_time_shape(self) -> "ReadinessLockoutCondition":
        if self.kind == "EVENT_LOCKOUT" and (self.begins_at is None or self.ends_at is None):
            raise ValueError("EVENT_LOCKOUT condition requires begins_at and ends_at.")
        if self.kind == "SESSION_LOCKOUT" and self.begins_at is None:
            raise ValueError("SESSION_LOCKOUT condition requires begins_at.")
        return self


class BriefingTriggerSummary(StrictModel):
    family: ReadinessTriggerFamily
    label: str
    summary: str
    supporting_claim_ids: list[str] = Field(min_length=1, max_length=4)
    provenance: list[NarrativeProvenance] = Field(min_length=1, max_length=6)
    unlock_action: ReadinessUnlockAction
    price_level: float | None = None
    recheck_at_time: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_family_shape(self) -> "BriefingTriggerSummary":
        if self.family == "recheck_at_time":
            if self.recheck_at_time is None or self.price_level is not None:
                raise ValueError(
                    "recheck_at_time trigger summary requires recheck_at_time and forbids price_level."
                )
            return self

        if self.price_level is None or self.recheck_at_time is not None:
            raise ValueError(
                "price_level_touch trigger summary requires price_level and forbids recheck_at_time."
            )
        return self


class ExpiryPolicy(StrictModel):
    expires_at: AwareDatetime
    reason: str


class PremarketBriefingV1(StrictModel):
    schema_name: Literal["premarket_briefing_v1"] = Field(
        default="premarket_briefing_v1",
        alias="$schema",
    )
    briefing_id: str
    contract: ReadinessV2Contract = "ZN"
    created_at: AwareDatetime
    source_packet_ref: str
    packet_timestamp: AwareDatetime
    session_snapshot: PremarketBriefingSessionSnapshot
    feature_snapshot: PremarketBriefingFeatureSnapshot
    narrative_feature_thesis: str
    thesis_claims: list[NarrativeClaim] = Field(min_length=3, max_length=6)
    narrative_feature_thesis_claim_ids: list[str] = Field(min_length=2, max_length=4)
    monitor_posture: BriefingMonitorPosture
    candidate_trigger_summaries: list[BriefingTriggerSummary] = Field(
        min_length=1,
        max_length=4,
    )
    invalidation_conditions: list[ReadinessInvalidationRule] = Field(
        min_length=1,
        max_length=6,
    )
    lockout_conditions: list[ReadinessLockoutCondition] = Field(default_factory=list)
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def validate_temporal_shape(self) -> "PremarketBriefingV1":
        if self.packet_timestamp > self.created_at:
            raise ValueError("packet_timestamp must be at or before created_at.")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at.")
        if self.monitor_posture == "LOCKED_OUT" and not self.lockout_conditions:
            raise ValueError("LOCKED_OUT monitor_posture requires lockout_conditions.")
        if self.monitor_posture != "LOCKED_OUT" and (
            self.session_snapshot.event_lockout_active
            or self.session_snapshot.governance_lockout_active
            or self.session_snapshot.session_access_state == "OUTSIDE_ALLOWED_HOURS"
        ):
            raise ValueError(
                "Event, governance, or session lockout state requires monitor_posture = LOCKED_OUT."
            )
        claim_lookup = {claim.claim_id: claim for claim in self.thesis_claims}
        if set(self.narrative_feature_thesis_claim_ids) - set(claim_lookup):
            raise ValueError("narrative_feature_thesis_claim_ids must reference thesis_claims.")
        if _join_claim_statements(claim_lookup, self.narrative_feature_thesis_claim_ids) != self.narrative_feature_thesis:
            raise ValueError(
                "narrative_feature_thesis must be the ordered join of narrative_feature_thesis_claim_ids."
            )
        for summary in self.candidate_trigger_summaries:
            if set(summary.supporting_claim_ids) - set(claim_lookup):
                raise ValueError(
                    "candidate_trigger_summaries.supporting_claim_ids must reference thesis_claims."
                )
        return self


class QueryTriggerDeterministicParameters(StrictModel):
    family: ReadinessTriggerFamily
    recheck_at_time: AwareDatetime | None = None
    price_level: float | None = None
    buffer_ticks: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_family_shape(self) -> "QueryTriggerDeterministicParameters":
        if self.family == "recheck_at_time":
            if self.recheck_at_time is None:
                raise ValueError(
                    "recheck_at_time deterministic parameters require recheck_at_time."
                )
            if self.price_level is not None or self.buffer_ticks is not None:
                raise ValueError(
                    "recheck_at_time deterministic parameters must not include price_level or buffer_ticks."
                )
            return self

        if self.price_level is None or self.buffer_ticks is None:
            raise ValueError(
                "price_level_touch deterministic parameters require price_level and buffer_ticks."
            )
        if self.recheck_at_time is not None:
            raise ValueError(
                "price_level_touch deterministic parameters must not include recheck_at_time."
            )
        return self


class QueryTriggerV1(StrictModel):
    schema_name: Literal["query_trigger_v1"] = Field(
        default="query_trigger_v1",
        alias="$schema",
    )
    trigger_id: str
    source_briefing_id: str
    contract: ReadinessV2Contract = "ZN"
    created_at: AwareDatetime
    family: ReadinessTriggerFamily
    mode: QueryTriggerMode
    label: str
    deterministic_parameters: QueryTriggerDeterministicParameters
    supporting_claim_ids: list[str] = Field(min_length=1, max_length=4)
    unlock_action: ReadinessUnlockAction
    post_trigger_policy: QueryTriggerPostTriggerPolicy
    expiry_policy: ExpiryPolicy
    invalidation_policy: list[ReadinessInvalidationRule] = Field(
        min_length=1,
        max_length=6,
    )
    operator_explanation: str
    operator_claims: list[NarrativeClaim] = Field(min_length=1, max_length=4)
    operator_explanation_claim_ids: list[str] = Field(min_length=1, max_length=4)
    validation_status: QueryTriggerValidationStatus

    @model_validator(mode="after")
    def validate_trigger_shape(self) -> "QueryTriggerV1":
        if self.family != self.deterministic_parameters.family:
            raise ValueError("family must match deterministic_parameters.family.")
        if self.expiry_policy.expires_at <= self.created_at:
            raise ValueError("expiry_policy.expires_at must be after created_at.")
        if self.mode != "deterministic":
            raise ValueError("Readiness v2 first slice only supports deterministic query triggers.")
        if self.unlock_action != "ROUTE_STAGE_AB_REANALYSIS":
            raise ValueError(
                "Readiness v2 first slice only supports ROUTE_STAGE_AB_REANALYSIS unlock_action."
            )
        if self.validation_status != "EXECUTABLE":
            raise ValueError("Readiness v2 first slice only supports executable query triggers.")
        claim_lookup = {claim.claim_id: claim for claim in self.operator_claims}
        if set(self.operator_explanation_claim_ids) - set(claim_lookup):
            raise ValueError("operator_explanation_claim_ids must reference operator_claims.")
        if _join_claim_statements(claim_lookup, self.operator_explanation_claim_ids) != self.operator_explanation:
            raise ValueError(
                "operator_explanation must be the ordered join of operator_explanation_claim_ids."
            )
        return self


class ReadinessWatchSourceRefs(StrictModel):
    briefing_id: str
    trigger_ids: list[str] = Field(min_length=1)
    active_trigger_id: str
    preserved_contract_analysis_ref: str | None = None

    @model_validator(mode="after")
    def validate_active_trigger(self) -> "ReadinessWatchSourceRefs":
        if self.active_trigger_id not in self.trigger_ids:
            raise ValueError("active_trigger_id must appear in trigger_ids.")
        return self


class ZNReadinessWatchContextSnapshot(StrictModel):
    evaluation_timestamp: AwareDatetime
    packet_timestamp: AwareDatetime
    packet_age_seconds: int = Field(ge=0)
    freshness_state: FreshnessState
    session_access_state: SessionAccessState
    event_lockout_active: bool
    governance_lockout_active: bool
    event_risk_state: ReadinessEventRiskState
    auction_proximity_state: ReadinessAuctionProximityState
    next_event_name: str | None = None
    next_event_time: AwareDatetime | None = None
    minutes_until_next_event: int | None = Field(default=None, ge=0)
    current_price: float
    directional_lean: DirectionalLean
    value_location_state: PriceLocationState
    macro_release_context: str
    treasury_auction_schedule: str
    active_data_quality_flags: list[str] = Field(default_factory=list)
    lockout_reasons: list[str] = Field(default_factory=list)
    contamination_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_shape(self) -> "ReadinessWatchContextSnapshot":
        if self.next_event_name is None:
            if self.next_event_time is not None or self.minutes_until_next_event is not None:
                raise ValueError(
                    "next_event_time and minutes_until_next_event require next_event_name."
                )
        elif self.next_event_time is None or self.minutes_until_next_event is None:
            raise ValueError(
                "next_event_name requires next_event_time and minutes_until_next_event."
            )
        if self.auction_proximity_state != "NONE":
            if self.next_event_name is None or "auction" not in self.next_event_name.lower():
                raise ValueError(
                    "auction_proximity_state requires an auction next_event_name."
                )
        return self


class ESReadinessWatchContextSnapshot(StrictModel):
    evaluation_timestamp: AwareDatetime
    packet_timestamp: AwareDatetime
    packet_age_seconds: int = Field(ge=0)
    freshness_state: FreshnessState
    session_access_state: SessionAccessState
    event_lockout_active: bool
    governance_lockout_active: bool
    event_risk_state: ReadinessEventRiskState
    next_event_name: str | None = None
    next_event_time: AwareDatetime | None = None
    minutes_until_next_event: int | None = Field(default=None, ge=0)
    current_price: float
    directional_lean: DirectionalLean
    value_location_state: PriceLocationState
    macro_release_context: str
    breadth: str
    index_cash_tone: IndexCashTone
    active_data_quality_flags: list[str] = Field(default_factory=list)
    lockout_reasons: list[str] = Field(default_factory=list)
    contamination_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_shape(self) -> "ESReadinessWatchContextSnapshot":
        if self.next_event_name is None:
            if self.next_event_time is not None or self.minutes_until_next_event is not None:
                raise ValueError(
                    "next_event_time and minutes_until_next_event require next_event_name."
                )
        elif self.next_event_time is None or self.minutes_until_next_event is None:
            raise ValueError(
                "next_event_name requires next_event_time and minutes_until_next_event."
            )
        return self


class NQReadinessWatchContextSnapshot(StrictModel):
    evaluation_timestamp: AwareDatetime
    packet_timestamp: AwareDatetime
    packet_age_seconds: int = Field(ge=0)
    freshness_state: FreshnessState
    session_access_state: SessionAccessState
    event_lockout_active: bool
    governance_lockout_active: bool
    event_risk_state: ReadinessEventRiskState
    next_event_name: str | None = None
    next_event_time: AwareDatetime | None = None
    minutes_until_next_event: int | None = Field(default=None, ge=0)
    current_price: float
    directional_lean: DirectionalLean
    value_location_state: PriceLocationState
    macro_release_context: str
    relative_strength_vs_es: float
    megacap_leadership_posture: str
    bond_yield_context: str
    active_data_quality_flags: list[str] = Field(default_factory=list)
    lockout_reasons: list[str] = Field(default_factory=list)
    contamination_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_shape(self) -> "NQReadinessWatchContextSnapshot":
        if self.next_event_name is None:
            if self.next_event_time is not None or self.minutes_until_next_event is not None:
                raise ValueError(
                    "next_event_time and minutes_until_next_event require next_event_name."
                )
        elif self.next_event_time is None or self.minutes_until_next_event is None:
            raise ValueError(
                "next_event_name requires next_event_time and minutes_until_next_event."
            )
        return self


class CLReadinessWatchContextSnapshot(StrictModel):
    evaluation_timestamp: AwareDatetime
    packet_timestamp: AwareDatetime
    packet_age_seconds: int = Field(ge=0)
    freshness_state: FreshnessState
    session_access_state: SessionAccessState
    event_lockout_active: bool
    governance_lockout_active: bool
    event_risk_state: ReadinessEventRiskState
    next_event_name: str | None = None
    next_event_time: AwareDatetime | None = None
    minutes_until_next_event: int | None = Field(default=None, ge=0)
    current_price: float
    directional_lean: DirectionalLean
    value_location_state: PriceLocationState
    eia_timing_context: str
    realized_volatility_context: RealizedVolatilityContext
    liquidity_sweep_summary: str
    dom_liquidity_summary: str
    cross_market_context: str
    active_data_quality_flags: list[str] = Field(default_factory=list)
    lockout_reasons: list[str] = Field(default_factory=list)
    contamination_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_shape(self) -> "CLReadinessWatchContextSnapshot":
        if self.next_event_name is None:
            if self.next_event_time is not None or self.minutes_until_next_event is not None:
                raise ValueError(
                    "next_event_time and minutes_until_next_event require next_event_name."
                )
        elif self.next_event_time is None or self.minutes_until_next_event is None:
            raise ValueError(
                "next_event_name requires next_event_time and minutes_until_next_event."
            )
        return self


class MGCReadinessWatchContextSnapshot(StrictModel):
    evaluation_timestamp: AwareDatetime
    packet_timestamp: AwareDatetime
    packet_age_seconds: int = Field(ge=0)
    freshness_state: FreshnessState
    session_access_state: SessionAccessState
    event_lockout_active: bool
    governance_lockout_active: bool
    event_risk_state: ReadinessEventRiskState
    next_event_name: str | None = None
    next_event_time: AwareDatetime | None = None
    minutes_until_next_event: int | None = Field(default=None, ge=0)
    current_price: float
    directional_lean: DirectionalLean
    value_location_state: PriceLocationState
    dxy_context: DxyContext
    yield_context: YieldContext
    macro_fear_catalyst_summary: str
    swing_penetration_volume_summary: str
    cross_market_context: str
    active_data_quality_flags: list[str] = Field(default_factory=list)
    lockout_reasons: list[str] = Field(default_factory=list)
    contamination_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_shape(self) -> "MGCReadinessWatchContextSnapshot":
        if self.next_event_name is None:
            if self.next_event_time is not None or self.minutes_until_next_event is not None:
                raise ValueError(
                    "next_event_time and minutes_until_next_event require next_event_name."
                )
        elif self.next_event_time is None or self.minutes_until_next_event is None:
            raise ValueError(
                "next_event_name requires next_event_time and minutes_until_next_event."
            )
        return self


class SixEReadinessWatchContextSnapshot(StrictModel):
    evaluation_timestamp: AwareDatetime
    packet_timestamp: AwareDatetime
    packet_age_seconds: int = Field(ge=0)
    freshness_state: FreshnessState
    session_access_state: SessionAccessState
    event_lockout_active: bool
    governance_lockout_active: bool
    event_risk_state: ReadinessEventRiskState
    next_event_name: str | None = None
    next_event_time: AwareDatetime | None = None
    minutes_until_next_event: int | None = Field(default=None, ge=0)
    current_price: float
    directional_lean: DirectionalLean
    value_location_state: PriceLocationState
    asia_high_low: PriceRange
    london_high_low: PriceRange
    ny_high_low_so_far: PriceRange
    dxy_context: DxyContext
    europe_initiative_status: str
    cross_market_context: str
    active_data_quality_flags: list[str] = Field(default_factory=list)
    lockout_reasons: list[str] = Field(default_factory=list)
    contamination_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_shape(self) -> "SixEReadinessWatchContextSnapshot":
        if self.next_event_name is None:
            if self.next_event_time is not None or self.minutes_until_next_event is not None:
                raise ValueError(
                    "next_event_time and minutes_until_next_event require next_event_name."
                )
        elif self.next_event_time is None or self.minutes_until_next_event is None:
            raise ValueError(
                "next_event_name requires next_event_time and minutes_until_next_event."
            )
        return self


ReadinessWatchContextSnapshot = (
    ZNReadinessWatchContextSnapshot
    | ESReadinessWatchContextSnapshot
    | NQReadinessWatchContextSnapshot
    | CLReadinessWatchContextSnapshot
    | MGCReadinessWatchContextSnapshot
    | SixEReadinessWatchContextSnapshot
)


class ReadinessWatchObservation(StrictModel):
    observed_at: AwareDatetime
    trigger_truth_state: ReadinessTriggerTruthState
    context_change: ReadinessV2WatchState
    note: str


class ReadinessWatchDetectedChange(StrictModel):
    kind: ReadinessWatchDetectedChangeKind
    from_value: str
    to_value: str
    detail: str


class ReadinessWatchHistoryEntry(StrictModel):
    revision: int = Field(ge=1)
    prior_watch_id: str | None = None
    prior_revision: int | None = Field(default=None, ge=1)
    evaluated_at: AwareDatetime
    packet_timestamp: AwareDatetime
    state: ReadinessV2WatchState
    routing_recommendation: ReadinessRoutingRecommendation
    trigger_truth_state: ReadinessTriggerTruthState
    transition_reason: ReadinessWatchTransitionReason
    detected_change_kinds: list[ReadinessWatchDetectedChangeKind] = Field(default_factory=list)
    change_summary: str
    terminal_reason: str | None = None

    @model_validator(mode="after")
    def validate_history_entry(self) -> "ReadinessWatchHistoryEntry":
        if self.revision == 1:
            if self.prior_watch_id is not None or self.prior_revision is not None:
                raise ValueError(
                    "revision 1 history entries must not include prior_watch_id or prior_revision."
                )
        else:
            if self.prior_watch_id is None or self.prior_revision != self.revision - 1:
                raise ValueError(
                    "history entries after revision 1 require prior_watch_id and prior_revision = revision - 1."
                )
        if self.packet_timestamp > self.evaluated_at:
            raise ValueError("history packet_timestamp must be at or before evaluated_at.")
        if self.change_summary != _expected_history_change_summary(
            transition_reason=self.transition_reason,
            state=self.state,
            routing_recommendation=self.routing_recommendation,
        ):
            raise ValueError(
                "change_summary must match the deterministic summary for transition_reason/state/routing_recommendation."
            )
        if self.transition_reason == "initialized" and self.revision != 1:
            raise ValueError("initialized transition_reason is only valid for revision 1.")
        if self.transition_reason == "no_material_change" and self.detected_change_kinds:
            raise ValueError("no_material_change history entries must not include detected_change_kinds.")
        if self.transition_reason == "trigger_requery_ready":
            if self.state != "READY_FOR_REANALYSIS" or self.routing_recommendation != "REQUERY_STAGE_B":
                raise ValueError(
                    "trigger_requery_ready requires READY_FOR_REANALYSIS with REQUERY_STAGE_B."
                )
            if "routing_recommendation_change" not in self.detected_change_kinds:
                raise ValueError(
                    "trigger_requery_ready history entries must include routing_recommendation_change."
                )
        if self.transition_reason == "context_contaminated" and self.state != "CONTEXT_CONTAMINATED":
            raise ValueError("context_contaminated transition_reason requires CONTEXT_CONTAMINATED state.")
        if self.transition_reason == "lockout_applied" and self.state != "LOCKED_OUT":
            raise ValueError("lockout_applied transition_reason requires LOCKED_OUT state.")
        if self.transition_reason == "thesis_invalidated":
            if self.state != "THESIS_INVALIDATED" or self.routing_recommendation != "EXPIRE_WATCH":
                raise ValueError(
                    "thesis_invalidated requires THESIS_INVALIDATED with EXPIRE_WATCH."
                )
            if "thesis_invalidation" not in self.detected_change_kinds:
                raise ValueError(
                    "thesis_invalidated history entries must include thesis_invalidation."
                )
        if self.transition_reason == "watch_expired":
            if self.state != "TERMINAL_EXPIRED" or self.routing_recommendation != "EXPIRE_WATCH":
                raise ValueError("watch_expired requires TERMINAL_EXPIRED with EXPIRE_WATCH.")
        terminal_states = {"THESIS_INVALIDATED", "TERMINAL_EXPIRED"}
        if self.state in terminal_states and self.terminal_reason is None:
            raise ValueError("terminal_reason is required in history for terminal watch states.")
        if self.state not in terminal_states and self.terminal_reason is not None:
            raise ValueError("terminal_reason in history is only valid for terminal watch states.")
        return self


class ReadinessWatchV1(StrictModel):
    schema_name: Literal["readiness_watch_v1"] = Field(
        default="readiness_watch_v1",
        alias="$schema",
    )
    watch_id: str
    contract: ReadinessV2Contract = "ZN"
    revision: int = Field(ge=1)
    prior_watch_id: str | None = None
    prior_revision: int | None = Field(default=None, ge=1)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    source_kind: ReadinessSourceKind
    source_refs: ReadinessWatchSourceRefs
    state: ReadinessV2WatchState
    active_trigger_family: ReadinessTriggerFamily
    trigger_payload: QueryTriggerDeterministicParameters
    post_trigger_policy: QueryTriggerPostTriggerPolicy
    context_snapshot: ReadinessWatchContextSnapshot
    routing_target: ReadinessRoutingTarget
    routing_recommendation: ReadinessRoutingRecommendation
    invalidation_rules: list[ReadinessInvalidationRule] = Field(
        min_length=1,
        max_length=6,
    )
    expiry_policy: ExpiryPolicy
    last_evaluated_at: AwareDatetime
    last_observation: ReadinessWatchObservation
    detected_changes: list[ReadinessWatchDetectedChange] = Field(default_factory=list)
    terminal_reason: str | None = None
    allowed_next_actions: list[ReadinessV2WatchNextAction] = Field(min_length=1)
    operator_summary: str
    operator_claims: list[NarrativeClaim] = Field(min_length=1, max_length=4)
    operator_summary_claim_ids: list[str] = Field(min_length=1, max_length=4)
    history: list[ReadinessWatchHistoryEntry] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_watch_shape(self) -> "ReadinessWatchV1":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be at or after created_at.")
        if self.last_evaluated_at < self.created_at:
            raise ValueError("last_evaluated_at must be at or after created_at.")
        if self.expiry_policy.expires_at <= self.created_at:
            raise ValueError("expiry_policy.expires_at must be after created_at.")
        if self.active_trigger_family != self.trigger_payload.family:
            raise ValueError("active_trigger_family must match trigger_payload.family.")
        if self.source_kind != "premarket_briefing":
            raise ValueError("Readiness v2 first slice only supports source_kind = premarket_briefing.")
        if self.source_refs.preserved_contract_analysis_ref is not None:
            raise ValueError(
                "Readiness v2 first slice must not include preserved_contract_analysis_ref."
            )
        if self.state == "READY_FOR_SETUP_REENTRY":
            raise ValueError("Readiness v2 first slice does not support READY_FOR_SETUP_REENTRY.")
        if self.routing_target == "STAGE_C_REENTRY":
            raise ValueError("Readiness v2 first slice does not support STAGE_C_REENTRY routing.")
        if self.routing_target == "STAGE_AB_REANALYSIS" and self.state != "READY_FOR_REANALYSIS":
            raise ValueError(
                "STAGE_AB_REANALYSIS routing_target is only valid in READY_FOR_REANALYSIS."
            )
        if self.routing_recommendation == "REQUERY_STAGE_B":
            if self.state != "READY_FOR_REANALYSIS" or self.routing_target != "STAGE_AB_REANALYSIS":
                raise ValueError(
                    "REQUERY_STAGE_B requires READY_FOR_REANALYSIS with STAGE_AB_REANALYSIS routing_target."
                )
        elif self.routing_recommendation == "EXPIRE_WATCH":
            if self.state not in {"THESIS_INVALIDATED", "TERMINAL_EXPIRED"}:
                raise ValueError(
                    "EXPIRE_WATCH is only valid for THESIS_INVALIDATED or TERMINAL_EXPIRED."
                )
            if self.routing_target != "NONE":
                raise ValueError("EXPIRE_WATCH requires routing_target = NONE.")
        elif self.state == "READY_FOR_REANALYSIS":
            raise ValueError("READY_FOR_REANALYSIS requires routing_recommendation = REQUERY_STAGE_B.")
        if self.context_snapshot.packet_timestamp > self.context_snapshot.evaluation_timestamp:
            raise ValueError(
                "context_snapshot.packet_timestamp must be at or before evaluation_timestamp."
            )
        if self.updated_at != self.context_snapshot.evaluation_timestamp:
            raise ValueError(
                "updated_at must match context_snapshot.evaluation_timestamp for deterministic watch snapshots."
            )
        if self.last_evaluated_at != self.context_snapshot.evaluation_timestamp:
            raise ValueError(
                "last_evaluated_at must match context_snapshot.evaluation_timestamp."
            )
        if self.last_observation.observed_at != self.updated_at:
            raise ValueError("last_observation.observed_at must match updated_at.")
        if self.last_observation.context_change != self.state:
            raise ValueError("last_observation.context_change must match the current watch state.")
        terminal_states = {"THESIS_INVALIDATED", "TERMINAL_EXPIRED"}
        if self.revision == 1:
            if self.prior_watch_id is not None or self.prior_revision is not None:
                raise ValueError(
                    "revision 1 watches must not include prior_watch_id or prior_revision."
                )
        else:
            if self.prior_watch_id != self.watch_id or self.prior_revision != self.revision - 1:
                raise ValueError(
                    "updated watches require prior_watch_id = watch_id and prior_revision = revision - 1."
                )
        if self.state in terminal_states and self.terminal_reason is None:
            raise ValueError("terminal_reason is required for terminal watch states.")
        if self.state not in terminal_states and self.terminal_reason is not None:
            raise ValueError(
                "terminal_reason must only be populated for terminal watch states."
            )
        claim_lookup = {claim.claim_id: claim for claim in self.operator_claims}
        if set(self.operator_summary_claim_ids) - set(claim_lookup):
            raise ValueError("operator_summary_claim_ids must reference operator_claims.")
        if _join_claim_statements(claim_lookup, self.operator_summary_claim_ids) != self.operator_summary:
            raise ValueError(
                "operator_summary must be the ordered join of operator_summary_claim_ids."
            )
        if len(self.history) != self.revision:
            raise ValueError("history length must match revision.")
        for index, entry in enumerate(self.history, start=1):
            if entry.revision != index:
                raise ValueError("history revisions must be contiguous and start at 1.")
            if index > 1:
                previous = self.history[index - 2]
                if entry.prior_watch_id != self.watch_id or entry.prior_revision != previous.revision:
                    raise ValueError(
                        "history entries after revision 1 must link back to the same watch_id and prior revision."
                    )
                if entry.evaluated_at < previous.evaluated_at:
                    raise ValueError("history evaluated_at values must be monotonic.")
                if entry.packet_timestamp < previous.packet_timestamp:
                    raise ValueError("history packet_timestamp values must be monotonic.")
        current_entry = self.history[-1]
        if current_entry.evaluated_at != self.updated_at:
            raise ValueError("latest history entry evaluated_at must match updated_at.")
        if current_entry.packet_timestamp != self.context_snapshot.packet_timestamp:
            raise ValueError("latest history entry packet_timestamp must match context_snapshot.packet_timestamp.")
        if current_entry.state != self.state:
            raise ValueError("latest history entry state must match current watch state.")
        if current_entry.routing_recommendation != self.routing_recommendation:
            raise ValueError(
                "latest history entry routing_recommendation must match current watch routing_recommendation."
            )
        if current_entry.trigger_truth_state != self.last_observation.trigger_truth_state:
            raise ValueError(
                "latest history entry trigger_truth_state must match last_observation.trigger_truth_state."
            )
        if current_entry.detected_change_kinds != [change.kind for change in self.detected_changes]:
            raise ValueError(
                "latest history entry detected_change_kinds must match detected_changes order."
            )
        if current_entry.terminal_reason != self.terminal_reason:
            raise ValueError("latest history entry terminal_reason must match watch terminal_reason.")
        return self


class ReadinessV2BootstrapArtifact(StrictModel):
    schema_name: Literal["readiness_v2_bootstrap_artifact_v1"] = Field(
        default="readiness_v2_bootstrap_artifact_v1",
        alias="$schema",
    )
    mode: Literal["bootstrap"] = "bootstrap"
    contract: ReadinessV2Contract = "ZN"
    evaluation_timestamp: AwareDatetime
    briefing: PremarketBriefingV1
    query_triggers: list[QueryTriggerV1] = Field(min_length=1)
    watch: ReadinessWatchV1

    @model_validator(mode="after")
    def validate_alignment(self) -> "ReadinessV2BootstrapArtifact":
        if self.briefing.contract != self.contract or self.watch.contract != self.contract:
            raise ValueError("Bootstrap artifact contract fields must align.")
        if any(trigger.contract != self.contract for trigger in self.query_triggers):
            raise ValueError("All bootstrap query_triggers must match artifact contract.")
        if self.briefing.created_at != self.evaluation_timestamp:
            raise ValueError("Bootstrap briefing.created_at must match evaluation_timestamp.")
        if any(
            trigger.source_briefing_id != self.briefing.briefing_id
            for trigger in self.query_triggers
        ):
            raise ValueError(
                "All bootstrap query_triggers must originate from briefing.briefing_id."
            )
        if any(trigger.created_at != self.evaluation_timestamp for trigger in self.query_triggers):
            raise ValueError(
                "All bootstrap query_triggers.created_at must match evaluation_timestamp."
            )
        if self.watch.created_at != self.evaluation_timestamp:
            raise ValueError("Bootstrap watch.created_at must match evaluation_timestamp.")
        if self.watch.source_refs.briefing_id != self.briefing.briefing_id:
            raise ValueError("Bootstrap watch.source_refs.briefing_id must match briefing.briefing_id.")
        trigger_ids = [trigger.trigger_id for trigger in self.query_triggers]
        if self.watch.source_refs.trigger_ids != trigger_ids:
            raise ValueError("Bootstrap watch.source_refs.trigger_ids must match query_triggers order.")
        return self


class ReadinessV2UpdateArtifact(StrictModel):
    schema_name: Literal["readiness_v2_watch_update_artifact_v1"] = Field(
        default="readiness_v2_watch_update_artifact_v1",
        alias="$schema",
    )
    mode: Literal["update"] = "update"
    contract: ReadinessV2Contract = "ZN"
    evaluation_timestamp: AwareDatetime
    prior_watch_id: str
    watch: ReadinessWatchV1

    @model_validator(mode="after")
    def validate_alignment(self) -> "ReadinessV2UpdateArtifact":
        if self.watch.contract != self.contract:
            raise ValueError("Update artifact contract fields must align.")
        if self.watch.watch_id != self.prior_watch_id:
            raise ValueError("Update artifact prior_watch_id must match watch.watch_id.")
        if self.watch.updated_at != self.evaluation_timestamp:
            raise ValueError("Update artifact watch.updated_at must match evaluation_timestamp.")
        return self


class ReadinessV2ReplayBootstrapSummary(StrictModel):
    briefing_id: str
    watch_id: str
    evaluation_timestamp: AwareDatetime
    initial_revision: int = Field(ge=1)
    initial_state: ReadinessV2WatchState
    initial_routing_recommendation: ReadinessRoutingRecommendation
    active_trigger_family: ReadinessTriggerFamily


class ReadinessV2ReplayStep(StrictModel):
    step_index: int = Field(ge=0)
    phase: ReadinessV2ReplayPhase
    revision: int = Field(ge=1)
    evaluation_timestamp: AwareDatetime
    packet_timestamp: AwareDatetime
    state: ReadinessV2WatchState
    routing_recommendation: ReadinessRoutingRecommendation
    trigger_truth_state: ReadinessTriggerTruthState
    transition_reason: ReadinessWatchTransitionReason
    change_summary: str
    detected_change_kinds: list[ReadinessWatchDetectedChangeKind] = Field(default_factory=list)
    terminal_reason: str | None = None

    @model_validator(mode="after")
    def validate_step_shape(self) -> "ReadinessV2ReplayStep":
        if self.step_index == 0 and self.phase != "bootstrap":
            raise ValueError("Replay step 0 must be bootstrap.")
        if self.step_index > 0 and self.phase != "update":
            raise ValueError("Replay steps after index 0 must be update.")
        if self.revision != self.step_index + 1:
            raise ValueError("Replay step revision must equal step_index + 1.")
        if self.packet_timestamp > self.evaluation_timestamp:
            raise ValueError("Replay packet_timestamp must be at or before evaluation_timestamp.")
        if self.change_summary != _expected_history_change_summary(
            transition_reason=self.transition_reason,
            state=self.state,
            routing_recommendation=self.routing_recommendation,
        ):
            raise ValueError(
                "Replay change_summary must match the deterministic summary for transition_reason/state/routing_recommendation."
            )
        return self


class ReadinessV2ReplayInvariants(StrictModel):
    watch_id_stable: bool
    revisions_contiguous: bool
    evaluation_timestamps_monotonic: bool
    packet_timestamps_monotonic: bool


class ReadinessV2ReplayArtifact(StrictModel):
    schema_name: Literal["readiness_v2_replay_artifact_v1"] = Field(
        default="readiness_v2_replay_artifact_v1",
        alias="$schema",
    )
    mode: Literal["replay"] = "replay"
    contract: ReadinessV2Contract = "ZN"
    bootstrap: ReadinessV2ReplayBootstrapSummary
    steps: list[ReadinessV2ReplayStep] = Field(min_length=1, max_length=64)
    final_watch: ReadinessWatchV1
    validation_status: ReadinessV2ReplayValidationStatus = "VALID"
    invariants: ReadinessV2ReplayInvariants
    terminal_outcome_state: ReadinessV2WatchState | None = None
    terminal_outcome_reason: str | None = None

    @model_validator(mode="after")
    def validate_replay_shape(self) -> "ReadinessV2ReplayArtifact":
        if self.final_watch.contract != self.contract:
            raise ValueError("Replay artifact contract must match final_watch.contract.")
        if self.bootstrap.watch_id != self.final_watch.watch_id:
            raise ValueError("Replay bootstrap.watch_id must match final_watch.watch_id.")
        if self.bootstrap.briefing_id != self.final_watch.source_refs.briefing_id:
            raise ValueError(
                "Replay bootstrap.briefing_id must match final_watch.source_refs.briefing_id."
            )
        if self.bootstrap.initial_revision != 1:
            raise ValueError("Replay bootstrap initial_revision must be 1.")
        if len(self.steps) != self.final_watch.revision:
            raise ValueError("Replay steps length must match final_watch.revision.")
        if self.steps[0].evaluation_timestamp != self.bootstrap.evaluation_timestamp:
            raise ValueError("Replay step 0 must align with bootstrap.evaluation_timestamp.")
        if self.steps[0].state != self.bootstrap.initial_state:
            raise ValueError("Replay step 0 state must align with bootstrap.initial_state.")
        if (
            self.steps[0].routing_recommendation
            != self.bootstrap.initial_routing_recommendation
        ):
            raise ValueError(
                "Replay step 0 routing_recommendation must align with bootstrap.initial_routing_recommendation."
            )
        if self.bootstrap.active_trigger_family != self.final_watch.active_trigger_family:
            raise ValueError(
                "Replay bootstrap.active_trigger_family must match final_watch.active_trigger_family."
            )
        for expected_revision, step in enumerate(self.steps, start=1):
            if step.revision != expected_revision:
                raise ValueError("Replay steps must have contiguous revisions starting at 1.")
        if self.steps[-1].state != self.final_watch.state:
            raise ValueError("Replay final step state must match final_watch.state.")
        if self.steps[-1].routing_recommendation != self.final_watch.routing_recommendation:
            raise ValueError(
                "Replay final step routing_recommendation must match final_watch.routing_recommendation."
            )
        if self.steps[-1].terminal_reason != self.final_watch.terminal_reason:
            raise ValueError("Replay final step terminal_reason must match final_watch.terminal_reason.")
        if not all(
            [
                self.invariants.watch_id_stable,
                self.invariants.revisions_contiguous,
                self.invariants.evaluation_timestamps_monotonic,
                self.invariants.packet_timestamps_monotonic,
            ]
        ):
            raise ValueError("Replay invariants must all be true for a VALID artifact.")
        terminal_states = {"THESIS_INVALIDATED", "TERMINAL_EXPIRED"}
        if self.terminal_outcome_state is None:
            if self.final_watch.state in terminal_states:
                raise ValueError("terminal_outcome_state is required when final_watch is terminal.")
        else:
            if self.terminal_outcome_state != self.final_watch.state:
                raise ValueError("terminal_outcome_state must match final_watch.state.")
            if self.terminal_outcome_state not in terminal_states:
                raise ValueError("terminal_outcome_state is only valid for terminal watch states.")
            if self.terminal_outcome_reason != self.final_watch.terminal_reason:
                raise ValueError("terminal_outcome_reason must match final_watch.terminal_reason.")
        return self


def _join_claim_statements(
    claim_lookup: dict[str, NarrativeClaim],
    claim_ids: list[str],
) -> str:
    return " ".join(claim_lookup[claim_id].statement for claim_id in claim_ids)


def _expected_history_change_summary(
    *,
    transition_reason: ReadinessWatchTransitionReason,
    state: ReadinessV2WatchState,
    routing_recommendation: ReadinessRoutingRecommendation,
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
