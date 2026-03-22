from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from ..schemas.contracts import ESContractMetadata
from ..schemas.packet import HistoricalPacket
from ..validation import validate_historical_packet
from .models import ESHistoricalDataInput, ESManualOverlayInput, HistoricalBar

ES_CANONICAL_CONTRACT_METADATA = ESContractMetadata.model_validate(
    {
        "$schema": "contract_metadata_v1",
        "contract": "ES",
        "tick_size": 0.25,
        "dollar_per_tick": 12.5,
        "point_value": 50.0,
        "max_position_size": 2,
        "slippage_ticks": 1,
        "allowed_hours_start_et": "09:30",
        "allowed_hours_end_et": "15:45",
    }
)
INITIAL_BALANCE_WINDOW_MINUTES = 60
MIN_INITIAL_BALANCE_OBSERVED_SPAN_MINUTES = 30


@dataclass(frozen=True)
class CompiledPacketArtifact:
    packet: HistoricalPacket
    provenance: dict[str, Any]


def _coerce_historical_input(
    payload: ESHistoricalDataInput | Mapping[str, Any],
) -> ESHistoricalDataInput:
    if isinstance(payload, ESHistoricalDataInput):
        return payload
    return ESHistoricalDataInput.model_validate(dict(payload))


def _coerce_overlay_input(payload: ESManualOverlayInput | Mapping[str, Any]) -> ESManualOverlayInput:
    if isinstance(payload, ESManualOverlayInput):
        return payload
    return ESManualOverlayInput.model_validate(dict(payload))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _first_open(bars: list[HistoricalBar]) -> float:
    return bars[0].open


def _last_close(bars: list[HistoricalBar]) -> float:
    return bars[-1].close


def _last_timestamp(bars: list[HistoricalBar]) -> datetime:
    return bars[-1].timestamp


def _max_high(bars: list[HistoricalBar]) -> float:
    return max(bar.high for bar in bars)


def _min_low(bars: list[HistoricalBar]) -> float:
    return min(bar.low for bar in bars)


def _session_range(bars: list[HistoricalBar]) -> float:
    return _max_high(bars) - _min_low(bars)


def _vwap(bars: list[HistoricalBar]) -> float:
    total_volume = sum(bar.volume for bar in bars)
    total_value = sum((((bar.high + bar.low + bar.close) / 3.0) * bar.volume) for bar in bars)
    return round(total_value / total_volume, 4)


def _initial_balance_bars(bars: list[HistoricalBar]) -> list[HistoricalBar]:
    window_start = bars[0].timestamp
    window_end = window_start + timedelta(minutes=INITIAL_BALANCE_WINDOW_MINUTES)
    ib_bars = [bar for bar in bars if window_start <= bar.timestamp < window_end]
    if len(ib_bars) < 2:
        raise ValueError(
            "Current RTH bars must contain at least two bars inside the first 60 minutes "
            "to derive initial balance."
        )
    observed_span = ib_bars[-1].timestamp - ib_bars[0].timestamp
    if observed_span < timedelta(minutes=MIN_INITIAL_BALANCE_OBSERVED_SPAN_MINUTES):
        raise ValueError(
            "Current RTH bars must span at least 30 minutes inside the first 60 minutes "
            "to derive initial balance."
        )
    return ib_bars


def _overlay_provenance(
    overlay: ESManualOverlayInput,
    field_name: str,
    *,
    default_source: str = "manual_overlay",
    assist_derivation: str | None = None,
) -> dict[str, str]:
    if field_name in overlay.model_fields_set:
        return {"source": default_source, "field": field_name}
    provenance = {"source": "overlay_assist", "field": field_name}
    if assist_derivation is not None:
        provenance["derivation"] = assist_derivation
    return provenance


def _build_field_provenance(overlay: ESManualOverlayInput) -> dict[str, dict[str, str]]:
    return {
        "challenge_state": {"source": "manual_overlay", "field": "challenge_state"},
        "attached_visuals": _overlay_provenance(
            overlay,
            "attached_visuals",
            assist_derivation="default all visuals to false when omitted",
        ),
        "contract_metadata": {
            "source": "compiler_constant",
            "field": "ES_CANONICAL_CONTRACT_METADATA",
        },
        "market_packet.timestamp": {
            "source": "historical_bars",
            "field": "current_rth_bars",
            "derivation": "last(timestamp)",
        },
        "market_packet.contract": {"source": "compiler_constant", "field": "ES"},
        "market_packet.session_type": {"source": "compiler_constant", "field": "RTH"},
        "market_packet.current_price": {
            "source": "historical_bars",
            "field": "current_rth_bars",
            "derivation": "last(close)",
        },
        "market_packet.session_open": {
            "source": "historical_bars",
            "field": "current_rth_bars",
            "derivation": "first(open)",
        },
        "market_packet.prior_day_high": {
            "source": "historical_bars",
            "field": "prior_rth_bars",
            "derivation": "max(high)",
        },
        "market_packet.prior_day_low": {
            "source": "historical_bars",
            "field": "prior_rth_bars",
            "derivation": "min(low)",
        },
        "market_packet.prior_day_close": {
            "source": "historical_bars",
            "field": "prior_rth_bars",
            "derivation": "last(close)",
        },
        "market_packet.overnight_high": {
            "source": "historical_bars",
            "field": "overnight_bars",
            "derivation": "max(high)",
        },
        "market_packet.overnight_low": {
            "source": "historical_bars",
            "field": "overnight_bars",
            "derivation": "min(low)",
        },
        "market_packet.current_session_vah": _overlay_provenance(overlay, "current_session_vah"),
        "market_packet.current_session_val": _overlay_provenance(overlay, "current_session_val"),
        "market_packet.current_session_poc": _overlay_provenance(overlay, "current_session_poc"),
        "market_packet.previous_session_vah": _overlay_provenance(overlay, "previous_session_vah"),
        "market_packet.previous_session_val": _overlay_provenance(overlay, "previous_session_val"),
        "market_packet.previous_session_poc": _overlay_provenance(overlay, "previous_session_poc"),
        "market_packet.vwap": {
            "source": "historical_bars",
            "field": "current_rth_bars",
            "derivation": "volume_weighted_typical_price",
        },
        "market_packet.session_range": {
            "source": "historical_bars",
            "field": "current_rth_bars",
            "derivation": "max(high)-min(low)",
        },
        "market_packet.avg_20d_session_range": _overlay_provenance(
            overlay, "avg_20d_session_range"
        ),
        "market_packet.cumulative_delta": _overlay_provenance(overlay, "cumulative_delta"),
        "market_packet.current_volume_vs_average": _overlay_provenance(
            overlay, "current_volume_vs_average"
        ),
        "market_packet.opening_type": _overlay_provenance(overlay, "opening_type"),
        "market_packet.major_higher_timeframe_levels": _overlay_provenance(
            overlay,
            "major_higher_timeframe_levels",
            assist_derivation="default to null when omitted",
        ),
        "market_packet.key_hvns": _overlay_provenance(
            overlay,
            "key_hvns",
            assist_derivation="default to null when omitted",
        ),
        "market_packet.key_lvns": _overlay_provenance(
            overlay,
            "key_lvns",
            assist_derivation="default to null when omitted",
        ),
        "market_packet.singles_excess_poor_high_low_notes": _overlay_provenance(
            overlay,
            "singles_excess_poor_high_low_notes",
            assist_derivation="default to null when omitted",
        ),
        "market_packet.event_calendar_remainder": _overlay_provenance(
            overlay, "event_calendar_remainder"
        ),
        "market_packet.cross_market_context": _overlay_provenance(
            overlay,
            "cross_market_context",
            assist_derivation="default to null when omitted",
        ),
        "market_packet.data_quality_flags": _overlay_provenance(
            overlay,
            "data_quality_flags",
            assist_derivation="default to [] when omitted",
        ),
        "contract_specific_extension.contract": {"source": "compiler_constant", "field": "ES"},
        "contract_specific_extension.breadth": _overlay_provenance(overlay, "breadth"),
        "contract_specific_extension.index_cash_tone": _overlay_provenance(
            overlay, "index_cash_tone"
        ),
    }


def compile_es_packet(
    historical_input: ESHistoricalDataInput | Mapping[str, Any],
    overlay: ESManualOverlayInput | Mapping[str, Any],
    *,
    compiled_at_iso: str | None = None,
) -> CompiledPacketArtifact:
    historical = _coerce_historical_input(historical_input)
    manual_overlay = _coerce_overlay_input(overlay)
    ib_bars = _initial_balance_bars(historical.current_rth_bars)

    packet_payload = {
        "$schema": "historical_packet_v1",
        "challenge_state": manual_overlay.challenge_state.model_dump(by_alias=True, mode="json"),
        "contract_metadata": ES_CANONICAL_CONTRACT_METADATA.model_dump(by_alias=True, mode="json"),
        "market_packet": {
            "$schema": "market_packet_v1",
            "timestamp": _last_timestamp(historical.current_rth_bars),
            "contract": "ES",
            "session_type": "RTH",
            "current_price": _last_close(historical.current_rth_bars),
            "session_open": _first_open(historical.current_rth_bars),
            "prior_day_high": _max_high(historical.prior_rth_bars),
            "prior_day_low": _min_low(historical.prior_rth_bars),
            "prior_day_close": _last_close(historical.prior_rth_bars),
            "overnight_high": _max_high(historical.overnight_bars),
            "overnight_low": _min_low(historical.overnight_bars),
            "current_session_vah": manual_overlay.current_session_vah,
            "current_session_val": manual_overlay.current_session_val,
            "current_session_poc": manual_overlay.current_session_poc,
            "previous_session_vah": manual_overlay.previous_session_vah,
            "previous_session_val": manual_overlay.previous_session_val,
            "previous_session_poc": manual_overlay.previous_session_poc,
            "vwap": _vwap(historical.current_rth_bars),
            "session_range": _session_range(historical.current_rth_bars),
            "avg_20d_session_range": manual_overlay.avg_20d_session_range,
            "cumulative_delta": manual_overlay.cumulative_delta,
            "current_volume_vs_average": manual_overlay.current_volume_vs_average,
            "opening_type": manual_overlay.opening_type,
            "major_higher_timeframe_levels": manual_overlay.major_higher_timeframe_levels,
            "key_hvns": manual_overlay.key_hvns,
            "key_lvns": manual_overlay.key_lvns,
            "singles_excess_poor_high_low_notes": manual_overlay.singles_excess_poor_high_low_notes,
            "event_calendar_remainder": [
                event.model_dump(by_alias=True, mode="json")
                for event in manual_overlay.event_calendar_remainder
            ],
            "cross_market_context": manual_overlay.cross_market_context,
            "data_quality_flags": manual_overlay.data_quality_flags,
        },
        "contract_specific_extension": {
            "$schema": "contract_specific_extension_v1",
            "contract": "ES",
            "breadth": manual_overlay.breadth,
            "index_cash_tone": manual_overlay.index_cash_tone,
        },
        "attached_visuals": manual_overlay.attached_visuals.model_dump(by_alias=True, mode="json"),
    }
    packet = validate_historical_packet(packet_payload)
    provenance = {
        "compiler_schema": "packet_compiler_provenance_v1",
        "contract": "ES",
        "compiled_at": compiled_at_iso or _utc_now_iso(),
        "packet_schema": "historical_packet_v1",
        "field_provenance": _build_field_provenance(manual_overlay),
        "derived_features": {
            "ib_high": {
                "value": _max_high(ib_bars),
                "source": "historical_bars",
                "field": "current_rth_bars",
                "derivation": (
                    "max(high) across current_rth_bars where "
                    "first_timestamp <= timestamp < first_timestamp + 60 minutes"
                ),
            },
            "ib_low": {
                "value": _min_low(ib_bars),
                "source": "historical_bars",
                "field": "current_rth_bars",
                "derivation": (
                    "min(low) across current_rth_bars where "
                    "first_timestamp <= timestamp < first_timestamp + 60 minutes"
                ),
            },
            "ib_range": {
                "value": _session_range(ib_bars),
                "source": "historical_bars",
                "field": "current_rth_bars",
                "derivation": "ib_high-ib_low from the first 60 minutes window",
            },
            "weekly_open": {
                "value": historical.weekly_open_bar.open,
                "source": "historical_bars",
                "field": "weekly_open_bar",
                "derivation": "open",
            },
        },
    }
    return CompiledPacketArtifact(packet=packet, provenance=provenance)


def write_compiled_packet(
    artifact: CompiledPacketArtifact,
    *,
    output_path: Path,
    provenance_output_path: Path | None = None,
) -> tuple[Path, Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_provenance_path = provenance_output_path or output_path.with_suffix(".provenance.json")
    resolved_provenance_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        artifact.packet.model_dump_json(by_alias=True, indent=2),
    )
    resolved_provenance_path.write_text(
        json.dumps(artifact.provenance, indent=2, sort_keys=True)
    )
    return output_path, resolved_provenance_path
