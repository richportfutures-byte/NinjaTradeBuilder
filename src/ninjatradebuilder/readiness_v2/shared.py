from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ..schemas.packet import HistoricalPacket
from ..schemas.readiness_v2 import (
    ReadinessV2ReplayInvariants,
    ReadinessV2ReplayPhase,
    ReadinessV2ReplayStep,
    ReadinessWatchDetectedChange,
    ReadinessWatchV1,
)


def coerce_replay_update(
    update: Mapping[str, Any],
    *,
    packet_coercer: Callable[[HistoricalPacket | Mapping[str, Any]], HistoricalPacket],
) -> tuple[HistoricalPacket, datetime]:
    packet_payload = update.get("packet")
    evaluation_timestamp = update.get("evaluation_timestamp")
    if not isinstance(packet_payload, Mapping):
        raise ValueError("Replay update entries require packet objects.")
    if not isinstance(evaluation_timestamp, str):
        raise ValueError("Replay update entries require evaluation_timestamp strings.")
    try:
        parsed_timestamp = datetime.fromisoformat(evaluation_timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "Replay update evaluation_timestamp must be a valid ISO-8601 datetime."
        ) from exc
    if parsed_timestamp.tzinfo is None:
        raise ValueError(
            "Replay update evaluation_timestamp must include timezone information."
        )
    return packet_coercer(packet_payload), parsed_timestamp.astimezone(timezone.utc)


def build_replay_step(
    watch: ReadinessWatchV1,
    *,
    step_index: int,
    phase: ReadinessV2ReplayPhase,
) -> ReadinessV2ReplayStep:
    history_entry = watch.history[-1]
    return ReadinessV2ReplayStep(
        step_index=step_index,
        phase=phase,
        revision=watch.revision,
        evaluation_timestamp=watch.updated_at,
        packet_timestamp=watch.context_snapshot.packet_timestamp,
        state=watch.state,
        routing_recommendation=watch.routing_recommendation,
        trigger_truth_state=watch.last_observation.trigger_truth_state,
        transition_reason=history_entry.transition_reason,
        change_summary=history_entry.change_summary,
        detected_change_kinds=list(history_entry.detected_change_kinds),
        terminal_reason=watch.terminal_reason,
    )


def build_replay_invariants(
    steps: Sequence[ReadinessV2ReplayStep],
    watch_id: str,
) -> ReadinessV2ReplayInvariants:
    return ReadinessV2ReplayInvariants(
        watch_id_stable=bool(watch_id) and len(steps) >= 1,
        revisions_contiguous=[step.revision for step in steps] == list(range(1, len(steps) + 1)),
        evaluation_timestamps_monotonic=all(
            current.evaluation_timestamp >= previous.evaluation_timestamp
            for previous, current in zip(steps, steps[1:])
        ),
        packet_timestamps_monotonic=all(
            current.packet_timestamp >= previous.packet_timestamp
            for previous, current in zip(steps, steps[1:])
        ),
    )


def append_detected_change(
    changes: list[ReadinessWatchDetectedChange],
    *,
    kind: str,
    from_value: str,
    to_value: str,
    detail: str,
) -> None:
    if from_value == to_value:
        return
    changes.append(
        ReadinessWatchDetectedChange(
            kind=kind,
            from_value=from_value,
            to_value=to_value,
            detail=detail,
        )
    )
