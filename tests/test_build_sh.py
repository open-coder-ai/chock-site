"""build.sh, the Cloudflare Pages build: pins are verified and it fails closed."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BUILD_SH = ROOT / "build.sh"
HEX40 = re.compile(r"[0-9a-f]{40}")
GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **GIT_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def source(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """A local catalog source: one commit, plus an annotated tag on it."""
    repo = tmp_path_factory.mktemp("catalog-source")
    _git(repo, "init", "-q")
    (repo / "README").write_text("catalog\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-q", "-m", "one")
    _git(repo, "tag", "-a", "v1", "-m", "tag")
    return {
        "url": repo.as_uri(),
        "commit": _git(repo, "rev-parse", "HEAD"),
        "tag": _git(repo, "rev-parse", "v1"),
    }


def _run(tmp_path: Path, catalog_ref: str, url: str) -> subprocess.CompletedProcess:
    """Run a copy of build.sh in tmp_path with the given .catalog-ref."""
    shutil.copy2(BUILD_SH, tmp_path / "build.sh")
    (tmp_path / ".framework-ref").write_text(
        (ROOT / ".framework-ref").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / ".catalog-ref").write_text(catalog_ref + "\n", encoding="utf-8")
    return subprocess.run(
        ["sh", str(tmp_path / "build.sh")],
        cwd=tmp_path,
        env={**os.environ, "CATALOG_URL": url, "PYTHON": sys.executable},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_build_sh_is_posix_sh_with_set_eu() -> None:
    text = BUILD_SH.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "#!/bin/sh"
    assert "set -eu" in lines
    # Only its own variables and three source overrides; no credential is read.
    names = set(re.findall(r"\$\{?([A-Za-z_]\w*)", text))
    assert names == {
        "ENGINE_URL",
        "CATALOG_URL",
        "PYTHON",
        "FRAMEWORK_REF",
        "CATALOG_REF",
        "pin",
        "work",
        "head",
    }
    subprocess.run(["sh", "-n", str(BUILD_SH)], check=True)


def test_build_sh_reads_both_pins_and_build_requirements() -> None:
    text = BUILD_SH.read_text(encoding="utf-8")
    assert "read_pin .framework-ref" in text
    assert "read_pin .catalog-ref" in text
    assert "-r requirements-build.txt" in text
    assert "--out dist" in text
    for name in (".framework-ref", ".catalog-ref"):
        assert HEX40.fullmatch((ROOT / name).read_text(encoding="utf-8").strip())


def test_build_requirements_are_pinned() -> None:
    rows = (ROOT / "requirements-build.txt").read_text(encoding="utf-8").split()
    assert rows
    for row in rows:
        assert re.fullmatch(r"[\w.-]+==[\w.]+", row), row
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    assert "-r requirements-build.txt" in dev


def test_ci_runs_build_sh() -> None:
    flow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    runs = [step.get("run", "") for step in flow["jobs"]["build"]["steps"]]
    assert "sh build.sh" in runs


@pytest.mark.parametrize(
    "pin",
    ["d141a72", "D141A72AE775DB4C674D4D8231D5838EAA4D9B88", "main", "", "a" * 41],
)
def test_malformed_catalog_pin_fails(tmp_path: Path, source, pin: str) -> None:
    result = _run(tmp_path, pin, source["url"])
    assert result.returncode != 0
    assert ".catalog-ref is not a full" in result.stderr
    assert not (tmp_path / "dist").exists()


def test_missing_catalog_commit_fails(tmp_path: Path, source) -> None:
    result = _run(tmp_path, "0" * 40, source["url"])
    assert result.returncode != 0
    assert "cannot fetch catalog commit" in result.stderr
    assert not (tmp_path / "dist").exists()


def test_catalog_head_mismatch_fails_closed(tmp_path: Path, source) -> None:
    # An annotated tag's object id is 40-hex and fetchable, but checks out its commit.
    result = _run(tmp_path, source["tag"], source["url"])
    assert result.returncode != 0
    assert (
        f"catalog HEAD is {source['commit']}, expected {source['tag']}" in result.stderr
    )
    assert not (tmp_path / "dist").exists()
