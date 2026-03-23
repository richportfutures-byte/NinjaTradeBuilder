# Readiness V2 Operator Harness Notes

## 1. What was added
- A separate ZN-only readiness v2 operator harness at `python -m ninjatradebuilder.readiness_v2.harness` that validates packet input, builds or updates schema-backed readiness v2 artifacts, emits deterministic JSON to stdout, and can optionally write the same artifact JSON to a file.
- Schema-backed bootstrap and update artifact validation for the harness output so briefing, trigger, and watch references stay aligned at the artifact boundary.
- Focused harness tests for bootstrap success, update success, invalid mode and argument rejection, non-ZN rejection, malformed prior-watch rejection, and artifact-file writing.

## 2. Exact supported modes
- `bootstrap`: validated packet -> `premarket_briefing_v1` + `query_trigger_v1` list + initial `readiness_watch_v1`
- `update`: prior `readiness_watch_v1` + validated packet + evaluation timestamp -> updated `readiness_watch_v1`

## 3. What remains intentionally deferred
- Any contract support beyond ZN.
- Any web, dashboard, or legacy readiness surface integration.
- Any LLM/provider behavior, narrative generation beyond the existing deterministic v2 artifacts, or Stage C reentry routing.
