"""The author page's data: interview copy, the copied kind templates and their edit plans (BV-S2)."""

import json
from pathlib import Path
from typing import Any

import yaml

from .pageparts import PageError

AUTHOR_YAML = "author.yaml"
KINDS_DIR = "kinds"
ENGINE_COMMIT = "engine-commit.txt"
AUTHOR_JSON = "data/author.json"
EDIT_OPS = ("find", "lines", "from")
FIELD_KEYS = {"stop", "message", "refuse_example", "pass_example"}
EXECUTE_KINDS = {"content_regex", "guard", "script"}
NEEDED_CATEGORIES = {"trigger", "negative_trigger", "behavior"}
CATEGORIES = NEEDED_CATEGORIES | {"implicit"}
# The probe values stand in for __ID__/__NAME__/__DATE__ when anchors are checked.
PROBE = {"__ID__": "my-check-x", "__NAME__": "My Check", "__DATE__": "2026-01-01"}


def _kind_files(kind_dir: Path) -> dict[str, str]:
    """The kind's template files as {path inside the policy: text}, .tmpl suffix dropped."""
    files = {}
    for path in sorted(kind_dir.rglob("*.tmpl")):
        rel = path.relative_to(kind_dir).as_posix()[: -len(".tmpl")]
        files[rel] = path.read_text(encoding="utf-8")
    if not files:
        raise PageError(f"{kind_dir}: no .tmpl files")
    return files


def _fill(text: str) -> str:
    """The probe tokens filled, the way author.js fills the user's values."""
    for token, value in PROBE.items():
        text = text.replace(token, value)
    return text


def _check_edit(kind: str, edit: dict[str, Any], files: dict[str, str]) -> None:
    """One edit names an existing file, exactly one op, and an anchor found exactly once."""
    file = edit.get("file")
    if file not in files:
        raise PageError(f"{kind}: edit names {file!r}, not one of {sorted(files)}")
    ops = [op for op in EDIT_OPS if edit.get(op)]
    if len(ops) != 1 or not edit.get("put"):
        raise PageError(f"{kind}: {file}: an edit needs one of {EDIT_OPS} and a `put`")
    anchor = _fill(edit[ops[0]])
    text = _fill(files[file])
    if text.count(anchor) != 1:
        raise PageError(
            f"{kind}: {file}: anchor occurs {text.count(anchor)} times, not once: {anchor[:60]!r}"
        )
    if (
        ops[0] in ("lines", "from")
        and sum(anchor in line for line in text.splitlines()) != 1
    ):
        raise PageError(
            f"{kind}: {file}: {ops[0]} anchor sits on no unique line: {anchor[:60]!r}"
        )


def _check_kind(kind: str, spec: dict[str, Any], files: dict[str, str]) -> None:
    """A kind's fields, edits and eval cases are complete and its anchors still match."""
    keys = {field["key"] for field in spec["fields"]}
    if keys != FIELD_KEYS:
        raise PageError(f"{kind}: fields {sorted(keys)} != {sorted(FIELD_KEYS)}")
    for edit in spec["edits"]:
        _check_edit(kind, edit, files)
    cases = spec["evals"]
    if len(cases) < 3:
        raise PageError(f"{kind}: evals need at least 3 cases")
    found = {case["category"] for case in cases}
    if not found <= CATEGORIES or not NEEDED_CATEGORIES <= found:
        raise PageError(
            f"{kind}: eval categories {sorted(found)} miss one of {sorted(NEEDED_CATEGORIES)}"
        )
    if kind in EXECUTE_KINDS:
        for case in cases:
            if not case.get("execute"):
                raise PageError(
                    f"{kind}: {case['category']} case {case['prompt'][:40]!r} has no execute"
                )


def load_author(data_dir: Path) -> dict[str, Any]:
    """author.yaml plus each kind's template text; a stale anchor or file fails the build."""
    config = yaml.safe_load((data_dir / AUTHOR_YAML).read_text(encoding="utf-8"))
    commit = (data_dir / KINDS_DIR / ENGINE_COMMIT).read_text(encoding="utf-8").strip()
    kinds = {}
    for kind, spec in config["kinds"].items():
        files = _kind_files(data_dir / KINDS_DIR / kind)
        _check_kind(kind, spec, files)
        kinds[kind] = {
            "title": spec["title"],
            "blurb": spec["blurb"],
            "fields": spec["fields"],
            "edits": spec["edits"],
            "evals": spec["evals"],
            "files": files,
        }
    return {
        "schema_version": 1,
        "engine_commit": commit,
        "texts": config["texts"],
        "script": config["script"],
        "kinds": kinds,
    }


def write_author_json(site_data: dict[str, Any], out_dir: Path) -> Path:
    """dist/data/author.json: everything author.js needs in one fetch."""
    path = out_dir / AUTHOR_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(site_data["author"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path
