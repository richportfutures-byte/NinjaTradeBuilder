from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "readiness_v2"


def _run_operator_surface(args: list[str]) -> dict:
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    pythonpath_entries = [str(REPO_ROOT / "src")]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

    result = subprocess.run(
        [sys.executable, "-m", "ninjatradebuilder.readiness_v2", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(2)
    return json.loads(result.stdout)


def main() -> int:
    cases = [
        (
            "ZN",
            [
                "bootstrap",
                "--packet",
                str(FIXTURES_DIR / "zn_bootstrap.packet.valid.json"),
            ],
            "bootstrap",
            "ARMED_WAITING",
        ),
        (
            "ES",
            [
                "update",
                "--prior-watch",
                str(FIXTURES_DIR / "es_initial_watch.valid.json"),
                "--packet",
                str(FIXTURES_DIR / "es_update_wait.packet.valid.json"),
                "--evaluation-timestamp",
                "2026-01-14T15:10:00Z",
            ],
            "update",
            "ARMED_WAITING",
        ),
        (
            "NQ",
            [
                "replay",
                "--packet",
                str(FIXTURES_DIR / "nq_bootstrap.packet.valid.json"),
                "--updates",
                str(FIXTURES_DIR / "nq_replay.updates.valid.json"),
            ],
            "replay",
            "READY_FOR_REANALYSIS",
        ),
        (
            "CL",
            [
                "bootstrap",
                "--packet",
                str(FIXTURES_DIR / "cl_bootstrap.packet.valid.json"),
            ],
            "bootstrap",
            "ARMED_WAITING",
        ),
        (
            "MGC",
            [
                "replay",
                "--packet",
                str(FIXTURES_DIR / "mgc_bootstrap.packet.valid.json"),
                "--updates",
                str(FIXTURES_DIR / "mgc_replay.updates.valid.json"),
            ],
            "replay",
            "READY_FOR_REANALYSIS",
        ),
        (
            "6E",
            [
                "update",
                "--prior-watch",
                str(FIXTURES_DIR / "6e_initial_watch.valid.json"),
                "--packet",
                str(FIXTURES_DIR / "6e_update_wait.packet.valid.json"),
                "--evaluation-timestamp",
                "2026-01-14T15:10:00Z",
            ],
            "update",
            "ARMED_WAITING",
        ),
    ]

    seen_contracts: set[str] = set()
    for contract, args, mode, expected_state in cases:
        payload = _run_operator_surface(args)
        seen_contracts.add(contract)
        assert payload["mode"] == mode
        assert payload["contract"] == contract
        if mode == "replay":
            assert payload["validation_status"] == "VALID"
            assert payload["final_watch"]["state"] == expected_state
        else:
            assert payload["watch"]["state"] == expected_state

    assert seen_contracts == {"ZN", "ES", "NQ", "CL", "MGC", "6E"}

    print("readiness_v2_operator_smoke=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
