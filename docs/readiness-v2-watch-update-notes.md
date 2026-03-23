# Readiness V2 Watch Update Notes

## 1. What was added
- A ZN-only deterministic `update_zn_readiness_watch(...)` path in `src/ninjatradebuilder/readiness_v2/zn.py` that advances an existing `readiness_watch_v1` from a prior watch, a newly validated packet, and an evaluation timestamp.
- Expanded `readiness_watch_v1` schema support for watch updates in `src/ninjatradebuilder/schemas/readiness_v2.py`, including:
  - deterministic routing recommendation
  - change-detection records
  - richer watch context fields for event risk, auction proximity, macro posture, and value location
  - persisted post-trigger policy on the watch
- State-machine routing output in `src/ninjatradebuilder/readiness_v2/state_machine.py` now emits deterministic operator recommendations limited to `WAIT`, `REQUERY_STAGE_B`, and `EXPIRE_WATCH`.
- Focused watch-update tests were added in `tests/test_readiness_v2.py`.

## 2. What update rules are now deterministic
- Packet freshness versus staleness.
- Session access changes, including transition into session lockout and resumption back into active waiting when the lockout clears.
- Event risk state changes.
- Treasury auction proximity state changes.
- Macro-release posture changes by direct comparison of structured extension fields.
- Value-location changes relative to the developing value area.
- Trigger truth changes for the canonical `price_level_touch` and `recheck_at_time` families.
- Trigger invalidation when the watch can no longer be used as-is.
- Thesis invalidation when the watch’s own deterministic invalidation rules are met.
- Expiry when the watch reaches its explicit TTL.
- Operator routing recommendation constrained to `WAIT`, `REQUERY_STAGE_B`, or `EXPIRE_WATCH`.
- Fail-closed rejection of incoherent updates such as terminal-watch advancement, timestamp regression, or backwards packet timestamps.

## 3. What remains intentionally deferred
- No Stage C reentry.
- No new prompt surface or LLM execution path.
- No readiness v2 web surface.
- No widening beyond ZN.
- No new trigger families beyond `price_level_touch` and `recheck_at_time`.
- No persistence, scheduler, or long-running watch loop.
