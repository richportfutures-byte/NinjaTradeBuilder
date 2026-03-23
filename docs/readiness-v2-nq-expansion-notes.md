# Readiness V2 NQ Expansion Notes

## 1. What NQ-specific deterministic logic was added
Added a dedicated NQ readiness v2 builder module at `src/ninjatradebuilder/readiness_v2/nq.py` plus an NQ adapter registration in `src/ninjatradebuilder/readiness_v2/adapters.py`. The NQ path now builds `premarket_briefing_v1`, `query_trigger_v1`, `readiness_watch_v1`, and replay artifacts from validated NQ packets using NQ-native fields including `relative_strength_vs_es`, deterministic megacap-leadership posture derived from `megacap_leadership_table`, and bond-yield headwind context from `market_packet.cross_market_context.bond_yield_direction`. NQ fixture-backed bootstrap, update, and replay artifact coverage was added under `tests/fixtures/readiness_v2/`.

## 2. What behavior remains shared through the adapter boundary
Bootstrap, update, and replay are still resolved through the shared adapter registry and the existing harness modes. The top-level artifact contracts, canonical trigger vocabulary, watch lifecycle, routing bounds, continuity rules, replay invariants, narrative grounding rules, and operator-surface behavior remain shared across `ES`, `NQ`, and `ZN`, with common replay/change helpers still centralized in `src/ninjatradebuilder/readiness_v2/shared.py`.

## 3. What remains intentionally deferred before adding a fourth contract
No fourth contract adapter was added, no legacy readiness v1 integration changed, no new operator modes were introduced, and no broader abstraction over all contract-specific feature extraction was introduced. Any fourth contract still requires its own contract-native feature snapshot, watch-context fields, trigger/invalidation logic, fixture pack, and golden-artifact coverage before registration.
