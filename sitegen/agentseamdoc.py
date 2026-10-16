"""agentseam docs sources: prose quoted from agentseam at its pinned commit, and a recorded direct run.

`python -m sitegen.agentseamdoc snapshot --agentseam <checkout>` copies the quoted sections of
agentseam's docs into data/agentseam-source/; add `--check` to fail (exit 1) when they drift.
`python -m sitegen.agentseamdoc run --record` runs data/agentseam-run.yaml with the installed
agentseam and writes data/agentseam-run.json; `run --check` fails when a re-run differs.
Both refuse an agentseam commit other than the one data/agentseam-source/source.json pins.
"""

import argparse
import difflib
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from . import engine
from .cliexamples import STEP_TIMEOUT, _env, normalise
from .docsmd import sections
from .docsource import load_docs
from .pageparts import PageError

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE_JSON = "source.json"
SCHEMA_VERSION = 1
PROGRAMS = ("agentseam", "python3", "cat")


def config(data_dir: Path) -> dict[str, Any]:
    """The `agentseam` block of data/docs.yaml."""
    return load_docs(data_dir)["agentseam"]


def pinned(data_dir: Path) -> str:
    """The agentseam commit the snapshot was taken at, which the pages document."""
    folder = data_dir / config(data_dir)["source_dir"]
    return json.loads((folder / SOURCE_JSON).read_text(encoding="utf-8"))[
        "agentseam_ref"
    ]


def snapshot_name(path: str) -> str:
    """The snapshot file an agentseam path is stored in."""
    return path.replace("/", "__")


def extract(text: str, quote: dict[str, Any]) -> str:
    """The quoted part of one agentseam file: the named sections, or all of it."""
    if quote.get("whole"):
        return text
    quoted = sections(text, quote["sections"], quote.get("level", 2))
    if quote.get("heading", True):
        return quoted
    return quoted.split("\n", 1)[1].lstrip("\n")


def snapshot(checkout: Path, cfg: dict[str, Any], ref: str) -> dict[str, str]:
    """Every snapshot file's text, keyed by name, plus source.json, read from a checkout."""
    files: dict[str, str] = {}
    record: dict[str, Any] = {"agentseam_ref": ref, "files": {}}
    for quote in cfg["quotes"]:
        source = checkout / quote["file"]
        if not source.is_file():
            raise PageError(f"{quote['file']}: not in the agentseam checkout at {ref}")
        name = snapshot_name(quote["file"])
        files[name] = extract(source.read_text(encoding="utf-8"), quote)
        record["files"][quote["file"]] = {"snapshot": name}
    files[SOURCE_JSON] = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    return files


def load(data_dir: Path) -> dict[str, str]:
    """Each quoted agentseam file's snapshot text, keyed by its path in agentseam."""
    cfg = config(data_dir)
    folder = data_dir / cfg["source_dir"]
    record = json.loads((folder / SOURCE_JSON).read_text(encoding="utf-8"))
    want = sorted(q["file"] for q in cfg["quotes"])
    if sorted(record["files"]) != want:
        raise PageError(
            f"{cfg['source_dir']}/{SOURCE_JSON} lists {sorted(record['files'])}, "
            f"docs.yaml quotes {want}: run python -m sitegen.agentseamdoc snapshot"
        )
    return {
        path: (folder / entry["snapshot"]).read_text(encoding="utf-8")
        for path, entry in record["files"].items()
    }


def load_script(data_dir: Path) -> dict[str, Any]:
    """The direct-run script, refused unless each step runs a program it allows."""
    cfg = config(data_dir)
    script = yaml.safe_load((data_dir / cfg["run_script"]).read_text(encoding="utf-8"))
    for step in script["steps"]:
        if not set(step) <= {"run", "stdin"} or step["run"][0] not in PROGRAMS:
            raise PageError(
                f"{cfg['run_script']}: a step is {{run: [{'|'.join(PROGRAMS)}, ...]}}"
                " with an optional stdin file"
            )
        if step.get("stdin") and step["stdin"] not in script["files"]:
            raise PageError(f"{cfg['run_script']}: stdin {step['stdin']!r} is no file")
    return script


def shown_command(step: dict[str, Any]) -> str:
    """A step as a line to type: its argv, then `< file` when it reads stdin from one."""
    line = shlex.join(step["run"])
    return f"{line} < {step['stdin']}" if step.get("stdin") else line


def _program(name: str) -> str:
    """The program beside this Python (agentseam, python3), else the one on PATH (cat)."""
    found = shutil.which(name, path=str(Path(sys.executable).parent)) or shutil.which(
        name
    )
    if found is None:
        raise PageError(f"no {name} on PATH or beside {sys.executable}")
    return found


def run_session(script: dict[str, Any], ref: str) -> dict[str, Any]:
    """The recording: every step run in order in one fresh repository."""
    total = len(script["steps"])
    examples = []
    with tempfile.TemporaryDirectory(prefix="agentseam-run-") as name:
        tmp = Path(name)
        repo, home = tmp / "demo", tmp / "home"
        repo.mkdir()
        home.mkdir()
        shown = {}
        for real, label in ((repo, script["repo"]), (home, script["home"])):
            shown[str(real)] = label
            shown[str(real.resolve())] = label
        env = _env(home)
        for argv in script["setup"]:
            subprocess.run(argv, cwd=repo, env=env, check=True, capture_output=True)
        for file, text in script["files"].items():
            (repo / file).write_text(text, encoding="utf-8", newline="\n")
        for number, step in enumerate(script["steps"], start=1):
            stdin = (repo / step["stdin"]).open("rb") if step.get("stdin") else None
            try:
                done = subprocess.run(
                    [_program(step["run"][0]), *step["run"][1:]],
                    cwd=repo,
                    env=env,
                    stdin=stdin or subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=STEP_TIMEOUT,
                    check=False,
                )
            finally:
                if stdin is not None:
                    stdin.close()
            output = normalise(done.stdout.decode("utf-8"), shown)
            if str(tmp) in output or str(tmp.resolve()) in output:
                raise PageError(f"step {number}: output names the throwaway folder")
            examples.append(
                {
                    "step": number,
                    "of": total,
                    "command": shown_command(step),
                    "output": output,
                    "exit": done.returncode,
                }
            )
    return {"schema_version": SCHEMA_VERSION, "agentseam": ref, "examples": examples}


def render(recording: dict[str, Any]) -> str:
    """A recording as committed JSON text."""
    return json.dumps(recording, indent=2, ensure_ascii=False) + "\n"


def load_run(data_dir: Path) -> dict[str, Any]:
    """The committed recording of the direct run."""
    path = data_dir / config(data_dir)["run_record"]
    return json.loads(path.read_text(encoding="utf-8"))


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _diff(name: str, committed: str, fresh: str) -> None:
    sys.stderr.writelines(
        difflib.unified_diff(
            committed.splitlines(keepends=True),
            fresh.splitlines(keepends=True),
            f"committed/{name}",
            f"fresh/{name}",
        )
    )


def _snapshot_main(args: argparse.Namespace) -> int:
    ref = pinned(args.data)
    head = _head(args.agentseam)
    if head != ref:
        print(
            f"{args.agentseam}: HEAD is {head}, the snapshot pins {ref}",
            file=sys.stderr,
        )
        return 2
    cfg = config(args.data)
    try:
        files = snapshot(args.agentseam, cfg, ref)
    except PageError as exc:
        print(exc, file=sys.stderr)
        return 2
    folder = args.data / cfg["source_dir"]
    present = {p.name for p in folder.glob("*")} if folder.is_dir() else set()
    if args.check:
        drift = sorted(
            name
            for name in set(files) | present
            if name not in files
            or name not in present
            or (folder / name).read_text(encoding="utf-8") != files[name]
        )
        if drift:
            for name in drift:
                old = (
                    (folder / name).read_text(encoding="utf-8")
                    if name in present
                    else ""
                )
                _diff(name, old, files.get(name, ""))
            print(
                "agentseam snapshot drifts from agentseam at "
                f"{ref[:12]}: {', '.join(drift)}\n"
                "run: python -m sitegen.agentseamdoc snapshot --agentseam <checkout>",
                file=sys.stderr,
            )
            return 1
        print(f"agentseam snapshot matches {ref[:12]} ({len(files) - 1} files)")
        return 0
    for name in present - set(files):
        (folder / name).unlink()
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(files)} files to {folder.relative_to(ROOT)}")
    return 0


def _run_main(args: argparse.Namespace) -> int:
    ref = pinned(args.data)
    installed = engine.agentseam_commit()
    if installed != ref:
        print(
            f"installed agentseam is {installed or 'not from git'}, the snapshot pins {ref}",
            file=sys.stderr,
        )
        return 2
    try:
        fresh = render(run_session(load_script(args.data), ref))
    except PageError as exc:
        print(exc, file=sys.stderr)
        return 2
    target = args.data / config(args.data)["run_record"]
    if args.check:
        committed = target.read_text(encoding="utf-8") if target.is_file() else ""
        if committed != fresh:
            _diff(target.name, committed, fresh)
            print(
                f"{target.name} differs from a re-run at agentseam {ref[:12]}\n"
                "run: python -m sitegen.agentseamdoc run --record",
                file=sys.stderr,
            )
            return 1
        print(
            f"agentseam run matches {ref[:12]} ({len(json.loads(fresh)['examples'])} steps)"
        )
        return 0
    target.write_text(fresh, encoding="utf-8", newline="\n")
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Write or check the prose snapshot, or record or check the direct run."""
    parser = argparse.ArgumentParser(prog="python -m sitegen.agentseamdoc")
    parser.add_argument("--data", type=Path, default=DATA)
    sub = parser.add_subparsers(dest="mode", required=True)
    snap = sub.add_parser("snapshot", help="quoted agentseam docs, from a checkout")
    snap.add_argument("--agentseam", required=True, type=Path)
    snap.add_argument("--check", action="store_true")
    run = sub.add_parser("run", help="the direct run, with the installed agentseam")
    mode = run.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return _snapshot_main(args) if args.mode == "snapshot" else _run_main(args)


if __name__ == "__main__":
    sys.exit(main())
