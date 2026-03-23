# Readiness V2 Review Handoff

## 1. Current supported contracts
`6E`, `CL`, `ES`, `MGC`, `NQ`, `ZN`

## 2. Current supported operator modes
`bootstrap`, `update`, `replay`

## 3. Exact operator invocation commands
```powershell
python -m ninjatradebuilder.readiness_v2 bootstrap --packet path\to\packet.json
python -m ninjatradebuilder.readiness_v2 update --prior-watch path\to\prior.watch.json --packet path\to\packet.json --evaluation-timestamp 2026-01-14T15:10:00Z
python -m ninjatradebuilder.readiness_v2 replay --packet path\to\bootstrap.packet.json --updates path\to\replay.updates.json
```

For multi-contract bundle inputs:
```powershell
python -m ninjatradebuilder.readiness_v2 bootstrap --packet path\to\packets.bundle.json --contract 6E
python -m ninjatradebuilder.readiness_v2 update --prior-watch path\to\prior.watch.json --packet path\to\packets.bundle.json --contract ES --evaluation-timestamp 2026-01-14T15:10:00Z
python -m ninjatradebuilder.readiness_v2 replay --packet path\to\packets.bundle.json --contract ZN --updates path\to\replay.updates.json
```

## 4. Exact test and smoke commands for verification
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_readiness_v2.py tests\test_readiness_v2_fixtures.py tests\test_readiness_v2_operator_surface.py
.\.venv\Scripts\python.exe tests\readiness_v2_operator_smoke_runner.py
```

## 5. Files/modules added or changed for readiness v2, grouped by:
### schemas
- `src/ninjatradebuilder/schemas/readiness_v2.py`

### contract adapters
- `src/ninjatradebuilder/readiness_v2/adapters.py`
- `src/ninjatradebuilder/readiness_v2/zn.py`
- `src/ninjatradebuilder/readiness_v2/es.py`
- `src/ninjatradebuilder/readiness_v2/nq.py`
- `src/ninjatradebuilder/readiness_v2/cl.py`
- `src/ninjatradebuilder/readiness_v2/mgc.py`
- `src/ninjatradebuilder/readiness_v2/sixe.py`

### shared/harness/operator surface
- `src/ninjatradebuilder/readiness_v2/shared.py`
- `src/ninjatradebuilder/readiness_v2/state_machine.py`
- `src/ninjatradebuilder/readiness_v2/harness.py`
- `src/ninjatradebuilder/readiness_v2/__init__.py`
- `src/ninjatradebuilder/readiness_v2/__main__.py`

### tests
- `tests/test_readiness_v2.py`
- `tests/test_readiness_v2_fixtures.py`
- `tests/test_readiness_v2_operator_surface.py`
- `tests/readiness_v2_operator_smoke_runner.py`

### fixtures
- `tests/fixtures/readiness_v2/zn_*`
- `tests/fixtures/readiness_v2/es_*`
- `tests/fixtures/readiness_v2/nq_*`
- `tests/fixtures/readiness_v2/cl_*`
- `tests/fixtures/readiness_v2/mgc_*`
- `tests/fixtures/readiness_v2/6e_*`

### docs
- `docs/readiness-v2-architecture-spec.md`
- `docs/readiness-v2-first-slice-notes.md`
- `docs/readiness-v2-first-slice-review.md`
- `docs/readiness-v2-watch-update-notes.md`
- `docs/readiness-v2-operator-harness-notes.md`
- `docs/readiness-v2-fixture-pack-notes.md`
- `docs/readiness-v2-narrative-grounding-notes.md`
- `docs/readiness-v2-watch-history-notes.md`
- `docs/readiness-v2-replay-notes.md`
- `docs/readiness-v2-contract-adapter-notes.md`
- `docs/readiness-v2-es-expansion-notes.md`
- `docs/readiness-v2-nq-expansion-notes.md`
- `docs/readiness-v2-cl-expansion-notes.md`
- `docs/readiness-v2-mgc-expansion-notes.md`
- `docs/readiness-v2-6e-expansion-notes.md`
- `docs/readiness-v2-operator-quickstart.md`
- `docs/readiness-v2-internal-release-notes.md`
- `docs/readiness-v2-rc-hardening-notes.md`
- `docs/readiness-v2-go-no-go.md`
- `docs/readiness-v2-thesis-conformance.md`

## 6. Preserved boundaries and non-goals
- Stage A-D production behavior remains untouched.
- Legacy readiness v1 surfaces remain untouched.
- `readiness_web.py` remains outside readiness v2.
- No new operator modes, product surfaces, trigger families, or routing targets were added beyond the current bounded v2 scope.
- No Stage C setup construction, trade authorization, or provider/LLM behavior is part of readiness v2.

## 7. Known acceptable limitations for the internal release candidate
- The surface is internal and deterministic only; it is not a hosted service and has no persistence or scheduler layer.
- The operator surface remains bounded to `bootstrap`, `update`, and `replay`.
- The release candidate is limited to the current six supported contracts and their fixture-backed artifact discipline.

## 8. Merge recommendation: READY_FOR_REVIEW or NOT_READY, with one sentence why
READY_FOR_REVIEW because the six-contract operator surface, golden artifacts, fail-closed behavior, smoke path, and reviewer/operator docs are now aligned to the current bounded readiness v2 release candidate.
