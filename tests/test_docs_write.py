"""DOCS-5: the Write policies pages, their recorded runs, and the schema reference tables."""

import html
import json
from pathlib import Path

import pytest
import yaml
from chock.validation.loading import SCHEMA_STORE, load_schema

from sitegen import writedoc
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
SCRIPT = yaml.safe_load((DATA / writedoc.SCRIPT_YAML).read_text(encoding="utf-8"))
ENGINE_REF = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
PAGES = ("write-own", "write-fly", "write-manifest", "write-evals")
RUNS = writedoc.load(DATA, ENGINE_REF)


def _page(built, key: str) -> tuple[str, str]:
    """A Write policies page's HTML, unescaped, and its Markdown twin."""
    folder = built.out / DOCS["pages"][key]["path"].strip("/")
    return (
        html.unescape((folder / "index.html").read_text(encoding="utf-8")),
        (folder / "index.md").read_text(encoding="utf-8"),
    )


def _step(run: str, command: str) -> list[dict]:
    return [e for e in RUNS[run]["examples"] if e["command"] == command]


def test_write_pages_are_one_nav_group_under_docs_write() -> None:
    group = next(g for g in DOCS["nav"] if g["group"] == "Write policies")
    assert tuple(group["pages"]) == PAGES
    for key in PAGES:
        assert DOCS["pages"][key]["path"].startswith("/docs/write/")


def test_every_run_is_recorded_at_the_pin_with_its_steps_in_order() -> None:
    assert set(RUNS) == set(SCRIPT["runs"])
    for name, steps in SCRIPT["runs"].items():
        recording = RUNS[name]
        assert recording["engine"] == ENGINE_REF
        assert [e["command"] for e in recording["examples"]] == [
            writedoc.command(s) for s in steps
        ]
        assert [e["step"] for e in recording["examples"]] == list(
            range(1, len(steps) + 1)
        )


def test_own_run_prints_both_next_steps_and_refuses_only_the_marked_commit() -> None:
    (new,) = _step("own", "chock new policy block-marker --kind content_regex")
    assert new["exit"] == 0
    assert new["output"].splitlines()[-2:] == [
        "Next:  python -m chock sync --repo .",
        "       python -m chock check --repo .",
    ]
    (check,) = _step("own", "chock check --repo .")
    assert check["exit"] == 0
    assert check["output"].splitlines()[-1] == "== result: PASS"
    commits = _step("own", "git commit -q -m 'Add notes'")
    assert [c["exit"] for c in commits] == [1, 0]
    assert "my-block-marker: this change adds a line" in commits[0]["output"]
    (first,) = _step("own", "git commit -q -m 'Add my-block-marker'")
    assert first["exit"] == 0


def test_fly_run_hook_denies_the_destroy_and_allows_the_plan() -> None:
    hooks = [
        e for e in RUNS["fly"]["examples"] if "claude_code.py --guard" in e["command"]
    ]
    destroy, plan = hooks
    assert "terraform destroy" in destroy["command"]
    decision = json.loads(destroy["output"].splitlines()[-1])
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "terraform plan" in plan["command"]
    assert (plan["exit"], plan["output"]) == (0, "")
    (log,) = _step("fly", "chock gate-log")
    row = next(
        line
        for line in log["output"].splitlines()
        if line.startswith("my-no-tf-destroy")
    )
    assert row.split()[:6] == ["my-no-tf-destroy", "pre-tool-use", "1", "0", "1", "0"]


def test_every_step_has_one_note() -> None:
    notes = DOCS["texts"]["write"]["run_notes"]
    assert {name: len(n) for name, n in notes.items()} == {
        name: len(steps) for name, steps in SCRIPT["runs"].items()
    }


def test_recording_from_another_engine_commit_is_refused() -> None:
    with pytest.raises(PageError, match="framework-ref"):
        writedoc.load(DATA, "0" * 40)


def test_script_refuses_a_program_it_does_not_allow(tmp_path: Path) -> None:
    (tmp_path / writedoc.SCRIPT_YAML).write_text(
        "repo: /work/demo\nhome: /home/demo\nsetup: []\nruns:\n  x:\n    - {run: [curl, x]}\n",
        encoding="utf-8",
    )
    with pytest.raises(PageError, match="a step is"):
        writedoc.load_script(tmp_path)


def test_schema_rows_follow_refs_items_and_named_keys() -> None:
    store = {
        "s": {
            "$id": "s",
            "required": ["a"],
            "properties": {
                "a": {"$ref": "o#/definitions/obj"},
                "b": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"c": {"type": "string"}},
                    },
                },
                "m": {
                    "type": "object",
                    "additionalProperties": {
                        "properties": {"d": {"type": "integer", "minimum": 1}}
                    },
                },
            },
        },
        "o": {
            "$id": "o",
            "definitions": {
                "obj": {
                    "type": "object",
                    "required": ["x"],
                    "properties": {
                        "x": {"type": "string", "enum": ["p", "q"], "description": "X."}
                    },
                }
            },
        },
    }
    rows = writedoc.schema_rows(store["s"], store)
    assert [(r["field"], r["type"], r["required"], r["allowed"]) for r in rows] == [
        ("a", "object", True, ""),
        ("a.x", "string", True, 'one of: "p", "q"'),
        ("b", "array of object", False, ""),
        ("b[].c", "string", False, ""),
        ("m", "object", False, ""),
        ("m.<name>.d", "integer", False, "minimum 1"),
    ]
    assert rows[1]["description"] == "X."


@pytest.mark.parametrize("name", ["manifest.schema.json", "eval.schema.json"])
def test_schema_rows_cover_every_top_level_and_referenced_field(name: str) -> None:
    schema = load_schema(name)
    fields = {r["field"] for r in writedoc.schema_rows(schema, SCHEMA_STORE)}
    for key, node in schema["properties"].items():
        assert key in fields, key
        resolved, _ = writedoc._resolve(node, SCHEMA_STORE, schema["$id"])
        for child in resolved.get("properties", {}):
            assert f"{key}.{child}" in fields, f"{key}.{child}"


def test_pages_show_every_step_with_its_exit_code(built) -> None:
    for key, run in (("write-own", "own"), ("write-fly", "fly")):
        page, twin = _page(built, key)
        for example in RUNS[run]["examples"]:
            assert f"$ {example['command']}" in page, example["command"]
            assert f"$ {example['command']}" in twin, example["command"]
            assert f"Step {example['step']}, exit code {example['exit']}." in page


def test_reference_pages_have_a_row_for_every_schema_field(built) -> None:
    for key, name in (
        ("write-manifest", "manifest.schema.json"),
        ("write-evals", "eval.schema.json"),
    ):
        page, twin = _page(built, key)
        for row in writedoc.schema_rows(load_schema(name), SCHEMA_STORE):
            assert f"<code>{row['field']}</code>" in page, row["field"]
            assert f"`{row['field']}`" in twin, row["field"]
