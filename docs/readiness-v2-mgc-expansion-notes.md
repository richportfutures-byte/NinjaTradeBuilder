# Readiness V2 MGC Expansion Notes

## 1. What MGC-specific deterministic logic was added
- `MGC` is now registered through the readiness v2 contract-adapter boundary for bootstrap, update, and replay.
- The MGC adapter uses MGC-native structured fields already present on validated packets and extensions: `dxy_context`, `yield_context`, `macro_fear_catalyst_summary`, `swing_penetration_volume_summary`, and packet `cross_market_context`.
- MGC briefing and watch artifacts now ground operator-facing narrative claims in those deterministic MGC fields, and MGC watch change detection now tracks MGC-specific macro and cross-market posture changes instead of carrying index-futures or CL-specific assumptions.
- MGC governance and trigger validation now fail closed on non-MGC packets, non-MGC triggers, and non-MGC watch chains.

## 2. What behavior remains shared through the adapter boundary
- The operator surface still exposes only the existing `bootstrap`, `update`, and `replay` modes.
- Artifact shapes, routing semantics, canonical trigger vocabulary, narrative-grounding requirements, watch continuity rules, and replay invariants remain shared and schema-backed across `ZN`, `ES`, `NQ`, `CL`, and `MGC`.
- Harness resolution, replay assembly, detected-change appending, and invariant enforcement still route through the existing shared readiness v2 modules.

## 3. What remains intentionally deferred before adding a sixth contract
- No legacy readiness v1 surfaces were widened or repurposed.
- No new trigger families, routing actions, or product surfaces were added for MGC.
- No provider or LLM behavior was introduced.
- Contract support beyond `ZN`, `ES`, `NQ`, `CL`, and `MGC` remains deferred until another contract can justify its own deterministic field set and fixture-backed artifact discipline.
