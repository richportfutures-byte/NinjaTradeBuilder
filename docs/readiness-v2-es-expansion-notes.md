# Readiness V2 ES Expansion Notes

## 1. What ES-specific deterministic logic was added
Added an ES contract adapter and a dedicated ES deterministic builder module behind the existing readiness v2 boundary. The ES path now builds `premarket_briefing_v1`, `query_trigger_v1`, `readiness_watch_v1`, and replay artifacts from validated ES packets using ES-native contract extension fields, ES event-calendar posture, ES value references, ES-specific trigger and invalidation wording, grounded claim/provenance records, and the same deterministic watch-history continuity rules already enforced for ZN.

## 2. What behavior remains shared through the adapter boundary
Bootstrap, update, and replay are still resolved through the shared adapter registry and the existing operator harness surface. Top-level artifact schemas, canonical trigger vocabulary, watch state model, routing bounds, watch-history continuity, replay invariants, narrative grounding rules, and targeted fixture-backed golden regression checks remain shared and deterministic across the now-supported `ES` and `ZN` contracts.

## 3. What remains intentionally deferred before adding a third contract
No third contract adapter, no broader contract-family abstraction over value logic, no legacy readiness integration changes, no prompt/provider behavior, and no expansion beyond the current bounded bootstrap/update/replay surface were added here. Additional contracts still require their own contract-native deterministic context, trigger, invalidation, and fixture packs before they should be registered.
