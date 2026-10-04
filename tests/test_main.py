"""Tests for the CLI: the catalog pin check and the engine-import boundary."""

import re
import subprocess
from pathlib import Path

import pytest

from sitegen.__main__ import build, main

ROOT = Path(__file__).resolve().parents[1]
SITEGEN = ROOT / "sitegen"
CHOCK_IMPORT = re.compile(r"^\s*(import chock|from chock)\b", re.MULTILINE)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_wrong_commit_refused(tmp_path: Path) -> None:
    repo = tmp_path / "catalog"
    repo.mkdir()
    _git(repo, "init")
    _git(
        repo,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "--allow-empty",
        "-m",
        "x",
    )
    with pytest.raises(SystemExit) as excinfo:
        build(repo, tmp_path / "out", "source", None)
    assert excinfo.value.code == 2


def test_missing_out_flag_fails() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--catalog", "x"])
    assert excinfo.value.code == 2


def test_only_engine_imports_chock() -> None:
    offenders = [
        path.name
        for path in SITEGEN.glob("*.py")
        if path.name != "engine.py"
        and CHOCK_IMPORT.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"chock imported outside engine.py: {offenders}"
