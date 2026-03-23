from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "readiness_v2"


def _run_operator_surface(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    pythonpath_entries = [str(REPO_ROOT / "src")]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return subprocess.run(
        [sys.executable, "-m", "ninjatradebuilder.readiness_v2", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _load_fixture_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_readiness_v2_operator_surface_help_is_clean() -> None:
    result = _run_operator_surface(["--help"])

    assert result.returncode == 0
    assert result.stderr == ""
    assert "python -m ninjatradebuilder.readiness_v2" in result.stdout
    assert "bootstrap" in result.stdout
    assert "update" in result.stdout
    assert "replay" in result.stdout


@pytest.mark.parametrize("mode", ["bootstrap", "update", "replay"])
def test_readiness_v2_operator_surface_subcommand_help_lists_all_supported_contracts(
    mode: str,
) -> None:
    result = _run_operator_surface([mode, "--help"])

    assert result.returncode == 0
    assert result.stderr == ""
    assert "6E" in result.stdout
    assert "CL" in result.stdout
    assert "ES" in result.stdout
    assert "MGC" in result.stdout
    assert "NQ" in result.stdout
    assert "ZN" in result.stdout


@pytest.mark.parametrize(
    ("args", "expected_name"),
    [
        (
            [
                "bootstrap",
                "--packet",
                str(FIXTURES_DIR / "zn_bootstrap.packet.valid.json"),
            ],
            "zn_bootstrap.expected.json",
        ),
        (
            [
                "bootstrap",
                "--packet",
                str(FIXTURES_DIR / "es_bootstrap.packet.valid.json"),
            ],
            "es_bootstrap.expected.json",
        ),
        (
            [
                "bootstrap",
                "--packet",
                str(FIXTURES_DIR / "nq_bootstrap.packet.valid.json"),
            ],
            "nq_bootstrap.expected.json",
        ),
        (
            [
                "bootstrap",
                "--packet",
                str(FIXTURES_DIR / "cl_bootstrap.packet.valid.json"),
            ],
            "cl_bootstrap.expected.json",
        ),
        (
            [
                "bootstrap",
                "--packet",
                str(FIXTURES_DIR / "mgc_bootstrap.packet.valid.json"),
            ],
            "mgc_bootstrap.expected.json",
        ),
        (
            [
                "bootstrap",
                "--packet",
                str(FIXTURES_DIR / "6e_bootstrap.packet.valid.json"),
            ],
            "6e_bootstrap.expected.json",
        ),
        (
            [
                "update",
                "--prior-watch",
                str(FIXTURES_DIR / "zn_initial_watch.valid.json"),
                "--packet",
                str(FIXTURES_DIR / "zn_update_wait.packet.valid.json"),
                "--evaluation-timestamp",
                "2026-01-14T15:10:00Z",
            ],
            "zn_update_wait.expected.json",
        ),
        (
            [
                "update",
                "--prior-watch",
                str(FIXTURES_DIR / "es_initial_watch.valid.json"),
                "--packet",
                str(FIXTURES_DIR / "es_update_wait.packet.valid.json"),
                "--evaluation-timestamp",
                "2026-01-14T15:10:00Z",
            ],
            "es_update_wait.expected.json",
        ),
        (
            [
                "update",
                "--prior-watch",
                str(FIXTURES_DIR / "nq_initial_watch.valid.json"),
                "--packet",
                str(FIXTURES_DIR / "nq_update_wait.packet.valid.json"),
                "--evaluation-timestamp",
                "2026-01-14T15:10:00Z",
            ],
            "nq_update_wait.expected.json",
        ),
        (
            [
                "update",
                "--prior-watch",
                str(FIXTURES_DIR / "cl_initial_watch.valid.json"),
                "--packet",
                str(FIXTURES_DIR / "cl_update_wait.packet.valid.json"),
                "--evaluation-timestamp",
                "2026-01-14T15:10:00Z",
            ],
            "cl_update_wait.expected.json",
        ),
        (
            [
                "update",
                "--prior-watch",
                str(FIXTURES_DIR / "mgc_initial_watch.valid.json"),
                "--packet",
                str(FIXTURES_DIR / "mgc_update_wait.packet.valid.json"),
                "--evaluation-timestamp",
                "2026-01-14T15:10:00Z",
            ],
            "mgc_update_wait.expected.json",
        ),
        (
            [
                "update",
                "--prior-watch",
                str(FIXTURES_DIR / "6e_initial_watch.valid.json"),
                "--packet",
                str(FIXTURES_DIR / "6e_update_wait.packet.valid.json"),
                "--evaluation-timestamp",
                "2026-01-14T15:10:00Z",
            ],
            "6e_update_wait.expected.json",
        ),
        (
            [
                "replay",
                "--packet",
                str(FIXTURES_DIR / "zn_bootstrap.packet.valid.json"),
                "--updates",
                str(FIXTURES_DIR / "zn_replay.updates.valid.json"),
            ],
            "zn_replay.expected.json",
        ),
        (
            [
                "replay",
                "--packet",
                str(FIXTURES_DIR / "es_bootstrap.packet.valid.json"),
                "--updates",
                str(FIXTURES_DIR / "es_replay.updates.valid.json"),
            ],
            "es_replay.expected.json",
        ),
        (
            [
                "replay",
                "--packet",
                str(FIXTURES_DIR / "nq_bootstrap.packet.valid.json"),
                "--updates",
                str(FIXTURES_DIR / "nq_replay.updates.valid.json"),
            ],
            "nq_replay.expected.json",
        ),
        (
            [
                "replay",
                "--packet",
                str(FIXTURES_DIR / "cl_bootstrap.packet.valid.json"),
                "--updates",
                str(FIXTURES_DIR / "cl_replay.updates.valid.json"),
            ],
            "cl_replay.expected.json",
        ),
        (
            [
                "replay",
                "--packet",
                str(FIXTURES_DIR / "mgc_bootstrap.packet.valid.json"),
                "--updates",
                str(FIXTURES_DIR / "mgc_replay.updates.valid.json"),
            ],
            "mgc_replay.expected.json",
        ),
        (
            [
                "replay",
                "--packet",
                str(FIXTURES_DIR / "6e_bootstrap.packet.valid.json"),
                "--updates",
                str(FIXTURES_DIR / "6e_replay.updates.valid.json"),
            ],
            "6e_replay.expected.json",
        ),
    ],
)
def test_readiness_v2_operator_surface_matches_existing_golden_artifacts(
    args: list[str],
    expected_name: str,
) -> None:
    result = _run_operator_surface(args)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == _load_fixture_json(expected_name)


def test_readiness_v2_operator_surface_fails_closed_on_unsupported_contract(
    tmp_path: Path,
) -> None:
    bundle_path = tmp_path / "packets.bundle.json"
    bundle_path.write_text(json.dumps(_load_fixture_json("../packets.valid.json"), indent=2, sort_keys=True))
    result = _run_operator_surface(
        [
            "bootstrap",
            "--packet",
            str(bundle_path),
            "--contract",
            "GC",
        ]
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "invalid choice" in result.stderr
