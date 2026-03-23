# Readiness V2 Replay Notes

## 1. What replay capability was added
Added a ZN-only deterministic `replay` path in the readiness v2 harness and builder layer. It bootstraps a watch from one validated ZN packet, applies an ordered list of replay updates through the existing watch update logic, and emits one strict `readiness_v2_replay_artifact_v1` JSON artifact containing the bootstrap summary, ordered watch steps, final watch snapshot, replay invariants, and terminal outcome fields when applicable.

## 2. What sequence behavior is now locked by tests
Tests now lock a successful bootstrap -> wait -> wait -> requery replay, replay artifact schema validity, revision and step ordering, monotonic evaluation and packet timestamps, final-watch alignment, harness JSON output stability for a golden replay case, rejection on non-monotonic timestamps, rejection after no-further-update states, and rejection on malformed or non-ZN replay inputs.

## 3. What remains intentionally deferred
Replay remains artifact-level only. It does not add persistence infrastructure, multi-contract support, legacy readiness integration, prompt/provider behavior, web-surface integration, or any routing beyond the existing ZN-only `WAIT`, `REQUERY_STAGE_B`, and terminal expiry outcomes already enforced by the current watch model.
