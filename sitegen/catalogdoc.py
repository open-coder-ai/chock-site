"""DOCS-4 catalog pages' sources: catalog files at .catalog-ref snapshotted into data/, and a recorded adopt run.

The snapshot holds quoted CONTRIBUTING.md and README.md sections, the policy trees, the CI jobs
and what tools/regen_all.py regenerates, each read from the catalog checkout.

Run `python -m sitegen.catalogdoc --catalog <catalog checkout at .catalog-ref>` with chock
installed at .framework-ref to regenerate, or add `--check` to fail (exit 1) when the committed
snapshot or recording differs from a fresh one. The adopt run fetches from GitHub.
"""

import argparse
import ast
import difflib
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from . import cliexamples
from .docsmd import sections
from .pageparts import PageError

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE_DIR = "catalog-source"
SOURCE_JSON = "source.json"
TREES_JSON = "trees.json"
GATES_JSON = "ci-gates.json"
REGEN_JSON = "regen.json"
ADOPT_JSON = "adopt.json"
ADOPT_YAML = "catalog-adopt.yaml"
TREES_FILE = "tools/trees.py"
CI_FILE = ".github/workflows/ci.yml"
REGEN_FILE = "tools/regen_all.py"
MANIFEST = "manifest.yaml"
CATALOG_REF = "__CATALOG_REF__"
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
SCHEMA_VERSION = 1


def quotes(docs: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Per catalog file: each (sections, level) the catalog pages quote, in page order."""
    files: dict[str, list[dict[str, Any]]] = {}
    for page in docs["pages"].values():
        for part in page.get("catalog", []):
            if "quote" in part:
                want = {"sections": part["sections"], "level": part.get("level", 2)}
                if want not in files.setdefault(part["quote"], []):
                    files[part["quote"]].append(want)
    return files


def snapshot_name(path: str) -> str:
    """The snapshot file a catalog path is stored in."""
    return path.replace("/", "__")


def quoted(text: str, wants: list[dict[str, Any]]) -> str:
    """The quoted sections of one file, HTML comments dropped as GitHub's renderer drops them."""
    text = COMMENT_RE.sub("", text)
    return "\n".join(sections(text, w["sections"], w["level"]) for w in wants)


def trees(catalog: Path) -> list[dict[str, Any]]:
    """Each policy tree tools/trees.py names, with its count of policy folders."""
    module = ast.parse((catalog / TREES_FILE).read_text(encoding="utf-8"))
    found = next(
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "TREES" for t in node.targets)
    )
    names = ast.literal_eval(found)
    return [
        {
            "tree": name,
            "policies": sum(
                1 for p in (catalog / name).iterdir() if (p / MANIFEST).is_file()
            ),
        }
        for name in names
    ]


def gates(catalog: Path) -> list[dict[str, Any]]:
    """Each job of the catalog's ci.yml: its id, its `if:` condition, and its step names."""
    workflow = yaml.safe_load((catalog / CI_FILE).read_text(encoding="utf-8"))
    return [
        {
            "job": job_id,
            "if": job.get("if"),
            "steps": [step["name"] for step in job.get("steps", []) if "name" in step],
        }
        for job_id, job in workflow["jobs"].items()
    ]


def regen(catalog: Path) -> dict[str, Any]:
    """tools/regen_all.py's docstring, and the scripts its regenerate() runs, in source order."""
    module = ast.parse((catalog / REGEN_FILE).read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "regenerate"
    )
    tools = {
        alias.asname or alias.name
        for node in module.body
        if isinstance(node, ast.Import)
        for alias in node.names
        if (catalog / "tools" / f"{alias.name}.py").is_file()
    }
    found = []
    for node in ast.walk(function):
        if isinstance(node, ast.Constant) and str(node.value).endswith(".py"):
            found.append((node.lineno, node.col_offset, node.value))
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in tools
        ):
            found.append((node.lineno, node.col_offset, f"tools/{node.value.id}.py"))
    scripts: list[str] = []
    for _line, _col, script in sorted(found):
        if script not in scripts:
            scripts.append(script)
    return {"doc": ast.get_docstring(module), "scripts": scripts}


def _json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def snapshot(catalog: Path, docs: dict[str, Any], ref: str) -> dict[str, str]:
    """Every snapshot file's text, keyed by name, read from a catalog checkout."""
    files: dict[str, str] = {}
    record: dict[str, Any] = {"catalog_ref": ref, "files": {}}
    for path, wants in sorted(quotes(docs).items()):
        source = catalog / path
        if not source.is_file():
            raise PageError(f"{path}: not in the catalog checkout at {ref}")
        name = snapshot_name(path)
        files[name] = quoted(source.read_text(encoding="utf-8"), wants)
        record["files"][path] = name
    files[TREES_JSON] = _json(trees(catalog))
    files[GATES_JSON] = _json(gates(catalog))
    files[REGEN_JSON] = _json(regen(catalog))
    files[SOURCE_JSON] = _json(record)
    return files


def load(data_dir: Path, ref: str) -> dict[str, Any]:
    """The committed snapshot: quoted text per file, trees, gates and the adopt run.

    Refuses a snapshot taken at another catalog commit than .catalog-ref.
    """
    folder = data_dir / SOURCE_DIR
    record = json.loads((folder / SOURCE_JSON).read_text(encoding="utf-8"))
    if record["catalog_ref"] != ref:
        raise PageError(
            f"{SOURCE_DIR}/{SOURCE_JSON} was taken at catalog {record['catalog_ref']}, "
            f"but .catalog-ref is {ref}: run python -m sitegen.catalogdoc --catalog <checkout>"
        )
    adopt = json.loads((folder / ADOPT_JSON).read_text(encoding="utf-8"))
    if adopt["catalog"] != ref:
        raise PageError(
            f"{SOURCE_DIR}/{ADOPT_JSON} was recorded at another catalog commit"
        )
    return {
        "quotes": {
            path: (folder / name).read_text(encoding="utf-8")
            for path, name in record["files"].items()
        },
        "trees": json.loads((folder / TREES_JSON).read_text(encoding="utf-8")),
        "gates": json.loads((folder / GATES_JSON).read_text(encoding="utf-8")),
        "regen": json.loads((folder / REGEN_JSON).read_text(encoding="utf-8")),
        "adopt": adopt,
    }


def load_script(data_dir: Path, ref: str) -> dict[str, Any]:
    """data/catalog-adopt.yaml with __CATALOG_REF__ arguments set to .catalog-ref."""
    script = yaml.safe_load((data_dir / ADOPT_YAML).read_text(encoding="utf-8"))
    for step in script["steps"]:
        if set(step) != {"run"} or step["run"][0] not in ("chock", "git"):
            raise PageError(f"{ADOPT_YAML}: a step is {{run: [chock|git, ...]}}")
        step["run"] = [ref if arg == CATALOG_REF else arg for arg in step["run"]]
    return script


def run_adopt(
    script: dict[str, Any], engine_ref: str, catalog_ref: str
) -> dict[str, Any]:
    """The adopt session: every step run in order in one fresh repository, as cliexamples runs its own."""
    chock = cliexamples._chock()
    examples = []
    with tempfile.TemporaryDirectory(prefix="chock-adopt-") as name:
        tmp = Path(name)
        repo, home, shown = cliexamples._paths(tmp, script)
        env = cliexamples._env(home)
        for argv in script["setup"]:
            subprocess.run(argv, cwd=repo, env=env, check=True, capture_output=True)
        for number, step in enumerate(script["steps"], start=1):
            argv = step["run"]
            done = subprocess.run(
                [chock, *argv[1:]] if argv[0] == "chock" else argv,
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
                    f"adopt step {number}: output names the throwaway folder"
                )
            examples.append(
                {
                    "step": number,
                    "command": shlex.join(argv),
                    "output": output,
                    "exit": done.returncode,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": engine_ref,
        "catalog": catalog_ref,
        "examples": examples,
    }


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    """Write the snapshot and the adopt recording, or with --check report any difference."""
    parser = argparse.ArgumentParser(prog="python -m sitegen.catalogdoc")
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args(argv)
    ref = (ROOT / ".catalog-ref").read_text(encoding="utf-8").strip()
    engine_ref = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
    head = _head(args.catalog)
    if head != ref:
        print(f"{args.catalog}: HEAD is {head}, .catalog-ref is {ref}", file=sys.stderr)
        return 2
    installed = cliexamples.installed_commit()
    if installed != engine_ref:
        print(
            f"installed chock is {installed or 'not from git'}, .framework-ref is {engine_ref}",
            file=sys.stderr,
        )
        return 2
    docs = yaml.safe_load((args.data / "docs.yaml").read_text(encoding="utf-8"))
    try:
        files = snapshot(args.catalog, docs, ref)
        adopt = run_adopt(load_script(args.data, ref), engine_ref, ref)
    except PageError as exc:
        print(exc, file=sys.stderr)
        return 2
    files[ADOPT_JSON] = _json(adopt)
    folder = args.data / SOURCE_DIR
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
                committed = (
                    (folder / name).read_text(encoding="utf-8")
                    if name in present
                    else ""
                )
                sys.stderr.writelines(
                    difflib.unified_diff(
                        committed.splitlines(keepends=True),
                        files.get(name, "").splitlines(keepends=True),
                        f"committed/{name}",
                        f"re-run/{name}",
                    )
                )
            print(
                "catalog snapshot drifts from the catalog at .catalog-ref: "
                + ", ".join(drift)
                + "\nrun: python -m sitegen.catalogdoc --catalog <checkout>",
                file=sys.stderr,
            )
            return 1
        print(f"catalog snapshot matches catalog {ref[:12]} ({len(files) - 1} files)")
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
