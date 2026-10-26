"""DOCS-5 Write policies pages' sources: the recorded runs of data/write-policy.yaml, and schema rows.

Run `python -m sitegen.writedoc --record` with chock installed at .framework-ref to re-record
data/write-source/, or `--check` to fail (exit 1) when a re-run prints something else or exits
with another code than the committed recording. The manifest and eval reference tables are
read from the installed engine's schemas at build time, so they need no recording.
"""

import argparse
import difflib
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from . import cliexamples
from .pageparts import PageError

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCRIPT_YAML = "write-policy.yaml"
OUT_DIR = "write-source"
SCHEMA_VERSION = 1
# The programs a run may execute, in its setup and its shown steps alike.
PROGRAMS = ("chock", "git", "cat")
# Nesting deeper than this is not tabulated; the engine's schemas nest at most 4 levels.
MAX_DEPTH = 8
CONSTRAINTS = (
    ("format", "format"),
    ("minLength", "min length"),
    ("maxLength", "max length"),
    ("minItems", "min items"),
    ("maxItems", "max items"),
    ("minimum", "minimum"),
    ("maximum", "maximum"),
)


def load_script(data_dir: Path) -> dict[str, Any]:
    """data/write-policy.yaml, refused unless every step is a run of chock, git or cat, or one sh line."""
    script = yaml.safe_load((data_dir / SCRIPT_YAML).read_text(encoding="utf-8"))
    for name, steps in script["runs"].items():
        for step in steps:
            ok = (set(step) == {"run"} and step["run"][0] in PROGRAMS) or (
                set(step) == {"sh"} and isinstance(step["sh"], str)
            )
            if not ok:
                raise PageError(
                    f"{SCRIPT_YAML} {name}: a step is {{run: [chock|git|cat, ...]}} or {{sh: line}}"
                )
    cliexamples.check_setup(script, PROGRAMS, SCRIPT_YAML)
    return script


def command(step: dict[str, Any]) -> str:
    """A step as the page shows it: the argv shell-quoted, or the sh line as written."""
    return step["sh"] if "sh" in step else shlex.join(step["run"])


def run_one(script: dict[str, Any], name: str, engine_ref: str) -> dict[str, Any]:
    """One run: its steps in order in a fresh repository, as cliexamples runs its session."""
    chock = cliexamples._chock()
    examples = []
    with tempfile.TemporaryDirectory(prefix="chock-write-") as folder:
        tmp = Path(folder)
        repo, home, shown = cliexamples._paths(tmp, script)
        env = cliexamples._env(home)
        for argv in script["setup"]:
            subprocess.run(argv, cwd=repo, env=env, check=True, capture_output=True)
        for number, step in enumerate(script["runs"][name], start=1):
            if "sh" in step:
                argv = ["sh", "-c", step["sh"]]
            else:
                argv = step["run"]
                if argv[0] == "chock":
                    argv = [chock, *argv[1:]]
            done = subprocess.run(
                argv,
                cwd=repo,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                timeout=cliexamples.STEP_TIMEOUT,
                check=False,
            )
            output = cliexamples.normalise(done.stdout, shown)
            if str(tmp) in output or str(tmp.resolve()) in output:
                raise PageError(
                    f"{name} step {number}: output names the throwaway folder"
                )
            examples.append(
                {
                    "step": number,
                    "command": command(step),
                    "output": output,
                    "exit": done.returncode,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": engine_ref,
        "run": name,
        "examples": examples,
    }


def render(recording: dict[str, Any]) -> str:
    """A recording as committed JSON text."""
    return json.dumps(recording, indent=2, ensure_ascii=False) + "\n"


def load(data_dir: Path, engine_ref: str) -> dict[str, dict[str, Any]]:
    """Every committed recording, keyed by run; refused if one was made with another engine."""
    runs = {}
    for path in sorted((data_dir / OUT_DIR).glob("*.json")):
        recording = json.loads(path.read_text(encoding="utf-8"))
        if recording["engine"] != engine_ref:
            raise PageError(
                f"{OUT_DIR}/{path.name} was recorded with chock {recording['engine']}, "
                f"but .framework-ref is {engine_ref}: run python -m sitegen.writedoc --record"
            )
        runs[path.stem] = recording
    return runs


# --- schema rows: the manifest and eval references -------------------------------------


def _resolve(
    node: dict[str, Any], store: dict[str, dict[str, Any]], base: str
) -> tuple[dict[str, Any], str]:
    """A schema node with its $ref followed (across the engine's schema files), and its file's $id."""
    seen = set()
    while "$ref" in node:
        url, _, pointer = node["$ref"].partition("#")
        doc_id = url or base
        if (doc_id, pointer) in seen:
            raise PageError(f"schema $ref loop at {node['$ref']}")
        seen.add((doc_id, pointer))
        target: Any = store[doc_id]
        for part in [p for p in pointer.split("/") if p]:
            target = target[part]
        extra = {k: v for k, v in node.items() if k != "$ref"}
        node, base = {**target, **extra}, doc_id
    return node, base


def _type(node: dict[str, Any], store: dict[str, dict[str, Any]], base: str) -> str:
    """A node's JSON type as the schema states it; an array names its items' type."""
    kind = node.get("type")
    if isinstance(kind, list):
        kind = " or ".join(kind)
    if kind == "array" and isinstance(node.get("items"), dict):
        items, _ = _resolve(node["items"], store, base)
        inner = _type(items, store, base)
        return f"array of {inner}" if inner else "array"
    if kind is None and "enum" in node:
        return "enum"
    return kind or ""


def _allowed(node: dict[str, Any]) -> str:
    """The values a node allows: its enum or const, then each format, length or range limit."""
    parts = []
    if "enum" in node:
        parts.append("one of: " + ", ".join(json.dumps(v) for v in node["enum"]))
    if "const" in node:
        parts.append("exactly " + json.dumps(node["const"]))
    for key, word in CONSTRAINTS:
        if key in node:
            parts.append(f"{word} {node[key]}")
    return ", ".join(parts)


def schema_rows(
    schema: dict[str, Any], store: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Every property a schema declares, depth first, as {field, type, required, allowed, pattern, description}.

    `field` is the dotted path: `a.b` for a property, `a[].b` inside an array's items, and
    `a.<name>.b` under additionalProperties. A $ref is followed into the engine's other files.
    """
    rows: list[dict[str, Any]] = []

    def walk(
        node: dict[str, Any], base: str, path: str, stack: tuple[str, ...]
    ) -> None:
        node, base = _resolve(node, store, base)
        required = set(node.get("required", []))
        for key, child in node.get("properties", {}).items():
            field = f"{path}.{key}" if path else key
            resolved, child_base = _resolve(child, store, base)
            rows.append(
                {
                    "field": field,
                    "type": _type(resolved, store, child_base),
                    "required": key in required,
                    "allowed": _allowed(resolved),
                    "pattern": resolved.get("pattern", ""),
                    "description": resolved.get("description", ""),
                }
            )
            descend(resolved, child_base, field, stack)

    def descend(
        node: dict[str, Any], base: str, path: str, stack: tuple[str, ...]
    ) -> None:
        if len(stack) >= MAX_DEPTH:
            return
        stack = (*stack, path)
        if node.get("properties"):
            walk(node, base, path, stack)
        extra = node.get("additionalProperties")
        if isinstance(extra, dict):
            inner, inner_base = _resolve(extra, store, base)
            if inner.get("properties"):
                walk(inner, inner_base, f"{path}.<name>", stack)
        items = node.get("items")
        if isinstance(items, dict):
            inner, inner_base = _resolve(items, store, base)
            if inner.get("properties"):
                walk(inner, inner_base, f"{path}[]", stack)

    walk(schema, schema.get("$id", ""), "", ())
    return rows


def main(argv: list[str] | None = None) -> int:
    """Record every run into data/write-source/, or with --check report any difference."""
    parser = argparse.ArgumentParser(prog="python -m sitegen.writedoc")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args(argv)
    ref = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
    installed = cliexamples.installed_commit()
    if installed != ref:
        print(
            f"installed chock is {installed or 'not from git'}, .framework-ref is {ref}",
            file=sys.stderr,
        )
        return 2
    try:
        script = load_script(args.data)
        wanted = {
            f"{name}.json": render(run_one(script, name, ref))
            for name in script["runs"]
        }
    except PageError as exc:
        print(exc, file=sys.stderr)
        return 2
    folder = args.data / OUT_DIR
    present = {p.name for p in folder.glob("*.json")} if folder.is_dir() else set()
    if args.check:
        drift = sorted(
            name
            for name in set(wanted) | present
            if name not in wanted
            or name not in present
            or (folder / name).read_text(encoding="utf-8") != wanted[name]
        )
        if drift:
            for name in drift:
                committed = (
                    (folder / name).read_text(encoding="utf-8")
                    if name in present
                    else ""
                )
                sys.stderr.writelines(
                    difflib.unified_diff(
                        committed.splitlines(keepends=True),
                        wanted.get(name, "").splitlines(keepends=True),
                        f"committed/{name}",
                        f"re-run/{name}",
                    )
                )
            print(
                "write-policy runs differ from a re-run at .framework-ref: "
                + ", ".join(drift)
                + "\nrun: python -m sitegen.writedoc --record",
                file=sys.stderr,
            )
            return 1
        print(f"write-policy runs match chock {ref[:12]} ({len(wanted)} runs)")
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    for name in present - set(wanted):
        (folder / name).unlink()
    for name, text in wanted.items():
        (folder / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(wanted)} files to {folder.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
