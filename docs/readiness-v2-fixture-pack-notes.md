# Readiness V2 Fixture Pack Notes

## 1. What fixture cases were added
- One ZN bootstrap case that emits `premarket_briefing_v1`, the initial `query_trigger_v1` set, and the initial `readiness_watch_v1`.
- One ZN wait-to-wait update case using the initial watch with a later evaluation timestamp and no trigger satisfaction.
- One ZN wait-to-requery update case using the initial watch with a price-touch observation and value-location shift.
- One ZN invalidation update case using the initial watch with a deterministic price-breach invalidation.

## 2. What artifact behavior is now locked by tests
- The exact JSON content of the bootstrap harness artifact for the fixture-backed ZN packet.
- The exact JSON content of the update harness artifact for the wait, requery, and invalidation fixture-backed ZN cases.
- Schema validity of the stored golden artifacts and the shared prior-watch fixture used by the update cases.
- The current deterministic IDs, timestamps, trigger payloads, routing recommendations, detected changes, and watch-state outputs for the fixture pack.

## 3. What remains intentionally unlocked
- Any contract other than ZN.
- Any readiness v2 case outside the single bootstrap and three update scenarios in this fixture pack.
- Any future deterministic artifact changes that require an intentional golden update after review.
