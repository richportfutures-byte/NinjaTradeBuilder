# Readiness V2 CL Expansion Notes

## 1. What CL-specific deterministic logic was added
- `CL` is now registered through the readiness v2 contract-adapter boundary for bootstrap, update, and replay.
- The CL adapter uses CL-native structured fields already present on validated packets and extensions: `eia_timing`, `realized_volatility_context`, `liquidity_sweep_summary`, `dom_liquidity_summary`, and packet `cross_market_context`.
- CL briefing and watch artifacts now ground operator-facing narrative claims in those deterministic CL fields, and CL watch change detection now tracks CL-specific posture changes instead of carrying NQ-specific relative-strength or megacap assumptions.
- CL governance and trigger validation now fail closed on non-CL packets, non-CL triggers, and non-CL watch chains.

## 2. What behavior remains shared through the adapter boundary
- The operator surface still exposes only the existing `bootstrap`, `update`, and `replay` modes.
- Artifact shapes, routing semantics, canonical trigger vocabulary, narrative-grounding requirements, watch continuity rules, and replay invariants remain shared and schema-backed across `ZN`, `ES`, `NQ`, and `CL`.
- Harness resolution, replay assembly, detected-change appending, and invariant enforcement still route through the existing shared readiness v2 modules.

## 3. What remains intentionally deferred before adding a fifth contract
- No legacy readiness v1 surfaces were widened or repurposed.
- No new trigger families, routing actions, or product surfaces were added for CL.
- No provider or LLM behavior was introduced.
- Contract support beyond `ZN`, `ES`, `NQ`, and `CL` remains deferred until another contract can justify its own deterministic field set and fixture-backed artifact discipline.
