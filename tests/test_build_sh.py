"""build.sh, the Cloudflare Pages build: pins are verified and it fails closed."""

import importlib.util
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
    assert "--require-hashes -r requirements-build.txt" in text
    assert "--no-deps --no-build-isolation" in text
    assert "pip check" in text or "venv_pip check" in text
    assert "--out dist" in text
    for name in (".framework-ref", ".catalog-ref"):
        assert HEX40.fullmatch((ROOT / name).read_text(encoding="utf-8").strip())


LOCKS = ("build", "dev", "workflows")
PIN = re.compile(r"^([A-Za-z0-9][\w.-]*)==([\w.]+)")


def _locked(name: str) -> dict[str, list[str]]:
    """Return {package: [hash, ...]} from requirements-<name>.txt."""
    text = (ROOT / f"requirements-{name}.txt").read_text(encoding="utf-8")
    pins: dict[str, list[str]] = {}
    current = ""
    for line in text.replace("\\\n", " ").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = PIN.match(line)
        assert match, f"requirements-{name}.txt: not a == pin: {line}"
        current = f"{match[1].lower().replace('_', '-')}=={match[2]}"
        pins[current] = re.findall(r"--hash=sha256:([0-9a-f]{64})", line)
    return pins


@pytest.mark.parametrize("name", LOCKS)
def test_lock_pins_every_package_by_hash(name: str) -> None:
    pins = _locked(name)
    assert pins
    for pin, hashes in pins.items():
        assert hashes, f"requirements-{name}.txt: {pin} has no sha256 hash"


@pytest.mark.parametrize("name", LOCKS)
def test_lock_matches_its_input(name: str) -> None:
    pins = set(_locked(name))
    for line in (ROOT / f"requirements-{name}.in").read_text("utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-r "):
            continue
        match = PIN.match(line)
        assert match, f"requirements-{name}.in: not a == pin: {line}"
        assert f"{match[1].lower().replace('_', '-')}=={match[2]}" in pins, line


def test_dev_lock_includes_the_build_lock() -> None:
    assert set(_locked("build")) <= set(_locked("dev"))


INSTALLERS = (
    "build.sh",
    ".github/workflows/ci.yml",
    "scripts/local-test.sh",
    "scripts/local-test.ps1",
    "README.md",
)


@pytest.mark.parametrize("path", INSTALLERS)
def test_every_pip_install_is_hash_checked_or_engine_only(path: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    calls = re.findall(r'pip"?,? +"?install\b"?(.*)', text)
    assert calls, path
    for call in calls:
        if "--require-hashes" in call:
            continue
        # The engine at its pinned commit, with nothing pulled from PyPI.
        assert "--no-deps" in call and "--no-build-isolation" in call, call
        assert "chock @ git+" in call or call.rstrip().endswith(","), call


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


def _engine_deps():
    """Load scripts/install_engine_deps.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "install_engine_deps", ROOT / "scripts" / "install_engine_deps.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_engine_git_pins_are_installed_without_deps() -> None:
    for path in ("build.sh", "scripts/local-test.sh", "scripts/local-test.ps1"):
        assert "scripts/install_engine_deps.py" in (ROOT / path).read_text("utf-8"), (
            path
        )
    flow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    for job in ("unit", "e2e"):
        runs = [step.get("run", "") for step in flow["jobs"][job]["steps"]]
        engine = next(i for i, r in enumerate(runs) if "chock @ git+" in r)
        assert runs[engine + 1] == "python scripts/install_engine_deps.py", job
    text = (ROOT / "scripts" / "install_engine_deps.py").read_text(encoding="utf-8")
    assert '"--no-deps",' in text and '"--no-build-isolation",' in text


@pytest.mark.parametrize("sep", [" @ ", "@ ", "@"])
def test_engine_git_pins_keep_only_commit_pinned_sources(sep: str) -> None:
    url = "git+https://github.com/open-coder-ai/agentseam@" + "b" * 40
    requires = [
        "pyyaml>=6.0",
        f"agentseam{sep}{url}",
        'pytest>=7; extra == "dev"',
    ]
    assert _engine_deps().git_pins(requires) == [f"agentseam @ {url}"]


@pytest.mark.parametrize(
    "req",
    [
        "agentseam @ git+https://github.com/open-coder-ai/agentseam@main",
        "agentseam @ git+https://github.com/open-coder-ai/agentseam@" + "B" * 40,
        "agentseam @ git+https://github.com/someone-else/agentseam@" + "b" * 40,
        "agentseam @ git+http://github.com/open-coder-ai/agentseam@" + "b" * 40,
        "agentseam @ https://example.invalid/agentseam.tar.gz",
        "agentseam @ git+https://github.com/open-coder-ai/agentseam@"
        + "b" * 40
        + ' ; python_version >= "3.9"',
    ],
)
def test_engine_git_pins_refuse_loose_sources(req: str) -> None:
    with pytest.raises(SystemExit):
        _engine_deps().git_pins([req])
