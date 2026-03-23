# Readiness V2 Cross-Contract Hardening Notes

## 1. What was tightened/shared
Shared bootstrap and update artifact assembly now runs through common adapter helpers in `src/ninjatradebuilder/readiness_v2/adapters.py` so ES and ZN use the same artifact-wrapping path. Shared replay-step construction, replay invariant calculation, replay-update parsing, and detected-change append behavior now run through `src/ninjatradebuilder/readiness_v2/shared.py` and are reused by both `es.py` and `zn.py`. The harness no longer silently defaults multi-contract bundle inputs to `ZN`; bundle inputs now require explicit `--contract ES` or `--contract ZN`. Schema validation also now enforces shared bootstrap timestamp alignment and replay contract alignment more explicitly.

## 2. What remains intentionally contract-specific
`src/ninjatradebuilder/readiness_v2/zn.py` still owns ZN-native treasury-auction posture, ZN contract-extension handling, and ZN watch-context fields such as `treasury_auction_schedule` and `auction_proximity_state`. `src/ninjatradebuilder/readiness_v2/es.py` still owns ES-native market-internals posture, ES contract-extension handling, and ES watch-context fields such as `breadth` and `index_cash_tone`. Contract-native briefing claims, trigger/invalidation wording, and context snapshots remain separate where they rely on genuinely different structured packet fields.

## 3. What remains intentionally deferred before adding a third contract
No third adapter was added, no legacy readiness v1 integration changed, no harness modes or product surfaces changed, and no broader abstraction over all contract-specific feature extraction was introduced. Additional contracts still require their own contract-native packet coercion, briefing feature snapshot, trigger logic, invalidation logic, fixture pack, and golden-artifact coverage before registration.
