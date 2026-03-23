# Readiness V2 First Slice Review

## 1. What matches the intended first slice
- The implementation remains ZN-only and uses validated historical packet structures as inputs.
- The new surfaces remain separate from Stage A-D and legacy readiness v1 behavior.
- The first slice still produces strict versioned artifacts for `premarket_briefing_v1`, `query_trigger_v1`, and `readiness_watch_v1`.
- Trigger generation still stays on the current canonical families `price_level_touch` and `recheck_at_time`.
- The watch lifecycle remains deterministic and centered on Stage A+B reanalysis rather than any trade-authorizing path.
- Operator-facing narrative fields are still built from structured packet and extension data rather than freeform LLM output.

## 2. What was weak or misaligned
- The first slice still exposed Stage C reentry fields and routing states in ways that could be materialized even though the first-slice boundary explicitly excludes them.
- Watch-schema coherence was too loose: observation state, evaluation timestamps, and current watch state were not tightly cross-validated.
- Session close was being represented as an invalidation condition even though it is better treated as expiry or lockout, which blurred deterministic semantics.
- Briefing posture did not fully account for session access or packet staleness, which weakened the deterministic ownership boundary.
- Trigger selection skipped structurally relevant nearby levels too aggressively, which made the initial `price_level_touch` less grounded than it should have been.
- Builder and test coverage did not explicitly reject mismatched trigger sets or Stage C boundary breaks.

## 3. What you changed
- Tightened `query_trigger_v1` so the first slice only accepts deterministic, executable triggers that unlock Stage A+B reanalysis.
- Tightened `readiness_watch_v1` so the first slice rejects `READY_FOR_SETUP_REENTRY`, rejects `STAGE_C_REENTRY`, requires coherent watch timestamps, and requires observation state to match the actual watch state.
- Tightened `premarket_briefing_v1` so lockout posture must align with actual session, event, and governance lockout state.
- Hardened the state machine so `READY_FOR_SETUP_REENTRY` is outside the first-slice transition boundary and no Stage C routing is emitted.
- Moved session-close handling out of builder-produced invalidation rules so expiry and lockout remain distinct from thesis invalidation.
- Strengthened ZN briefing grounding by carrying ZN-specific macro context into structured claims and the narrative thesis.
- Normalized builder-generated datetimes to UTC for more consistent deterministic artifacts.
- Tightened trigger selection so the initial `price_level_touch` chooses the nearest structurally relevant untouched level instead of skipping ahead unnecessarily.
- Added builder-side validation that watch triggers must belong to the supplied briefing and remain unique by family.
- Expanded tests to cover stale-briefing posture, mismatched trigger rejection, Stage C boundary rejection, and the hardened state-machine boundary.

## 4. What remains intentionally deferred
- No Stage C reentry support.
- No new readiness v2 runtime entrypoint, prompt surface, or LLM execution path.
- No readiness v2 web surface.
- No widening beyond ZN.
- No new trigger families beyond `price_level_touch` and `recheck_at_time`.
- No persistence, scheduler, or long-running watch orchestration.
