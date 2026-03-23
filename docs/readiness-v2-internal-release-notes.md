# Readiness V2 Internal Release Notes

## 1. What was added for internal deployability
Added a deterministic readiness v2 operator smoke runner at `tests/readiness_v2_operator_smoke_runner.py` and wired it into `.github/workflows/ci-smoke.yml` so CI now proves the packaged entrypoint `python -m ninjatradebuilder.readiness_v2` is runnable through the current bounded modes. Also tightened repo-level discovery by documenting the separate readiness v2 operator surface in `README.md` and preserving the dedicated invocation guide in `docs/readiness-v2-operator-quickstart.md`.

## 2. What invocation/test paths now prove the surface is runnable
The operator surface is now proven by direct module-invocation tests in `tests/test_readiness_v2_operator_surface.py`, fixture-backed golden checks in `tests/test_readiness_v2_fixtures.py`, and the deterministic CI smoke path `python tests/readiness_v2_operator_smoke_runner.py`, which runs `python -m ninjatradebuilder.readiness_v2` in `bootstrap`, `update`, and `replay` modes across the current six-contract fixture pack: `6E`, `CL`, `ES`, `MGC`, `NQ`, and `ZN`.

## 3. What remains intentionally out of scope before a broader release
Legacy readiness v1 integration, `readiness_web.py`, Stage A-D changes, prompt/provider behavior, contracts beyond `6E`, `CL`, `ES`, `MGC`, `NQ`, and `ZN`, new operator modes, and any broader service, UI, persistence, or hosted deployment layer remain intentionally out of scope for the current internal release.
