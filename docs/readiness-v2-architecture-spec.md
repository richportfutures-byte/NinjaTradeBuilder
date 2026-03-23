# Readiness V2 Architecture Spec

## 1. Design Objective
Readiness v2 is a repaired, single-contract operator layer that sits beside the unchanged Stage A-D production spine: it should turn validated packet data, deterministic trigger truth, lockout truth, freshness truth, and preserved analysis artifacts into operator-facing briefings, executable query triggers, and active watch objects, while leaving Stage A+B, Stage C, and Stage D as the only production surfaces that emit market reads, setups, and risk authorization. The narrative-feature thesis remains an operator-facing, structure-pointing articulation grounded in real schema-backed facts and feature claims, not a substitute for pipeline output or a freeform trade directive. [`pipeline.py`](../src/ninjatradebuilder/pipeline.py#L70-L163) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L200-L203) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L375-L389) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L438-L452) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L495-L533)

## 2. Preserved Boundaries
- What Stage A+B still own: packet sufficiency gating and contract market read remain the exclusive producers of `sufficiency_gate_output_v1` and `contract_analysis_v1`, and any fresh market read still comes from the existing Stage A+B prompt path inside the production pipeline. [`pipeline.py`](../src/ninjatradebuilder/pipeline.py#L76-L113) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L136-L186) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L200-L203)
- What Stage C still owns: setup construction remains the exclusive producer of `proposed_setup_v1`, including entry, stop, targets, sizing, and setup class, and it still accepts `contract_analysis_json` rather than any readiness-owned object. [`pipeline.py`](../src/ninjatradebuilder/pipeline.py#L115-L137) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L375-L432)
- What Stage D still owns: risk and challenge authorization remain the exclusive producers of `risk_authorization_v1`, including approval, rejection, reduction, and the ordered 13-check decision surface. [`pipeline.py`](../src/ninjatradebuilder/pipeline.py#L139-L163) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L438-L489)
- What readiness v2 may do: create operator-facing briefings, express executable query triggers, hold active watch state, evaluate watch progression deterministically, mark contamination/invalidation/expiry, and route operators back to Stage A+B reanalysis or to Stage C reentry only through a preserved same-contract `contract_analysis_v1`.
- What readiness v2 may never do: emit `contract_analysis_v1`, `proposed_setup_v1`, or `risk_authorization_v1`; generate exact entry, stop, target, or size language; bypass deterministic trigger truth or lockout truth; coerce watch output into Stage C input; or change the current Stage A-D production spine. [`schemas/outputs.py`](../src/ninjatradebuilder/schemas/outputs.py#L181-L324) [`runtime.py`](../src/ninjatradebuilder/runtime.py#L271-L299)

## 3. New Surfaces
### premarket_briefing_v1
- purpose: Produce an operator-facing pre-session or pre-engagement briefing that states the narrative-feature thesis, points to structure that matters, identifies candidate triggers, and records invalidation and lockout posture using real schema-backed inputs.
- producer: A new readiness v2 briefing surface that consumes validated packet data plus deterministic context and uses the LLM only for contract-native articulation.
- consumer: The operator, `query_trigger_v1`, and `readiness_watch_v1`.
- relation to the existing pipeline: Upstream and parallel to `run_pipeline()`; it does not replace Stage A+B and does not emit Stage C or Stage D artifacts. [`pipeline.py`](../src/ninjatradebuilder/pipeline.py#L70-L163)

### query_trigger_v1
- purpose: Represent the next executable readiness condition as a machine-readable trigger object with explicit downstream unlock semantics.
- producer: A new readiness v2 query surface that starts from briefing claims or preserved analysis context, then validates trigger executability deterministically before accepting the trigger.
- consumer: `readiness_watch_v1`, the operator, and the routing layer.
- relation to the existing pipeline: It does not call Stage C or Stage D directly; it only arms watches or qualifies later routing back into the preserved pipeline.

### readiness_watch_v1
- purpose: Persist and evaluate active readiness state, including trigger truth, contamination, invalidation, expiry, and routing eligibility.
- producer: A deterministic watch manager built from accepted `query_trigger_v1` objects plus current packet context.
- consumer: The watch evaluator/router and the operator.
- relation to the existing pipeline: It may dispatch Stage A+B reanalysis or Stage C reentry through routing policy, but the watch object itself never becomes a substitute pipeline input.

## 4. Ownership Model
### deterministic ownership
- Trigger truth: determine whether a time, price, event, or session trigger has actually fired.
- Freshness/staleness: own packet age, source recency, and reuse validity.
- Event/session/governance lockouts: own event lockout truth, session availability, and governance hard stops.
- Watch state transitions: own every state entry, exit, downgrade, terminalization, and resume rule.
- Invalidation/expiry: own thesis invalidation levels, expiration windows, and reuse cutoffs.
- Routing decisions: own whether the next valid action is no-op, Stage A+B reanalysis, or Stage C reentry through a preserved `contract_analysis_v1`.

### LLM ownership
- Explanation: explain why the current watch or briefing posture exists in readable operator language.
- Contract-native articulation: express structure in contract-specific language without inventing non-schema evidence.
- Rendering structured claims into readable operator language: convert deterministic facts and schema-backed feature claims into concise operator-facing text, including the narrative-feature thesis.

## 5. Readiness V2 State Model
### UNARMED
- entry criteria: no active watch exists for the current briefing or query trigger, or the prior watch was closed without rearm.
- exit criteria: an accepted trigger is attached to a new watch and deterministic prerequisites are satisfied.
- allowed next actions: create `query_trigger_v1`, arm `readiness_watch_v1`, or discard the current thesis.

### ARMED_WAITING
- entry criteria: a watch exists, the trigger payload is valid, no hard lockout is active, and the watch is still within freshness and expiry limits.
- exit criteria: the trigger becomes true, contamination appears, invalidation appears, a hard lockout appears, or the watch expires.
- allowed next actions: keep evaluating trigger truth, expose operator status, or disarm the watch.

### TRIGGER_OBSERVED
- entry criteria: the primary deterministic trigger flips true for the active watch.
- exit criteria: the watch either requires a bounded post-trigger formation step, becomes ready for reanalysis, becomes ready for setup reentry, or is interrupted by contamination or lockout.
- allowed next actions: snapshot the observation, start a structure-forming window, or route immediately if policy allows.

### STRUCTURE_FORMING
- entry criteria: a trigger has fired, but the watch policy requires a bounded formation or settling period before routing.
- exit criteria: formation resolves cleanly, contamination appears, invalidation appears, a lockout appears, or expiry occurs.
- allowed next actions: continue bounded evaluation, record structure markers, or cancel/expire the watch.

### READY_FOR_REANALYSIS
- entry criteria: trigger and context conditions are satisfied, no preserved Stage B thesis is eligible for reuse, and the next valid action is a fresh Stage A+B run.
- exit criteria: the router dispatches Stage A+B, or contamination/lockout/expiry occurs before dispatch.
- allowed next actions: dispatch Stage A+B, notify the operator, and archive or replace the watch.

### READY_FOR_SETUP_REENTRY
- entry criteria: trigger and context conditions are satisfied, and a preserved same-contract `contract_analysis_v1` remains valid for reuse into Stage C.
- exit criteria: the router dispatches Stage C with the preserved analysis, or the preserved analysis loses freshness/validity and the watch downgrades to reanalysis, contamination, lockout, or expiry.
- allowed next actions: dispatch Stage C using preserved analysis, downgrade to Stage A+B reanalysis, or archive the watch.

### CONTEXT_CONTAMINATED
- entry criteria: the watch context is materially polluted by freshness failure, session/event contamination, contradictory deterministic context, or similar non-terminal disturbance.
- exit criteria: the operator rebuilds from fresh inputs, or contamination explicitly clears and the watch is deliberately rearmed.
- allowed next actions: halt routing, request fresh packet inputs, rebuild the briefing/query/watch chain, or discard the watch.

### THESIS_INVALIDATED
- entry criteria: a deterministic invalidation condition proves the watch thesis wrong.
- exit criteria: none for the same watch.
- allowed next actions: close and archive the watch, then start a new briefing if needed.

### LOCKED_OUT
- entry criteria: session, event, or governance truth blocks action for the active watch.
- exit criteria: the lockout clears while the watch remains fresh and valid, or the watch expires or contaminates while locked.
- allowed next actions: hold the watch, notify the operator, resume to the appropriate active state when clear, or expire the watch.

### TERMINAL_EXPIRED
- entry criteria: the watch exceeds its explicit TTL, session horizon, or reuse window.
- exit criteria: none for the same watch.
- allowed next actions: archive the watch and regenerate a new briefing/query/watch chain from fresh data.

## 6. Trigger Family Expansion
- Current canonical family `recheck_at_time`
  - what evidence supports it: wall-clock time crossing a configured ISO timestamp.
  - whether it is deterministic, hybrid, or LLM-assisted: deterministic.
  - what downstream action it can unlock: `TRIGGER_OBSERVED`, then either `STRUCTURE_FORMING` or `READY_FOR_REANALYSIS`, and later `READY_FOR_SETUP_REENTRY` when a preserved analysis is eligible. [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L9-L13) [`runtime.py`](../src/ninjatradebuilder/runtime.py#L195-L207) [`watchman.py`](../src/ninjatradebuilder/watchman.py#L432-L440)
- Current canonical family `price_level_touch`
  - what evidence supports it: current price reaching a configured level within deterministic tick tolerance.
  - whether it is deterministic, hybrid, or LLM-assisted: deterministic.
  - what downstream action it can unlock: `TRIGGER_OBSERVED`, then either `STRUCTURE_FORMING`, `READY_FOR_REANALYSIS`, or `READY_FOR_SETUP_REENTRY` depending watch policy. [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L9-L13) [`runtime.py`](../src/ninjatradebuilder/runtime.py#L209-L217) [`watchman.py`](../src/ninjatradebuilder/watchman.py#L442-L449)
- Next family `price_level_break`
  - what evidence supports it: price crossing and holding beyond a configured level with explicit buffer and hold rules.
  - whether it is deterministic, hybrid, or LLM-assisted: deterministic.
  - what downstream action it can unlock: `READY_FOR_REANALYSIS` or `READY_FOR_SETUP_REENTRY` when the watch depends on a break rather than a touch.
- Next family `event_window_clear`
  - what evidence supports it: a known event lockout window ending according to deterministic event timestamps already present in packet and contract-extension data.
  - whether it is deterministic, hybrid, or LLM-assisted: deterministic.
  - what downstream action it can unlock: transition out of `LOCKED_OUT` into `ARMED_WAITING` or directly into `READY_FOR_REANALYSIS` when the watch was only blocked by event timing.
- Next family `session_window_open`
  - what evidence supports it: current time entering a configured contract session or named subwindow.
  - whether it is deterministic, hybrid, or LLM-assisted: deterministic.
  - what downstream action it can unlock: arming the watch, resuming from `LOCKED_OUT`, or routing to `READY_FOR_REANALYSIS` when the watch thesis is explicitly session-gated.
- Next family `structure_reclaim`
  - what evidence supports it: deterministic packet features showing reclaim or hold relative to schema-native structure points such as value area, VWAP, pivot, or prior session extremes, with LLM articulation used only to describe why the reclaim matters in contract-native language.
  - whether it is deterministic, hybrid, or LLM-assisted: hybrid.
  - what downstream action it can unlock: `READY_FOR_REANALYSIS` only; it should not unlock direct Stage C reentry on its own.

## 7. Schema Direction
### premarket_briefing_v1
| Field | Direction |
| --- | --- |
| `schema` | Literal identity: `premarket_briefing_v1`. |
| `briefing_id` | Stable unique identifier for the briefing artifact. |
| `contract` | Contract symbol; v2 first slice runs on a single contract at runtime. |
| `created_at` | Briefing creation timestamp. |
| `source_packet_ref` | Packet identifier, digest, or equivalent reference to the validated source packet. |
| `packet_timestamp` | Original market-packet timestamp used for the briefing. |
| `session_snapshot` | Structured session/event/governance posture at briefing time. |
| `feature_snapshot` | Structured market features pulled directly from validated packet data and deterministic context. |
| `narrative_feature_thesis` | Short operator-facing paragraph describing the current thesis in contract-native language. |
| `thesis_claims` | Structured claims list, each tied to a schema-backed feature and evidence-field references. |
| `monitor_posture` | Operator-facing posture such as monitor, stand aside, or locked out. |
| `candidate_trigger_summaries` | Short list of candidate trigger summaries that can later become `query_trigger_v1`. |
| `invalidation_conditions` | Structured invalidation conditions tied to real levels, time windows, or deterministic context changes. |
| `lockout_conditions` | Structured event, session, or governance conditions that block action. |
| `expires_at` | Explicit briefing expiry. |

### query_trigger_v1
| Field | Direction |
| --- | --- |
| `schema` | Literal identity: `query_trigger_v1`. |
| `trigger_id` | Stable unique identifier for the trigger artifact. |
| `source_briefing_id` | Reference back to the originating `premarket_briefing_v1`. |
| `contract` | Contract symbol matching the source briefing or preserved analysis. |
| `created_at` | Trigger creation timestamp. |
| `family` | Canonical trigger family name. |
| `mode` | `deterministic`, `hybrid`, or `llm_assisted`. |
| `label` | Short operator label for the trigger. |
| `deterministic_parameters` | Family-specific executable payload, such as `recheck_at_time`, `price_level`, `buffer_ticks`, `hold_seconds`, `event_id`, or `session_window`. |
| `supporting_claim_ids` | References to briefing or analysis claims that justify the trigger. |
| `unlock_action` | The next action this trigger can unlock, such as `route_stage_ab`, `route_stage_c_reentry`, `clear_lockout`, or `mark_invalidated`. |
| `expiry_policy` | Explicit expiry window or session-boundary rule for the trigger. |
| `invalidation_policy` | Explicit invalidation conditions that make the trigger unusable. |
| `operator_explanation` | Readable operator-facing explanation of why this trigger matters. |
| `validation_status` | Deterministic acceptance state for whether the trigger is executable. |

### readiness_watch_v1
| Field | Direction |
| --- | --- |
| `schema` | Literal identity: `readiness_watch_v1`. |
| `watch_id` | Stable unique identifier for the watch. |
| `contract` | Contract symbol for the active watch. |
| `created_at` | Watch creation timestamp. |
| `updated_at` | Last state-transition or evaluation timestamp. |
| `source_kind` | Origin type such as `premarket_briefing`, `query_trigger`, or `contract_analysis`. |
| `source_refs` | References to the source briefing, trigger, and optional preserved analysis artifacts. |
| `state` | One of the readiness v2 watch lifecycle states. |
| `active_trigger_family` | Primary trigger family currently being evaluated. |
| `trigger_payload` | The executable trigger parameters currently armed on the watch. |
| `context_snapshot` | Deterministic context at the last evaluation, including freshness, lockout, and session state. |
| `routing_target` | Current routing intent: none, Stage A+B reanalysis, or Stage C reentry. |
| `preserved_contract_analysis_ref` | Optional reference to a reusable `contract_analysis_v1`; required only for Stage C reentry routes. |
| `invalidation_rules` | Structured invalidation levels and conditions for the watch thesis. |
| `expiry_at` | Explicit terminal expiry timestamp. |
| `last_evaluated_at` | Last deterministic evaluation timestamp. |
| `last_observation` | Most recent trigger-truth or context observation that affected watch state. |
| `terminal_reason` | Populated only when the watch reaches a terminal state. |
| `operator_summary` | Readable operator-facing summary of the current watch posture. |

## 8. Proposed Module Layout
- Existing repo modules to keep stable initially
  - `src/ninjatradebuilder/pipeline.py`: keep as the Stage A-D production spine.
  - `src/ninjatradebuilder/runtime.py`: keep as the current prompt-execution layer and v1 readiness execution surface.
  - `src/ninjatradebuilder/readiness_verify.py`: keep as the current v1 operator verification harness.
  - `src/ninjatradebuilder/readiness_web.py`: keep as the current legacy local readiness surface.
- Proposed new modules
  - `src/ninjatradebuilder/readiness_v2/briefing.py`: own `premarket_briefing_v1` creation and briefing-level orchestration.
  - `src/ninjatradebuilder/readiness_v2/query.py`: own `query_trigger_v1` generation, deterministic validation, and trigger acceptance.
  - `src/ninjatradebuilder/readiness_v2/watch.py`: own `readiness_watch_v1` creation, storage shape, and lifecycle updates.
  - `src/ninjatradebuilder/readiness_v2/trigger_engine.py`: own deterministic evaluation of all supported trigger families.
  - `src/ninjatradebuilder/readiness_v2/state_machine.py`: own allowed watch states, transitions, and terminalization rules.
  - `src/ninjatradebuilder/readiness_v2/router.py`: own routing decisions back into Stage A+B or Stage C without letting watch output masquerade as pipeline input.
  - `src/ninjatradebuilder/readiness_v2/contracts/zn.py`: own first-slice contract-specific defaults, feature selection, and operator-language hints for the initial contract.

## 9. Migration Approach
- Treatment of current `readiness_engine_output_v1`: keep it as a frozen v1 compatibility surface for the current `run_readiness()` path, schema validation, and verification harness; do not retrofit the v2 watch lifecycle or new product surfaces into that v1 contract. [`runtime.py`](../src/ninjatradebuilder/runtime.py#L271-L299) [`schemas/outputs.py`](../src/ninjatradebuilder/schemas/outputs.py#L181-L324) [`readiness_verify.py`](../src/ninjatradebuilder/readiness_verify.py#L422-L487)
- Treatment of `readiness_web.py`: keep it as a legacy-only local surface and do not use it as the initial shell for v2. [`readiness_web.py`](../src/ninjatradebuilder/readiness_web.py#L186-L256)
- What should be built first: the v2 artifacts and deterministic watch machinery for one contract, centered on `premarket_briefing_v1`, `query_trigger_v1`, `readiness_watch_v1`, canonical trigger families, deterministic state transitions, and routing to Stage A+B only.
- What should not be touched yet: `pipeline.py`, prompt IDs 2-9, current Stage A-D schemas, current `run_readiness()` behavior, `readiness_engine_output_v1`, the current verifier artifact contract, and `readiness_web.py`. [`pipeline.py`](../src/ninjatradebuilder/pipeline.py#L70-L163) [`runtime.py`](../src/ninjatradebuilder/runtime.py#L271-L299) [`readiness_verify.py`](../src/ninjatradebuilder/readiness_verify.py#L465-L487) [`readiness_web.py`](../src/ninjatradebuilder/readiness_web.py#L186-L256)

## 10. First Implementation Slice
The first implementation slice should be a single-contract ZN readiness v2 slice that produces one `premarket_briefing_v1`, derives one validated `query_trigger_v1` using only the current canonical families `recheck_at_time` and `price_level_touch`, materializes one `readiness_watch_v1`, and drives that watch deterministically through `UNARMED`, `ARMED_WAITING`, `TRIGGER_OBSERVED`, `STRUCTURE_FORMING`, `READY_FOR_REANALYSIS`, `CONTEXT_CONTAMINATED`, `THESIS_INVALIDATED`, `LOCKED_OUT`, and `TERMINAL_EXPIRED`, with routing limited to fresh Stage A+B reanalysis only. This slice should not introduce Stage C reentry, should not extend `readiness_web.py`, should not alter `readiness_engine_output_v1`, and should use ZN because the current built-in fixture-backed readiness verification path is already ZN-only. [`readiness_verify.py`](../src/ninjatradebuilder/readiness_verify.py#L182-L203) [`readiness_verify.py`](../src/ninjatradebuilder/readiness_verify.py#L383-L399)
