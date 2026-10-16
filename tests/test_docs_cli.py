"""DOCS-1: one CLI page per engine command and subcommand, from its parser and recorded runs."""

import html
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from sitegen import cliexamples, docs, engine
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
CLI = DOCS["pages"]["cli"]["path"]
TREE = engine.cli_tree()
REF = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
NO_SUCH_OPTION = "--no-such-option-for-the-docs"


def _page(built, node: dict, name: str = "index.html") -> str:
    path = built.out / CLI.strip("/") / Path(*node["path"]) / name
    return path.read_text(encoding="utf-8")


def _ctx(**changes) -> SimpleNamespace:
    """The parts of a docs Ctx the coverage check reads."""
    ctx = SimpleNamespace(
        docs={"cli_pages": [" ".join(n["path"]) for n in TREE]},
        cli_tree=TREE,
        cli_examples=cliexamples.load(DATA),
        site=SimpleNamespace(framework_ref=REF),
    )
    for key, value in changes.items():
        setattr(ctx, key, value)
    return ctx


def _chock() -> str:
    found = shutil.which("chock", path=str(Path(sys.executable).parent))
    assert found, "install chock at .framework-ref beside this Python"
    return found


def test_tree_starts_from_every_engine_command() -> None:
    tops = [n["path"][0] for n in TREE if len(n["path"]) == 1]
    assert tops == [c["name"] for c in engine.cli_commands()]
    assert {n["group"] for n in TREE} <= set(DOCS["texts"]["cli_groups"])
    assert all(n["summary"] for n in TREE)


def test_docs_yaml_lists_every_node_in_engine_order() -> None:
    assert DOCS["cli_pages"] == [" ".join(n["path"]) for n in TREE]


def test_every_node_has_a_page_twin_and_index_link(built) -> None:
    index = (built.out / CLI.strip("/") / "index.html").read_text(encoding="utf-8")
    twin = (built.out / CLI.strip("/") / "index.md").read_text(encoding="utf-8")
    for node in TREE:
        href = f"{CLI}{'/'.join(node['path'])}/"
        name = " ".join(["chock", *node["path"]])
        page = _page(built, node)
        assert f"<h1>{html.escape(name)}</h1>" in page or f">{name}</h1>" in page, href
        assert _page(built, node, "index.md").startswith(f"# {name}\n"), href
        assert f'href="{href}"' in index, href
        assert f"{href}index.md)" in twin, href


def test_every_cli_page_maps_to_a_node(built) -> None:
    folder = built.out / CLI.strip("/")
    pages = {
        p.parent.relative_to(folder).as_posix()
        for p in folder.rglob("index.html")
        if p.parent != folder
    }
    assert pages == {"/".join(n["path"]) for n in TREE}


def test_every_argument_and_subcommand_is_on_its_page(built) -> None:
    for node in TREE:
        page = _page(built, node)
        twin = _page(built, node, "index.md")
        for argument in node["arguments"]:
            shown = argument["name"]
            if argument["value"] and not argument["choices"]:
                shown += " " + argument["value"]
            assert f"<code>{html.escape(shown)}</code>" in page, (node["path"], shown)
            assert f"`{shown}`" in twin, (node["path"], shown)
            for choice in argument["choices"]:
                assert html.escape(choice) in page, (node["path"], choice)
            if argument["default"]:
                assert f"<code>{html.escape(argument['default'])}</code>" in page
        for sub in node["subcommands"]:
            assert f'href="{CLI}{"/".join([*node["path"], sub["name"]])}/"' in page


def test_parser_pages_show_usage_and_help_as_the_engine_prints_them(built) -> None:
    for node in TREE:
        page = _page(built, node)
        assert html.escape(node["help"]) in page, node["path"]
        if node["parser"]:
            assert node["usage"].startswith(" ".join(["chock", *node["path"]]))
            assert html.escape(node["usage"]) in page, node["path"]


def test_commands_without_argparse_show_only_their_printed_help(built) -> None:
    own = [n for n in TREE if not n["parser"]]
    assert [n["path"] for n in own] == [["compliance"], ["check-matrix"]]
    for node in own:
        assert node["help"] and not node["arguments"]
        page = _page(built, node)
        assert DOCS["texts"]["cli"]["exit_own_parser"] in page
        assert DOCS["texts"]["cli"]["exit_usage"] not in page


def test_recorded_examples_are_on_their_pages_with_exit_codes(built) -> None:
    recordings = cliexamples.load(DATA)
    assert recordings, "run python -m sitegen.cliexamples --record"
    for page_key, recording in recordings.items():
        node = next(n for n in TREE if "/".join(n["path"]) == page_key)
        page = _page(built, node)
        twin = _page(built, node, "index.md")
        for example in recording["examples"]:
            assert html.escape(f"$ {example['command']}") in page
            assert f"exit code {example['exit']}." in page
            for line in example["output"].splitlines():
                assert line in twin, (page_key, line)


def test_script_steps_name_real_commands() -> None:
    script = cliexamples.load_script(DATA)
    keys = {"/".join(n["path"]) for n in TREE}
    assert {step["page"] for step in script["steps"]} <= keys
    assert set(cliexamples.load(DATA)) == {step["page"] for step in script["steps"]}


def test_a_step_that_is_not_its_page_is_refused(tmp_path: Path) -> None:
    script = yaml.safe_load((DATA / "cli-examples.yaml").read_text(encoding="utf-8"))
    script["steps"] = [{"page": "status", "run": ["chock", "sync"]}]
    (tmp_path / "cli-examples.yaml").write_text(yaml.safe_dump(script), "utf-8")
    with pytest.raises(PageError, match="is not the command"):
        cliexamples.load_script(tmp_path)


def test_normalise_names_paths_and_times() -> None:
    text = "at /tmp/x/demo/a by /tmp/x/home at 2026-10-16T00:33:49Z  \n"
    shown = cliexamples.normalise(
        text, {"/tmp/x/demo": "/work/demo", "/tmp/x/home": "/home/demo"}
    )
    assert shown == "at /work/demo/a by /home/demo at <time>"


def test_an_unlisted_command_fails_the_build() -> None:
    listed = [" ".join(n["path"]) for n in TREE][:-1]
    with pytest.raises(PageError, match="not listed"):
        docs._cli_covered(_ctx(docs={"cli_pages": listed}))
    with pytest.raises(PageError, match="not in the engine"):
        docs._cli_covered(_ctx(docs={"cli_pages": [*listed, "gate-log", "nope"]}))
    docs._cli_covered(_ctx())


def test_a_stale_or_stray_recording_fails_the_build() -> None:
    recordings = cliexamples.load(DATA)
    stale = {k: {**v, "engine": "0" * 40} for k, v in recordings.items()}
    with pytest.raises(PageError, match="recorded at"):
        docs._cli_covered(_ctx(cli_examples=stale))
    with pytest.raises(PageError, match="for no command"):
        docs._cli_covered(_ctx(cli_examples={**recordings, "nope": {}}))


def test_every_parser_exits_2_on_an_unknown_option(tmp_path: Path) -> None:
    # The pages' exit-code line rests on this run, not on a reading of argparse.
    chock = _chock()
    for node in TREE:
        if not node["parser"]:
            continue
        done = subprocess.run(
            [chock, *node["path"], NO_SUCH_OPTION],
            cwd=tmp_path,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert done.returncode == 2, (node["path"], done.stderr[-300:])
        assert "error:" in done.stderr, node["path"]


def test_an_unknown_command_exits_2(tmp_path: Path) -> None:
    done = subprocess.run(
        [_chock(), "no-such-command-for-the-docs"],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 2
