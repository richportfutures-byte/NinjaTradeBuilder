# Readiness V2 Merge Packet

## 1. Release status
Current six-contract readiness v2 internal release candidate with `GO` recommendation from the full-regression audit.

## 2. Supported contracts
`6E`, `CL`, `ES`, `MGC`, `NQ`, `ZN`

## 3. Supported operator modes
`bootstrap`, `update`, `replay`

## 4. Exact operator invocation commands
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

## 5. Exact verification commands used for signoff
```powershell
.\.venv\Scripts\python.exe -m pytest
$env:GEMINI_API_KEY='ci-placeholder'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe tests\cli_smoke_runner.py
$env:GEMINI_API_KEY='ci-placeholder'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe tests\compiler_runtime_smoke_runner.py
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe tests\readiness_v2_operator_smoke_runner.py
```

## 6. Files changed for readiness v2, grouped by:
### schemas
- `src/ninjatradebuilder/schemas/readiness_v2.py`

### adapters/contracts
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
- `README.md`
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
- `docs/readiness-v2-review-handoff.md`
- `docs/readiness-v2-full-regression-audit.md`

## 7. Preserved boundaries / non-goals
- Stage A-D production behavior remains untouched.
- Legacy readiness v1 remains untouched.
- `readiness_web.py` remains outside readiness v2.
- No new modes, product surfaces, trigger families, routing targets, or provider/LLM behavior were added beyond the current six-contract readiness v2 scope.
- Readiness v2 remains analytical, deterministic, and bounded; it does not construct setups or perform authorization.

## 8. Known acceptable limitations for internal release
- The surface is internal-only and deterministic; it is not a hosted service and has no persistence or scheduler layer.
- The operator surface remains limited to `bootstrap`, `update`, and `replay`.
- The release candidate is limited to the current six supported contracts and the current fixture-backed artifact discipline.
- External provider behavior is not part of the readiness v2 signoff path; provider-dependent repo smoke commands use placeholder env values.

## 9. Reviewer focus points
- Confirm the six-contract adapter boundary is still narrow and deterministic.
- Confirm operator-facing narrative remains claim/provenance-backed and does not leak setup-construction or authorization duties.
- Confirm the fixture/golden pack matches the intended bounded artifact semantics for bootstrap, update, and replay.
- Confirm repo discovery docs, operator quickstart, release recommendation, and full-regression audit are all aligned to the same six-contract internal release candidate.

## 10. Merge recommendation: READY_TO_MERGE or HOLD, with one sentence why
READY_TO_MERGE because the six-contract readiness v2 surface, repo discovery docs, full-regression audit, and reviewer handoff materials now align to the same bounded internal release candidate with clean deterministic verification.
