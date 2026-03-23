# Readiness Repair Decisions

## 1. Contract Scope
- Decision: Should readiness remain multi-contract or be reduced to a single-contract slice?
- Recommendation: Reduce readiness to a single-contract slice.
- Why: The current readiness prompt asset is shared-scope and packet-backed readiness conversion supports `ES`, `NQ`, `CL`, `ZN`, `6E`, and `MGC`, while the built-in fixture-backed readiness verification path is only wired for `ZN`. That leaves the current repo with broader readiness runtime scope than its narrowest deterministic verification surface. [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L536-L554) [`readiness_adapter.py`](../src/ninjatradebuilder/readiness_adapter.py#L9-L30) [`readiness_verify.py`](../src/ninjatradebuilder/readiness_verify.py#L182-L203)
- Tradeoff: This tightens repair scope and boundary control, but temporarily narrows readiness contract coverage while the repaired slice is stabilized.

## 2. Canonical Vocabulary
- Decision: Should canonical readiness vocabulary remain the current repo vocabulary or be renamed?
- Recommendation: Keep the current repo vocabulary as canonical for the repair.
- Why: `WAIT_FOR_TRIGGER` and `recheck_at_time` are already encoded consistently across the readiness prompt asset, readiness-trigger normalization, readiness schema validation, and watchman trigger handling. Renaming them during repair would add terminology churn to code paths that already align with each other. [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L9-L13) [`prompt_assets.py`](../src/ninjatradebuilder/prompt_assets.py#L525-L533) [`runtime.py`](../src/ninjatradebuilder/runtime.py#L174-L217) [`schemas/outputs.py`](../src/ninjatradebuilder/schemas/outputs.py#L50-L87) [`watchman.py`](../src/ninjatradebuilder/watchman.py#L304-L323)
- Tradeoff: This preserves current naming even though it differs from the earlier narrow-slice terminology.

## 3. Readiness Web Surface
- Decision: Is the existing readiness web surface part of the repaired product surface, legacy-only, or out of scope?
- Recommendation: Treat the existing readiness web surface as legacy-only.
- Why: The current readiness runtime boundary is centered on `run_readiness()` and the operator verification harness, while a separate local web interface already exists as an additional surface. The runtime and verifier are the clearer readiness execution and validation center of gravity in the inspected repo state. [`runtime.py`](../src/ninjatradebuilder/runtime.py#L271-L299) [`readiness_verify.py`](../src/ninjatradebuilder/readiness_verify.py#L43-L115) [`readiness_verify.py`](../src/ninjatradebuilder/readiness_verify.py#L422-L487) [`readiness_web.py`](../src/ninjatradebuilder/readiness_web.py#L186-L256)
- Tradeoff: The repo keeps a non-core readiness surface in place without elevating it into the repaired product contract.

## 4. Watchman Breadth
- Decision: Is current Watchman breadth intentional foundation or unintended scope expansion?
- Recommendation: Treat current Watchman breadth as unintended scope expansion.
- Why: Watchman currently derives a broad readiness substrate that includes allowed-hours state, staleness, visual readiness, value location, opening state, range expansion, volume participation, delta agreement, trigger context, event risk, governance flags, and contract-specific macro state before prompt execution. That is materially broader than a minimal trigger-first readiness foundation. [`watchman.py`](../src/ninjatradebuilder/watchman.py#L62-L80) [`watchman.py`](../src/ninjatradebuilder/watchman.py#L84-L248) [`watchman.py`](../src/ninjatradebuilder/watchman.py#L432-L580) [`runtime.py`](../src/ninjatradebuilder/runtime.py#L277-L285)
- Tradeoff: This frames part of the current deterministic readiness substrate as non-core, which may later require pruning, containment, or explicit re-justification.
