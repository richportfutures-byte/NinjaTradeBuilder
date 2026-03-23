# Readiness V2 First Slice Notes

## What was added
- A new strict schema surface for `premarket_briefing_v1`, `query_trigger_v1`, and `readiness_watch_v1` in `src/ninjatradebuilder/schemas/readiness_v2.py`.
- A separate `src/ninjatradebuilder/readiness_v2/` package with:
  - deterministic watch-lifecycle scaffolding in `state_machine.py`
  - ZN-only briefing, query-trigger, and watch builders in `zn.py`
- Focused fixture-backed tests in `tests/test_readiness_v2.py` covering:
  - ZN-only packet acceptance
  - grounded briefing construction
  - canonical trigger-family generation
  - initial watch construction
  - deterministic lifecycle transitions

## What remains intentionally unimplemented
- No Stage C reentry routing.
- No new prompt surface or LLM runtime path for readiness v2.
- No readiness v2 web surface.
- No storage, scheduler, or long-running watch loop.
- No widening beyond ZN.
- No new trigger families beyond the current canonical `price_level_touch` and `recheck_at_time`.

## Exact boundaries preserved
- Stage A-D pipeline behavior was not intentionally changed.
- `readiness_engine_output_v1` behavior was not intentionally changed.
- Prompt 10 behavior was not intentionally changed.
- `watchman.py` was not rewritten into readiness v2.
- `readiness_web.py` and legacy readiness surfaces were left intact.

## Follow-on decisions required before widening beyond ZN
- Whether readiness v2 should stay on a deterministic Stage A+B reroute only boundary or admit Stage C reentry in a later slice.
- Which additional trigger families should be promoted from the architecture spec into executable schema and deterministic evaluation.
- Whether readiness v2 should eventually own a new runtime entrypoint or remain builder-first until a dedicated execution surface is justified.
- Whether legacy readiness verification and readiness v2 verification should remain separate or converge under a shared operator harness later.
