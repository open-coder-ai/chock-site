"""Tests for the CLI: the catalog pin check and the engine-import boundary."""

import re
import subprocess
from pathlib import Path

import pytest

from sitegen.__main__ import MARKER, build, main

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


def test_out_repo_root_refused(catalog_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build(catalog_path, ROOT, "source", None)
    assert excinfo.value.code == 2


def test_out_home_refused(catalog_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build(catalog_path, Path.home(), "source", None)
    assert excinfo.value.code == 2


def test_out_filesystem_root_refused(catalog_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build(catalog_path, Path(ROOT.anchor), "source", None)
    assert excinfo.value.code == 2


def test_out_repo_ancestor_refused(catalog_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build(catalog_path, ROOT.parent, "source", None)
    assert excinfo.value.code == 2


def test_out_nonempty_without_marker_refused(
    catalog_path: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        build(catalog_path, out, "source", None)
    assert excinfo.value.code == 2
    assert (out / "keep.txt").read_text(encoding="utf-8") == "x"


def test_out_plain_file_refused(catalog_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        build(catalog_path, out, "source", None)
    assert excinfo.value.code == 2


def test_out_empty_dir_allowed(catalog_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    build(catalog_path, out, "source", None)
    assert (out / MARKER).is_file()
    assert (out / "data" / "site.json").is_file()


def test_out_with_marker_is_rebuilt(catalog_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / MARKER).write_text("", encoding="utf-8")
    (out / "stale.txt").write_text("x", encoding="utf-8")
    build(catalog_path, out, "source", None)
    assert not (out / "stale.txt").exists()
    assert (out / "data" / "site.json").is_file()


def test_only_engine_imports_chock() -> None:
    offenders = [
        path.name
        for path in SITEGEN.glob("*.py")
        if path.name != "engine.py"
        and CHOCK_IMPORT.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"chock imported outside engine.py: {offenders}"
