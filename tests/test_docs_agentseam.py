"""DOCS-3: the agentseam pages, from the pinned agentseam: quoted docs, a recorded run, API, CLI."""

import html
import json
import re
from pathlib import Path
from types import SimpleNamespace

import agentseam
import pytest
import yaml

from sitegen import agentseamdoc, docs, engine
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
CFG = DOCS["agentseam"]
KEYS = ["agentseam", "agentseam-direct", "agentseam-api", "agentseam-cli"]
NO_SUCH_OPTION = "--no-such-option-for-the-docs"


def _page(built, key: str, name: str = "index.html") -> str:
    path = built.out / DOCS["pages"][key]["path"].strip("/") / name
    return path.read_text(encoding="utf-8")


def _examples() -> list[dict]:
    return agentseamdoc.load_run(DATA)["examples"]


def test_the_pinned_commit_is_installed_and_is_chocks_pin() -> None:
    ref = agentseamdoc.pinned(DATA)
    assert re.fullmatch(r"[0-9a-f]{40}", ref)
    assert engine.agentseam_commit() == ref
    assert engine.agentseam_chock_pin() == ref


def test_build_refuses_another_installed_agentseam(monkeypatch) -> None:
    monkeypatch.setattr(engine, "agentseam_commit", lambda: "0" * 40)
    ctx = SimpleNamespace(data_dir=DATA)
    with pytest.raises(PageError, match="the installed agentseam is 0000"):
        docs._agentseam_ref(ctx)


def test_every_page_is_in_nav_with_a_twin(built) -> None:
    group = next(g for g in DOCS["nav"] if g["group"] == "agentseam")
    assert group["pages"] == KEYS
    for key in KEYS:
        assert DOCS["pages"][key]["path"].startswith("/docs/agentseam/")
        assert DOCS["texts"]["ask_first"] in _page(built, key, "index.md")
        assert html.escape(DOCS["pages"][key]["nav_label"]) in _page(built, "overview")


def test_snapshot_lists_exactly_the_quoted_files() -> None:
    quoted = agentseamdoc.load(DATA)
    assert sorted(quoted) == sorted(q["file"] for q in CFG["quotes"])
    assert all(text.strip() for text in quoted.values())


def test_extract_without_heading_drops_only_the_heading_line() -> None:
    text = "# Design\n\n- a\n- b\n\n# Next\n\nc\n"
    quote = {"sections": ["Design"], "level": 1, "heading": False}
    assert agentseamdoc.extract(text, quote) == "- a\n- b\n"
    assert agentseamdoc.extract(text, quote | {"heading": True}).startswith("# Design")


def test_handler_is_the_readme_quick_start_word_for_word() -> None:
    quickstart = agentseamdoc.load(DATA)["docs/quickstart.sh"]
    heredoc = re.search(r"<< 'EOF'\n(.*?\n)EOF\n", quickstart, re.DOTALL).group(1)
    script = agentseamdoc.load_script(DATA)
    assert script["files"]["my_handler.py"] == heredoc


def test_payloads_take_the_claude_code_example_shape() -> None:
    files = agentseamdoc.load_script(DATA)["files"]
    deny, allow = json.loads(files["deny.json"]), json.loads(files["allow.json"])
    assert deny["hook_event_name"] == allow["hook_event_name"] == "PreToolUse"
    assert {k: v for k, v in deny.items() if k != "tool_input"} == {
        k: v for k, v in allow.items() if k != "tool_input"
    }
    assert "AKIA" in deny["tool_input"]["content"]
    assert "AKIA" not in allow["tool_input"]["content"]


def test_recording_backs_each_step_note() -> None:
    by_step = {e["step"]: e for e in _examples()}
    assert set(CFG["texts"]["run_notes"]) == set(by_step)
    assert by_step[1]["output"] == agentseam.__version__
    assert by_step[3]["output"].count("wired ") == len(agentseam.adapted_agents())
    assert "/home/demo/.junie/" in by_step[3]["output"]
    assert "/home/demo/.kimi-code/" in by_step[3]["output"]
    assert '"_agentseam": "agentseam"' in by_step[4]["output"]
    assert '"permissionDecision": "deny"' in by_step[5]["output"]
    assert by_step[6]["output"] == "" and by_step[6]["exit"] == 0
    assert "decision: deny no AWS keys in memory files" in by_step[7]["output"]
    assert by_step[9]["output"] == "{}"
    assert all(e["exit"] == 0 for e in by_step.values())


def test_direct_page_shows_every_recorded_step(built) -> None:
    page = _page(built, "agentseam-direct")
    twin = _page(built, "agentseam-direct", "index.md")
    for example in _examples():
        assert html.escape(f"$ {example['command']}") in page
        assert f"$ {example['command']}" in twin
    assert agentseamdoc.pinned(DATA) in twin


def test_api_page_has_every_exported_name(built) -> None:
    twin = _page(built, "agentseam-api", "index.md")
    for name in agentseam.__all__:
        assert f"### {name}\n" in twin or f"| `{name}` |" in twin, name


def test_api_groups_must_cover_all_exactly_once() -> None:
    api = engine.agentseam_api()
    groups = [*CFG["api_groups"], {"heading": "x", "names": ["run", "nope"]}]
    ctx = SimpleNamespace(docs={"agentseam": {"api_groups": groups}})
    with pytest.raises(
        PageError, match=r"not exported \['nope'\], listed twice \['run'\]"
    ):
        docs._api_groups(ctx, api)
    short = [
        {**g, "names": [n for n in g["names"] if n != "run"]} for g in CFG["api_groups"]
    ]
    ctx = SimpleNamespace(docs={"agentseam": {"api_groups": short}})
    with pytest.raises(PageError, match=r"not listed \['run'\]"):
        docs._api_groups(ctx, api)


def test_api_entries_match_inspect() -> None:
    import inspect

    entries = {e["name"]: e for e in engine.agentseam_api()}
    assert entries["run"]["signature"] == str(inspect.signature(agentseam.run))
    assert entries["Decision"]["kind"] == "class"
    assert "deny" in [m["name"] for m in entries["Decision"]["members"]]
    assert entries["MATRIX"]["size"] == len(agentseam.MATRIX)
    assert entries["PRE_TOOL"]["value"] == repr(agentseam.PRE_TOOL)
    assert entries["run"]["source"].startswith("src/agentseam/dispatch.py#L")


def test_cli_page_has_every_command(built) -> None:
    twin = _page(built, "agentseam-cli", "index.md")
    for node in engine.agentseam_cli():
        name = " ".join(["agentseam", *node["path"]])
        assert f"## `{name}`\n" in twin, name
        for argument in node["arguments"]:
            assert f"`{argument['name']}" in twin, (name, argument["name"])


@pytest.mark.parametrize(
    "path", [n["path"] for n in engine.agentseam_cli()], ids=lambda p: " ".join(p)
)
def test_every_agentseam_command_exits_2_on_an_unknown_option(path) -> None:
    assert engine.agentseam_exit([*path, NO_SUCH_OPTION]) == 2
