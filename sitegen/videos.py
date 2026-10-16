"""DOCS-6 videos: each videos/<name>.tape, the MP4 and poster VHS rendered from it, and their sidecar.

After `vhs videos/<name>.tape`, run `python -m sitegen.videos --sidecar <name> --engine <sha>`
to write static/video/<name>.json: the sha256 of the tape it was rendered from, of the MP4 and
of the poster, the MP4's size, and the engine and catalog commits it ran. `--check` exits 1
when a tape changed without a re-render, a file is missing or changed, or an MP4 is over
MAX_BYTES. The pages list each tape's shown commands from the tape itself.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TAPES = "videos"
STATIC = "static/video"
SITE_PREFIX = "/video/"
MAX_BYTES = 3_000_000
SCHEMA_VERSION = 1
# A VHS string argument: "...", '...' or `...`, with no escapes inside.
ARG_RE = re.compile(r"""^(\w+)(?:\s+(?:"([^"]*)"|'([^']*)'|`([^`]*)`|(\S+)))?""")
HEREDOC_RE = re.compile(r"<<'(\w+)'$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tape_files(tape: str) -> dict[str, str]:
    """The tape's Output and Screenshot paths, relative to the repository."""
    found = {}
    for line in tape.splitlines():
        match = ARG_RE.match(line.strip())
        if match and match.group(1) in ("Output", "Screenshot"):
            value = next(g for g in match.groups()[1:] if g is not None)
            found["mp4" if match.group(1) == "Output" else "poster"] = value
    return found


def shown_commands(tape: str) -> list[str]:
    """What the video shows being typed, one line per Enter, Hide..Show and `clear` left out.

    A command line starts with "$ "; the lines a here-document reads, and its end word, do not.
    """
    lines: list[str] = []
    hidden = False
    typed = ""
    heredoc = None
    for raw in tape.splitlines():
        match = ARG_RE.match(raw.strip())
        if not match:
            continue
        word = match.group(1)
        if word == "Hide":
            hidden = True
        elif word == "Show":
            hidden = False
        elif word == "Type" and not hidden:
            typed += next(g for g in match.groups()[1:] if g is not None)
        elif word == "Enter" and not hidden:
            if heredoc is not None:
                lines.append(typed)
                if typed == heredoc:
                    heredoc = None
            elif typed != "clear":
                lines.append(f"$ {typed}")
                end = HEREDOC_RE.search(typed)
                heredoc = end.group(1) if end else None
            typed = ""
    return lines


def _probe(mp4: Path) -> dict[str, Any]:
    """The MP4's width, height and duration, as ffprobe reads them."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration",
            "-of",
            "json",
            str(mp4),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    data = json.loads(out)
    seconds = round(float(data["format"]["duration"]))
    return {
        "width": data["streams"][0]["width"],
        "height": data["streams"][0]["height"],
        "duration": f"{seconds // 60}:{seconds % 60:02d}",
    }


def sidecar(root: Path, name: str, engine: str, catalog: str | None) -> dict[str, Any]:
    """The sidecar record for a freshly rendered video."""
    tape_path = root / TAPES / f"{name}.tape"
    files = tape_files(tape_path.read_text(encoding="utf-8"))
    mp4, poster = root / files["mp4"], root / files["poster"]
    vhs = subprocess.run(
        ["vhs", "--version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "tape": f"{TAPES}/{name}.tape",
        "tape_sha256": _sha256(tape_path),
        "mp4": files["mp4"],
        "mp4_sha256": _sha256(mp4),
        "mp4_bytes": mp4.stat().st_size,
        "poster": files["poster"],
        "poster_sha256": _sha256(poster),
        **_probe(mp4),
        "engine": engine,
        "catalog": catalog,
        "vhs": vhs,
    }


def load(root: Path, name: str) -> dict[str, Any]:
    """A video's committed sidecar."""
    return json.loads((root / STATIC / f"{name}.json").read_text(encoding="utf-8"))


def site_path(path: str) -> str:
    """A static/video/ file as the site serves it."""
    return SITE_PREFIX + path.removeprefix(STATIC + "/")


def check(root: Path) -> list[str]:
    """Every problem with the committed videos: a tape changed since its render, a file missing or changed, an MP4 too big."""
    problems = []
    tapes = sorted((root / TAPES).glob("*.tape"))
    names = {t.stem for t in tapes}
    for extra in sorted((root / STATIC).glob("*.json")):
        if extra.stem not in names:
            problems.append(f"{extra.relative_to(root)}: no videos/{extra.stem}.tape")
    for tape in tapes:
        name = tape.stem
        side = root / STATIC / f"{name}.json"
        if not side.is_file():
            problems.append(f"{name}: no {STATIC}/{name}.json; render the tape and run --sidecar")
            continue
        record = load(root, name)
        files = tape_files(tape.read_text(encoding="utf-8"))
        if files != {"mp4": f"{STATIC}/{name}.mp4", "poster": f"{STATIC}/{name}.png"}:
            problems.append(f"{name}: the tape must write {STATIC}/{name}.mp4 and .png, not {files}")
            continue
        if record["tape_sha256"] != _sha256(tape):
            problems.append(f"{name}: the tape changed since the video was rendered; re-render it")
        for key in ("mp4", "poster"):
            path = root / record[key]
            if record[key] != files[key] or not path.is_file():
                problems.append(f"{name}: {record[key]} is missing")
            elif record[f"{key}_sha256"] != _sha256(path):
                problems.append(f"{name}: {record[key]} is not the file the sidecar records")
        mp4 = root / files["mp4"]
        if mp4.is_file() and mp4.stat().st_size > MAX_BYTES:
            problems.append(f"{name}: {files['mp4']} is {mp4.stat().st_size} B, over {MAX_BYTES} B")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Write one video's sidecar, or with --check report every problem."""
    parser = argparse.ArgumentParser(prog="python -m sitegen.videos")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sidecar", metavar="NAME")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--engine", help="the chock commit the tape ran (default: .framework-ref)")
    parser.add_argument("--catalog", help="the chock-catalog commit the tape ran, if any")
    args = parser.parse_args(argv)
    if args.check:
        problems = check(ROOT)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return 1
        count = len(list((ROOT / TAPES).glob("*.tape")))
        print(f"{count} videos match their tapes, each at most {MAX_BYTES} B")
        return 0
    engine = args.engine or (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
    record = sidecar(ROOT, args.sidecar, engine, args.catalog)
    target = ROOT / STATIC / f"{args.sidecar}.json"
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
