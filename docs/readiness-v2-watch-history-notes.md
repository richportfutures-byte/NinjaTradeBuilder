# Readiness V2 Watch History Notes

## 1. What continuity fields were added or tightened
- Added `revision`, `prior_watch_id`, `prior_revision`, and `history` to `readiness_watch_v1` so each watch artifact now carries deterministic lineage and revision continuity.
- Added strict history entries with revision number, prior-link fields, evaluation and packet timestamps, trigger-truth state, routing recommendation, transition reason, detected change kinds, and a deterministic change summary.
- Tightened watch validation so the latest history entry must match the current watch state, routing recommendation, timestamps, detected changes, and terminal reason.

## 2. What lifecycle continuity is now locked by tests
- Bootstrap watches now start at revision 1 with a single initialized history entry.
- Wait-to-wait updates now require revision growth, prior linkage, and a `no_material_change` history entry.
- Wait-to-requery updates now require revision growth, prior linkage, and a `trigger_requery_ready` history entry.
- Completed or terminal watches now fail closed on further update attempts, and fixture-backed harness outputs lock the continuity fields in the stored golden artifacts.

## 3. What remains intentionally deferred
- Any persistence layer beyond the continuity carried inside the watch artifact itself.
- Any continuity model beyond the current ZN-only readiness v2 watch lifecycle.
- Any legacy readiness v1, Stage A-D, or readiness web continuity integration.
