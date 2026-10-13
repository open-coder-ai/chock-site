"""The docs prose snapshot: chock doc sections at .framework-ref, copied into data/ and checked for drift.

Run `python -m sitegen.docsource --chock <chock checkout at .framework-ref>` to regenerate,
or add `--check` to fail (exit 1) when the committed snapshot differs.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from .docsmd import first_sections, sections
from .pageparts import PageError

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS_YAML = "docs.yaml"
SOURCE_JSON = "source.json"


def load_docs(data_dir: Path) -> dict[str, Any]:
    """data/docs.yaml."""
    return yaml.safe_load((data_dir / DOCS_YAML).read_text(encoding="utf-8"))


def wanted(docs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per chock file: the section titles every page quotes, or how many leading sections."""
    files: dict[str, dict[str, Any]] = {}
    # The overview's path tabs quote code blocks from engine docs too.
    tabs = [
        part
        for path in docs["texts"]["paths"]
        for part in path["tab"]
        if isinstance(part, dict)
    ]
    for page in [*docs["pages"].values(), {"prose": tabs}]:
        for entry in page["prose"]:
            want = files.setdefault(
                entry["file"],
                {"sections": [], "first": 0, "optional": entry.get("optional", False)},
            )
            for title in entry.get("sections", []):
                if title not in want["sections"]:
                    want["sections"].append(title)
            want["first"] = max(want["first"], entry.get("first", 0))
    return files


def snapshot_name(path: str) -> str:
    """The snapshot file a chock path is stored in."""
    return path.replace("/", "__")


def extract(text: str, want: dict[str, Any]) -> str:
    """The quoted part of one chock file: its leading sections, or the named ones."""
    if want["first"]:
        return first_sections(text, want["first"])
    return sections(text, want["sections"])


def snapshot(chock: Path, docs: dict[str, Any], ref: str) -> dict[str, str]:
    """Every snapshot file's text, keyed by name, plus source.json, read from a checkout."""
    files: dict[str, str] = {}
    record: dict[str, Any] = {"engine_ref": ref, "files": {}}
    for path, want in sorted(wanted(docs).items()):
        source = chock / path
        if not source.is_file():
            if want["optional"]:
                record["files"][path] = None
                continue
            raise PageError(f"{path}: not in the chock checkout at {ref}")
        name = snapshot_name(path)
        files[name] = extract(source.read_text(encoding="utf-8"), want)
        record["files"][path] = {"snapshot": name}
    files[SOURCE_JSON] = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    return files


def load(data_dir: Path, ref: str) -> dict[str, str | None]:
    """Each quoted chock file's snapshot text (None for an absent optional file).

    Refuses a snapshot taken at another engine commit than .framework-ref.
    """
    docs = load_docs(data_dir)
    folder = data_dir / docs["source_dir"]
    record = json.loads((folder / SOURCE_JSON).read_text(encoding="utf-8"))
    if record["engine_ref"] != ref:
        raise PageError(
            f"{docs['source_dir']}/{SOURCE_JSON} was taken at engine "
            f"{record['engine_ref']}, but .framework-ref is {ref}: run "
            "python -m sitegen.docsource --chock <chock checkout at .framework-ref>"
        )
    want = wanted(docs)
    if sorted(record["files"]) != sorted(want):
        raise PageError(
            f"{docs['source_dir']}/{SOURCE_JSON} lists {sorted(record['files'])}, "
            f"docs.yaml quotes {sorted(want)}: regenerate the snapshot"
        )
    return {
        path: None
        if entry is None
        else (folder / entry["snapshot"]).read_text(encoding="utf-8")
        for path, entry in record["files"].items()
    }


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    """Write the snapshot from a chock checkout, or with --check report any drift."""
    parser = argparse.ArgumentParser(prog="python -m sitegen.docsource")
    parser.add_argument("--chock", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args(argv)
    ref = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
    head = _head(args.chock)
    if head != ref:
        print(f"{args.chock}: HEAD is {head}, .framework-ref is {ref}", file=sys.stderr)
        return 2
    docs = load_docs(args.data)
    try:
        files = snapshot(args.chock, docs, ref)
    except PageError as exc:
        print(exc, file=sys.stderr)
        return 2
    folder = args.data / docs["source_dir"]
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
            print(
                "docs snapshot drifts from chock at .framework-ref: "
                + ", ".join(drift)
                + "\nrun: python -m sitegen.docsource --chock <checkout>",
                file=sys.stderr,
            )
            return 1
        print(f"docs snapshot matches chock {ref[:12]} ({len(files) - 1} files)")
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    for name in present - set(files):
        (folder / name).unlink()
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(files)} files to {folder.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
