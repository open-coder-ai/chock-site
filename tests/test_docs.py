"""DOC-1: the docs section is generated from the pinned engine, agentseam and catalog."""

import json
import shutil
import subprocess
from pathlib import Path

import agentseam.matrix
import pytest
import yaml

from sitegen import docsfacts, docsource, engine
from sitegen.docsmd import Renderer, rewrite_links, sections
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))


def _api(built) -> dict:
    return json.loads(
        (built.out / "api" / "docs" / "index.json").read_text(encoding="utf-8")
    )


def _page(built, path: str, name: str = "index.html") -> str:
    return (built.out / path.strip("/") / name).read_text(encoding="utf-8")


def test_every_docs_yaml_page_has_a_page_and_twin(built) -> None:
    for page in DOCS["pages"].values():
        assert (built.out / page["path"].strip("/") / "index.html").is_file()
        assert (built.out / page["path"].strip("/") / "index.md").is_file()


def test_one_page_per_agentseam_agent(built) -> None:
    api = _api(built)
    assert [a["id"] for a in api["agents"]] == list(engine.matrix_agents())
    assert set(engine.matrix_agents()) == set(agentseam.matrix.MATRIX)
    for agent in api["agents"]:
        text = _page(built, f"/docs/agents/{agent['slug']}/")
        assert agent["tier"] in text and agent["grade"] in text, agent["id"]


def test_one_page_per_visible_policy(built) -> None:
    for policy in built.site.policies:
        text = _page(built, f"/docs/policies/{policy.id}/")
        assert f'href="/coding/policies/{policy.id}/"' in text
        assert policy.source_url in text


def test_every_docs_page_names_engine_and_catalog(built) -> None:
    engine_ref, catalog_ref = built.site.framework_ref, built.site.catalog_ref
    for page in (built.out / "docs").rglob("index.html"):
        text = page.read_text(encoding="utf-8")
        assert f"/commit/{engine_ref}" in text, page
        assert f"/commit/{catalog_ref}" in text, page
    for twin in (built.out / "docs").rglob("index.md"):
        text = twin.read_text(encoding="utf-8")
        assert engine_ref[:12] in text and catalog_ref[:12] in text, twin
        assert DOCS["texts"]["ask_first"] in text, twin


def test_plugin_quickstart_shows_every_client_and_its_engine_steps(built) -> None:
    text = _page(built, DOCS["pages"]["quickstart-plugin"]["path"])
    for client in engine.client_ids():
        assert f"--client {client}" in text, client
        for step in engine.client_steps(client):
            if "command" in step:
                assert step["command"] in text, (client, step)


def test_repo_quickstart_lists_every_agent_sync_wires(built) -> None:
    text = _page(built, DOCS["pages"]["quickstart-repo"]["path"])
    for agent in engine.sync_vendors():
        assert f"<code>{engine.sync_agent_name(agent)}</code>" in text, agent


def test_cli_reference_has_every_engine_command(built) -> None:
    text = _page(built, DOCS["pages"]["cli"]["path"])
    for command in engine.cli_commands():
        assert f"<code>chock {command['name']}</code></h3>" in text, command["name"]


def test_docs_nav_is_in_the_header_and_marks_the_page(built) -> None:
    text = _page(built, "/docs/configure/")
    assert '<a href="/docs/" aria-current="page">Docs</a>' in text
    assert '<a href="/docs/configure/" aria-current="page">Configure</a>' in text
    home = (built.out / "index.html").read_text(encoding="utf-8")
    assert '<a href="/docs/">Docs</a>' in home


def test_llms_txt_links_every_docs_twin(built) -> None:
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    docs_part = llms.split("## Docs\n", 1)[1].split("\n## ", 1)[0]
    for twin in (built.out / "docs").rglob("index.md"):
        rel = "/" + twin.relative_to(built.out).as_posix()
        assert f"]({rel})" in docs_part, rel


def test_plugin_witness_never_clears_a_sync_claim() -> None:
    docs = {**DOCS, "surface_routes": {"plugin-hook": "plugin", "x": "sync"}}
    rows = [
        {
            "agent": "cursor",
            "surface": "plugin-hook",
            "client": "c",
            "date": "d",
            "method": "m",
        }
    ]
    original = engine.witness_ledger
    engine.witness_ledger = lambda: rows
    try:
        assert [r["route"] for r in docsfacts.ledger(docs)] == ["plugin"]
        rows[0]["surface"] = "unknown-surface"
        with pytest.raises(PageError, match="has no route"):
            docsfacts.ledger(docs)
    finally:
        engine.witness_ledger = original


def test_agent_pages_follow_the_install_pages_routes(built) -> None:
    """One source: docs agents take plugin, repo-hooks and reason from S-ALL's agent_routes."""
    routes = built.site.data["agent_routes"]["agents"]
    api = {a["id"]: a for a in _api(built)["agents"]}
    assert list(api) == [r["agent"] for r in routes]
    for row in routes:
        text = _page(built, f"/docs/agents/{api[row['agent']]['slug']}/")
        if row["plugin"]:
            assert f"--client {row['plugin']['client']}" in text, row["agent"]
        if row["sync"]:
            assert row["sync"]["command"] in text, row["agent"]
        if row["reason"]:
            assert row["reason"] in text.replace("&#x27;", "'"), row["agent"]


def test_snapshot_taken_at_another_engine_commit_is_refused(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    with pytest.raises(PageError, match="framework-ref"):
        docsource.load(data, "0" * 40)


def _fake_chock(root: Path) -> Path:
    """A git repo holding every file docs.yaml quotes, built from the committed snapshot."""
    root.mkdir()
    record = json.loads(
        (DATA / DOCS["source_dir"] / docsource.SOURCE_JSON).read_text(encoding="utf-8")
    )
    for path, entry in record["files"].items():
        if entry is None:
            continue
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        snap = DATA / DOCS["source_dir"] / entry["snapshot"]
        target.write_text(snap.read_text(encoding="utf-8"), encoding="utf-8")
    return root


def test_snapshot_round_trips_and_check_finds_drift(tmp_path: Path) -> None:
    chock = _fake_chock(tmp_path / "chock")
    ref = json.loads(
        (DATA / DOCS["source_dir"] / docsource.SOURCE_JSON).read_text(encoding="utf-8")
    )["engine_ref"]
    files = docsource.snapshot(chock, DOCS, ref)
    for name, text in files.items():
        committed = (DATA / DOCS["source_dir"] / name).read_text(encoding="utf-8")
        assert text == committed, name
    concepts = chock / "docs" / "concepts.md"
    concepts.write_text(
        concepts.read_text(encoding="utf-8").replace("## Gate", "## Gate\n\nNew line."),
        encoding="utf-8",
    )
    assert (
        docsource.snapshot(chock, DOCS, ref)["docs__concepts.md"]
        != files["docs__concepts.md"]
    )


def test_snapshot_refuses_a_missing_required_file(tmp_path: Path) -> None:
    chock = _fake_chock(tmp_path / "chock")
    (chock / "docs" / "concepts.md").unlink()
    with pytest.raises(PageError, match="concepts.md"):
        docsource.snapshot(chock, DOCS, "r")


def test_docsource_check_refuses_a_checkout_at_another_commit(tmp_path: Path) -> None:
    chock = _fake_chock(tmp_path / "chock")
    git = ["git", "-C", str(chock)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run(
        [*git, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "t"],
        check=True,
    )
    assert docsource.main(["--chock", str(chock), "--check"]) == 2


def _render(text: str) -> str:
    return str(Renderer(TEMPLATES, lambda href: "R:" + href).blocks(text))


def test_markdown_is_escaped_and_links_resolved() -> None:
    out = _render("Hi <script>x</script> [a](b.md) `c<d>` **e**\n")
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert '<a href="R:b.md">a</a>' in out
    assert "<code>c&lt;d&gt;</code>" in out and "<strong>e</strong>" in out


def test_markdown_link_cannot_inject_attributes() -> None:
    out = _render('[x](a"onclick=y)\n')
    assert '"onclick' not in out


def test_markdown_blocks() -> None:
    out = _render(
        "## T\n\n- one\n- two\n  more\n\n1. a\n2. b\n\n> q\n\n"
        "| A | B |\n| :--- | ---: |\n| `x|y` | z |\n\n```bash\nls <x>\n```\n\n## T\n"
    )
    assert '<h2 id="t">T</h2>' in out and '<h2 id="t-2">T</h2>' in out
    assert "<li>two more</li>" in out
    assert '<ol start="1"><li>a</li><li>b</li></ol>' in out
    assert "<blockquote><p>q</p>" in out
    assert '<td class="align-left"><code>x|y</code></td>' in out
    assert '<td class="align-right">z</td>' in out
    assert '<code class="language-bash">ls &lt;x&gt;</code>' in out


def test_sections_and_twin_links() -> None:
    text = "# Top\n\n## A\n\na\n\n```\n## not a heading\n```\n\n## B\n\n[l](x.md)\n"
    assert sections(text, ["B"]) == "## B\n\n[l](x.md)\n"
    assert "## not a heading" in sections(text, ["A"])
    with pytest.raises(PageError):
        sections(text, ["missing"])
    twin = rewrite_links(sections(text, ["A", "B"]), lambda h: "R:" + h, "ASK")
    assert "[l](R:x.md)" in twin and "ASK\n\n```" in twin


# --- SITE-1: a snapshot name or a quoted path stays in its folder -------------------------


def test_a_snapshot_name_that_leaves_the_folder_is_refused(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    source = data / DOCS["source_dir"] / docsource.SOURCE_JSON
    record = json.loads(source.read_text(encoding="utf-8"))
    (tmp_path / "escaped").write_text("outside", encoding="utf-8")
    first = next(path for path, entry in record["files"].items() if entry)
    record["files"][first] = {"snapshot": "../../../escaped"}
    source.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(PageError, match="'../../../escaped'"):
        docsource.load(data, record["engine_ref"])


def test_a_quoted_path_that_leaves_the_checkout_is_refused(tmp_path: Path) -> None:
    chock = _fake_chock(tmp_path / "chock")
    (tmp_path / "escaped.md").write_text("## Gate\n\noutside\n", encoding="utf-8")
    docs = json.loads(json.dumps(DOCS))
    docs["pages"]["overview"]["prose"][0]["file"] = "../escaped.md"
    with pytest.raises(PageError, match="'../escaped.md'"):
        docsource.snapshot(chock, docs, "r")
