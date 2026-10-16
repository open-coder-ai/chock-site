"""CLI examples from real runs: data/cli-examples.yaml's session, recorded to data/cli-examples/.

Run `python -m sitegen.cliexamples --record` with chock installed at .framework-ref to
re-record, or `--check` to fail (exit 1) when a re-run prints something else or exits
with another code than the committed recording.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any

import yaml

from .pageparts import PageError

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCRIPT_YAML = "cli-examples.yaml"
OUT_DIR = "cli-examples"
SCHEMA_VERSION = 1
PROG = "chock"
TIME_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
TIME_WORD = "<time>"
STEP_TIMEOUT = 120


def load_script(data_dir: Path) -> dict[str, Any]:
    """data/cli-examples.yaml, refused unless every step runs chock and names a page."""
    script = yaml.safe_load((data_dir / SCRIPT_YAML).read_text(encoding="utf-8"))
    for step in script["steps"]:
        if set(step) != {"page", "run"} or step["run"][0] != PROG:
            raise PageError(f"{SCRIPT_YAML}: a step is {{page, run: [chock, ...]}}")
        if step["page"].split("/") != step["run"][1 : 1 + step["page"].count("/") + 1]:
            raise PageError(
                f"{SCRIPT_YAML}: page {step['page']!r} is not the command {step['run']}"
            )
    return script


def installed_commit() -> str:
    """The chock commit pip installed from git, or "" if chock was not installed that way."""
    try:
        raw = distribution("chock").read_text("direct_url.json") or "{}"
    except PackageNotFoundError:
        return ""
    return json.loads(raw).get("vcs_info", {}).get("commit_id", "")


def normalise(text: str, paths: dict[str, str]) -> str:
    """Output with the throwaway paths named as the script names them, times as <time>, no trailing spaces."""
    for real, shown in sorted(paths.items(), key=lambda p: -len(p[0])):
        text = text.replace(real, shown)
    text = TIME_RE.sub(TIME_WORD, text)
    return "\n".join(line.rstrip() for line in text.rstrip().splitlines())


def _paths(tmp: Path, script: dict[str, Any]) -> tuple[Path, Path, dict[str, str]]:
    """The repo and home folders under tmp, and each real spelling mapped to its shown path."""
    repo, home = tmp / "demo", tmp / "home"
    repo.mkdir()
    home.mkdir()
    shown = {}
    for real, name in ((repo, script["repo"]), (home, script["home"])):
        shown[str(real)] = name
        shown[str(real.resolve())] = name
    return repo, home, shown


def _env(home: Path) -> dict[str, str]:
    """A fixed environment: PATH from this process, and nothing else from it."""
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "COLUMNS": "100",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
    }


def _chock() -> str:
    """The chock console script installed beside this Python."""
    found = shutil.which(PROG, path=str(Path(sys.executable).parent))
    if found is None:
        raise PageError(f"no {PROG} script beside {sys.executable}: pip install chock")
    return found


def run_session(script: dict[str, Any], engine_ref: str) -> dict[str, dict[str, Any]]:
    """Each page's recording: every step run in order in one fresh repository."""
    chock = _chock()
    pages: dict[str, dict[str, Any]] = {}
    total = len(script["steps"])
    with tempfile.TemporaryDirectory(prefix="chock-cli-") as name:
        tmp = Path(name)
        repo, home, shown = _paths(tmp, script)
        env = _env(home)
        for argv in script["setup"]:
            subprocess.run(argv, cwd=repo, env=env, check=True, capture_output=True)
        for number, step in enumerate(script["steps"], start=1):
            done = subprocess.run(
                [chock, *step["run"][1:]],
                cwd=repo,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                timeout=STEP_TIMEOUT,
                check=False,
            )
            output = normalise(done.stdout, shown)
            if str(tmp) in output or str(tmp.resolve()) in output:
                raise PageError(f"step {number}: output names the throwaway folder")
            page = pages.setdefault(
                step["page"],
                {
                    "schema_version": SCHEMA_VERSION,
                    "engine": engine_ref,
                    "examples": [],
                },
            )
            page["examples"].append(
                {
                    "step": number,
                    "of": total,
                    "command": shlex.join(step["run"]),
                    "output": output,
                    "exit": done.returncode,
                }
            )
    return pages


def page_file(page: str) -> str:
    """The recording's file, relative to data/cli-examples/."""
    return f"{page}.json"


def render(page: dict[str, Any]) -> str:
    """A recording as committed JSON text."""
    return json.dumps(page, indent=2, ensure_ascii=False) + "\n"


def load(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Every committed recording, keyed by page ("bundle/status")."""
    folder = data_dir / OUT_DIR
    return {
        path.relative_to(folder).as_posix().removesuffix(".json"): json.loads(
            path.read_text(encoding="utf-8")
        )
        for path in sorted(folder.rglob("*.json"))
    }


def main(argv: list[str] | None = None) -> int:
    """Record the session into data/cli-examples/, or with --check report any difference."""
    parser = argparse.ArgumentParser(prog="python -m sitegen.cliexamples")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args(argv)
    ref = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
    installed = installed_commit()
    if installed != ref:
        print(
            f"installed chock is {installed or 'not from git'}, .framework-ref is {ref}",
            file=sys.stderr,
        )
        return 2
    try:
        pages = run_session(load_script(args.data), ref)
    except PageError as exc:
        print(exc, file=sys.stderr)
        return 2
    folder = args.data / OUT_DIR
    wanted = {page_file(page): render(data) for page, data in pages.items()}
    present = (
        {p.relative_to(folder).as_posix() for p in folder.rglob("*.json")}
        if folder.is_dir()
        else set()
    )
    if args.check:
        drift = sorted(
            name
            for name in set(wanted) | present
            if name not in wanted
            or name not in present
            or (folder / name).read_text(encoding="utf-8") != wanted[name]
        )
        if drift:
            print(
                "CLI examples differ from a re-run at .framework-ref: "
                + ", ".join(drift)
                + "\nrun: python -m sitegen.cliexamples --record",
                file=sys.stderr,
            )
            return 1
        print(f"CLI examples match chock {ref[:12]} ({len(wanted)} pages)")
        return 0
    for name in present - set(wanted):
        (folder / name).unlink()
    for name, text in wanted.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(wanted)} files to {folder.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
