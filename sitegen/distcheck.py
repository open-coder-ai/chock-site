"""Fail when a built site shows a path with Windows separators, so every OS builds the same site."""

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Page text: a backslash between two name characters (`a\b`, `~\.chock`).
PAGE_PATH = re.compile(r"[\w~.-]\\[\w.-]")
# JSON values also hold escapes and regexes, so only home, dot-folder and drive paths count.
DATA_PATH = re.compile(r"~\\|\\\.chock|\b[A-Za-z]:\\\w")
PAGE_SUFFIXES = (".html", ".md", ".txt")


def _strings(value: Any) -> Iterator[str]:
    """Every string inside a decoded JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def find(site: Path) -> list[str]:
    """Each file under `site` that shows a Windows-style path, with the matching text."""
    found = []
    for path in sorted(site.rglob("*")):
        if path.suffix in PAGE_SUFFIXES:
            texts, pattern = [path.read_text(encoding="utf-8")], PAGE_PATH
        elif path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            texts, pattern = list(_strings(data)), DATA_PATH
        else:
            continue
        for text in texts:
            match = pattern.search(text)
            if match:
                start = max(match.start() - 30, 0)
                snippet = text[start : match.end() + 30]
                found.append(f"{path.relative_to(site).as_posix()}: {snippet!r}")
                break
    return found


def main(argv: list[str]) -> int:
    """Check the site folder named on the command line; exit 1 if any path leaked."""
    if len(argv) != 1:
        print("usage: python -m sitegen.distcheck <site-folder>", file=sys.stderr)
        return 2
    found = find(Path(argv[0]))
    for line in found:
        print(f"Windows-style path in {line}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
