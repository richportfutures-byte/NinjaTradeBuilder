# Readiness V2 PR Packet

## 1. Suggested PR title
Add six-contract readiness v2 internal operator surface and release-candidate verification pack

## 2. Suggested PR summary
This PR adds the bounded readiness v2 internal operator surface with deterministic `bootstrap`, `update`, and `replay` flows across `6E`, `CL`, `ES`, `MGC`, `NQ`, and `ZN`. It includes strict schema-backed artifacts, contract adapters, fixture/golden coverage, operator-surface smoke coverage, and the merge/release review docs needed for internal review. It preserves the Stage A-D production spine, leaves legacy readiness v1 untouched, and keeps readiness v2 analytical, deterministic, and bounded.

## 3. Scope included
- `readiness_v2` schemas, contract adapters, shared logic, harness, and package entrypoint
- Six supported contracts: `6E`, `CL`, `ES`, `MGC`, `NQ`, `ZN`
- Deterministic bootstrap/update/replay artifact generation
- Fixture and golden artifact pack for the supported contracts
- Operator-surface tests and deterministic smoke coverage
- Readiness v2 release, conformance, regression, review, and merge docs

## 4. Scope explicitly not included
- Any Stage A-D pipeline behavior changes
- Any legacy readiness v1 behavior changes
- Any `readiness_web.py` changes
- Any new operator modes or product surfaces
- Any scheduler, persistence, hosted service, or UI layer
- Any provider/LLM behavior inside readiness v2
- Any setup construction, trade authorization, or Stage C routing expansion

## 5. Verification performed
- `.\.venv\Scripts\python.exe -m pytest`
- `$env:GEMINI_API_KEY='ci-placeholder'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe tests\cli_smoke_runner.py`
- `$env:GEMINI_API_KEY='ci-placeholder'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe tests\compiler_runtime_smoke_runner.py`
- `$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe tests\readiness_v2_operator_smoke_runner.py`

## 6. Reviewer focus points
- Verify the six-contract adapter boundary remains narrow and deterministic.
- Verify operator-facing narrative remains claim/provenance-backed and structure-pointing rather than setup-building or decorative.
- Verify routing, lockout, freshness, invalidation, replay, and continuity remain deterministic and bounded.
- Verify fixture/golden outputs match the intended artifact semantics for `bootstrap`, `update`, and `replay`.
- Verify the handoff, go/no-go, thesis-conformance, and full-regression docs agree on scope and release status.

## 7. Merge risk assessment
Low-to-moderate for the bounded internal surface: the repo has full pytest coverage, deterministic smoke coverage, explicit fail-closed behavior, and no intended changes to Stage A-D or legacy readiness; the main review risk is ensuring the reviewer agrees with the widened six-contract internal scope and the amount of readiness-v2 documentation included in the change.

## 8. Recommended labels, if any
- `internal`
- `readiness-v2`
- `deterministic-runtime`
- `review-required`
- `docs`
