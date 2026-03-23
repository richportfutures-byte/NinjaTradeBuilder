# Readiness V2 Narrative Grounding Notes

## 1. What grounding/provenance fields were added or tightened
- Added explicit narrative provenance records to grounded claim-bearing artifacts so thesis, trigger, invalidation, lockout, and watch-summary text now carry source-path, value, timestamp, and deterministic-condition backing.
- Tightened `premarket_briefing_v1` so `narrative_feature_thesis` must be the ordered join of `narrative_feature_thesis_claim_ids` over `thesis_claims`, and tightened trigger summaries so they carry supporting claim ids plus provenance.
- Tightened `query_trigger_v1` and `readiness_watch_v1` so `operator_explanation` and `operator_summary` must be the ordered join of explicit local claim ids over schema-backed operator claim records.

## 2. What narrative behavior is now locked by tests
- Bootstrap briefing narrative text must resolve exactly from grounded thesis claims with provenance.
- Trigger explanation text must resolve exactly from grounded trigger claims with provenance.
- Watch summary text must resolve exactly from grounded watch claims with provenance across the fixture-backed bootstrap, wait, requery, and invalidation cases.
- Schema validation now fails when operator-facing narrative text is changed without matching claim-id and provenance support.

## 3. What remains intentionally deferred
- Any grounding model beyond the existing ZN-only readiness v2 artifacts.
- Any LLM-assisted articulation, provider-generated provenance, or cross-surface narrative unification.
- Any attempt to ground legacy readiness v1, Stage A-D, or the legacy readiness web surface.
