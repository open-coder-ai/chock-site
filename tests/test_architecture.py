"""ARCH-1..3: the Architecture docs section, its diagrams, links, twins and the cited-path check."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from sitegen import architecture, docsfacts, docsource, engine
from sitegen.pageparts import PageError
from sitegen.render import md

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ARCH = DATA / "architecture"
IDS = [
    "whole-train",
    "life-of-a-policy",
    "chock-internals",
    "agentseam-internals",
    "chock-catalog",
    "context-report",
    "chock-site",
    "release-train",
    "trust-boundaries",
]
TAGLINE = "Blocks your coding agent's wrong moves before they land."


def _page(built, diagram_id: str) -> str:
    return (built.out / "docs" / "architecture" / diagram_id / "index.html").read_text(
        encoding="utf-8"
    )


def _twin(built, diagram_id: str) -> str:
    return (built.out / "docs" / "architecture" / diagram_id / "index.md").read_text(
        encoding="utf-8"
    )


def _diagrams() -> dict[str, architecture.Diagram]:
    return {d.id: d for d in architecture.load()}


def test_both_diagrams_load_in_order() -> None:
    assert [d.id for d in architecture.load()] == IDS


def test_index_page_lists_each_diagram_and_carries_the_tagline(built) -> None:
    page = (built.out / "docs" / "architecture" / "index.html").read_text(
        encoding="utf-8"
    )
    for diagram_id in IDS:
        assert f'href="/docs/architecture/{diagram_id}/"' in page
    assert TAGLINE.replace("'", "&#x27;") in page
    twin = (built.out / "docs" / "architecture" / "index.md").read_text(
        encoding="utf-8"
    )
    for diagram_id in IDS:
        assert f"(/docs/architecture/{diagram_id}/index.md)" in twin


def test_docs_nav_names_architecture_once(built) -> None:
    page = (built.out / "docs" / "index.html").read_text(encoding="utf-8")
    assert page.count('href="/docs/architecture/"') == 1


@pytest.mark.parametrize("diagram_id", IDS)
def test_every_node_is_drawn_and_links_to_its_card(built, diagram_id: str) -> None:
    diagram = _diagrams()[diagram_id]
    page = _page(built, diagram_id)
    assert page.count('<svg class="arch-svg"') == 1
    for node in diagram.nodes:
        card = architecture.card_id(diagram, node)
        assert f'href="#{card}" data-node="{node["id"]}"' in page
        assert f'id="{card}"' in page
    assert page.count('<g class="arch-edge') == len(diagram.edges)


@pytest.mark.parametrize("diagram_id", IDS)
def test_main_path_is_marked_in_the_svg(built, diagram_id: str) -> None:
    diagram = _diagrams()[diagram_id]
    page = _page(built, diagram_id)
    steps = list(zip(diagram.path, diagram.path[1:]))
    for a, b in steps:
        assert f'class="arch-edge arch-on-path" data-from="{a}" data-to="{b}"' in page
    assert page.count("arch-edge arch-on-path") == len(steps)


@pytest.mark.parametrize("diagram_id", IDS)
def test_source_links_point_at_the_pinned_commit(built, diagram_id: str) -> None:
    diagram = _diagrams()[diagram_id]
    page = _page(built, diagram_id)
    twin = _twin(built, diagram_id)
    for node in diagram.nodes:
        repo, path = architecture.split_source(node["source"])
        url = (
            f"https://github.com/open-coder-ai/{repo}/blob/{diagram.pins[repo]}/{path}"
        )
        assert f'href="{url}"' in page
        assert f"]({url})" in twin


@pytest.mark.parametrize("diagram_id", IDS)
def test_twin_has_every_card_connection_and_step(built, diagram_id: str) -> None:
    diagram = _diagrams()[diagram_id]
    twin = _twin(built, diagram_id)
    labels = {n["id"]: n["label"] for n in diagram.nodes}
    for node in diagram.nodes:
        assert f"- **{node['label']}**" in twin
    for edge in diagram.edges:
        assert (
            f"- {labels[edge['from']]} → {labels[edge['to']]}: {edge['label']}" in twin
        )
    for i, step in enumerate(diagram.path, 1):
        assert f"{i}. {labels[step]}\n" in twin


@pytest.mark.parametrize("diagram_id", IDS)
def test_llms_files_carry_each_diagram_twin(built, diagram_id: str) -> None:
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    full = (built.out / "llms-full.txt").read_text(encoding="utf-8")
    assert f"(/docs/architecture/{diagram_id}/index.md)" in llms
    assert _twin(built, diagram_id).strip() in full


@pytest.mark.parametrize("diagram_id", IDS)
def test_diagram_json_is_published(built, diagram_id: str) -> None:
    published = built.out / "api" / "docs" / "architecture" / f"{diagram_id}.json"
    source = json.loads((ARCH / f"{diagram_id}.json").read_text(encoding="utf-8"))
    assert json.loads(published.read_text(encoding="utf-8")) == source
    assert f'href="/api/docs/architecture/{diagram_id}.json"' in _page(
        built, diagram_id
    )


def test_tier_facts_come_from_agentseam_tier_table(built) -> None:
    texts = architecture.load_texts()
    agents = docsfacts.agents(
        docsource.load_docs(DATA), built.site.data["agent_routes"]
    )
    rows = architecture.tier_facts(texts, agents)
    assert sum(int(re.search(r"\((\d+)\)", r).group(1)) for r in rows) == len(agents)
    for agent in agents:
        assert agent["tier"] == engine.tier_row(agent["id"])["tier"]
    # ARCH-3: diagrams 5-8 have no client box; diagram 9 is the fail-mode view.
    with_tiers = [
        "whole-train",
        "life-of-a-policy",
        "chock-internals",
        "agentseam-internals",
        "trust-boundaries",
    ]
    diagrams = _diagrams()
    for diagram_id in with_tiers:
        assert any(n.get("facts") == "tiers" for n in diagrams[diagram_id].nodes), (
            diagram_id
        )
        twin = _twin(built, diagram_id)
        for row in rows:
            assert f"  - {md(row)}\n" in twin


def test_no_hand_written_fail_modes_or_kill_switch() -> None:
    """Fail modes are agentseam's data; the tagline never says kill switch."""
    for file in [
        *ARCH.glob("*.json"),
        *(ROOT / "templates" / "architecture").glob("*"),
    ]:
        text = file.read_text(encoding="utf-8").lower()
        assert "kill switch" not in text, file
        if file.suffix == ".json":
            assert not re.search(r"fails? (open|closed)|fail-(open|closed)", text), file


# Diagram 1's boxes link to the diagram of the repo their source lives in.
REPO_DIAGRAM = {
    "chock": "chock-internals",
    "agentseam": "agentseam-internals",
    "chock-catalog": "chock-catalog",
    "chock-release": "release-train",
    "context-report": "context-report",
    "chock-site": "chock-site",
}


def test_whole_train_boxes_link_to_their_repo_diagram(built) -> None:
    diagram = _diagrams()["whole-train"]
    page = _page(built, "whole-train")
    twin = _twin(built, "whole-train")
    titles = {d.id: d.title for d in architecture.load()}
    linked = 0
    for node in diagram.nodes:
        repo, _ = architecture.split_source(node["source"])
        if repo not in REPO_DIAGRAM:
            assert "link" not in node
            continue
        target = REPO_DIAGRAM[repo]
        assert node["link"] == f"/docs/architecture/{target}/"
        card = page.split(f'id="{architecture.card_id(diagram, node)}"', 1)[1]
        card = re.split(r'<li class="arch-card |</ol>', card, maxsplit=1)[0]
        assert (
            f'<p class="arch-card-link"><a href="/docs/architecture/{target}/">'
            f"Its diagram: {titles[target]}</a></p>"
        ) in card
        assert (
            f"[Its diagram: {md(titles[target])}](/docs/architecture/{target}/index.md)"
            in twin
        )
        assert (built.out / "docs" / "architecture" / target / "index.html").exists()
        linked += 1
    assert linked == len(diagram.nodes) - 1


def test_link_base_is_the_architecture_page_path() -> None:
    docs = docsource.load_docs(DATA)
    assert (
        architecture.load_texts()["link_base"] == docs["pages"]["architecture"]["path"]
    )


def test_missing_links_names_a_link_to_no_diagram() -> None:
    texts = architecture.load_texts()
    diagrams = architecture.load()
    node = diagrams[0].nodes[0]
    node["link"] = "/docs/architecture/no-such-diagram/"
    want = (
        f"whole-train: node {node['id']!r} links to "
        "/docs/architecture/no-such-diagram/, which is no diagram"
    )
    assert architecture.missing_links(diagrams, texts) == [want]


def test_check_reports_a_broken_link(tmp_path: Path, monkeypatch, capsys) -> None:
    data = _data_with(
        tmp_path,
        lambda d: _node(d, "gate").update(link="/docs/architecture/nowhere/"),
    )
    load = architecture.load
    monkeypatch.setattr(
        architecture, "load", lambda **kw: load(data, kw["texts"], kw["links"])
    )
    clones = tmp_path / "clones"
    clones.mkdir()
    assert architecture.main(["--check", "--clones", str(clones)]) == 1
    err = capsys.readouterr().err
    assert (
        "life-of-a-policy: node 'gate' links to /docs/architecture/nowhere/, "
        "which is no diagram"
    ) in err


# --- validation -----------------------------------------------------------------


def _data_with(tmp_path: Path, edit) -> Path:
    data = tmp_path / "data"
    shutil.copytree(ARCH, data / "architecture")
    file = data / "architecture" / "life-of-a-policy.json"
    doc = json.loads(file.read_text(encoding="utf-8"))
    edit(doc)
    file.write_text(json.dumps(doc), encoding="utf-8")
    return data


def _node(doc, node_id):
    return next(n for n in doc["nodes"] if n["id"] == node_id)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (
            lambda d: d["edges"].append(
                {"from": "gate", "to": "nowhere", "label": "x"}
            ),
            "unknown node",
        ),
        (lambda d: d["path"].append("rules"), "has no edge"),
        (
            lambda d: _node(d, "gate").update(source="chock-release/check.py"),
            "pinned repo/path",
        ),
        (
            lambda d: _node(d, "gate").update(source="chock/../etc/passwd"),
            "pinned repo/path",
        ),
        (
            lambda d: _node(d, "gate").update(label="A label far too long for its box"),
            "too long",
        ),
        (lambda d: _node(d, "gate").update(kind="cloud"), "unknown kind"),
        (lambda d: _node(d, "gate").update(x=900), "outside the canvas"),
        (lambda d: d["pins"].update(chock="main"), "40-hex"),
        (lambda d: d["pins"].update({"chock-site": "0" * 40}), "pins no node cites"),
        (lambda d: d.update(colour="red"), "unknown ['colour']"),
        (lambda d: d.update(id="other"), "must match the file name"),
        (
            lambda d: _node(d, "gate").update(link="/docs/architecture/nowhere/"),
            "which is no diagram",
        ),
        (
            lambda d: _node(d, "gate").update(link="https://example.com/"),
            "must be another diagram's",
        ),
        (
            lambda d: _node(d, "gate").update(link="/docs/architecture/whole-train"),
            "must be another diagram's",
        ),
        (
            lambda d: _node(d, "gate").update(
                link="/docs/architecture/life-of-a-policy/"
            ),
            "must be another diagram's",
        ),
    ],
)
def test_load_refuses_a_broken_diagram(tmp_path: Path, edit, message: str) -> None:
    data = _data_with(tmp_path, edit)
    with pytest.raises(PageError, match=re.escape(message)):
        architecture.load(data, architecture.load_texts())


def test_unknown_fail_mode_has_no_wording() -> None:
    with pytest.raises(PageError, match="no wording for fail mode"):
        architecture.tier_facts(
            architecture.load_texts(),
            [{"name": "X", "tier": "block", "fail_mode": "sideways"}],
        )


def test_edges_start_and_end_on_box_borders() -> None:
    texts = architecture.load_texts()
    diagram = _diagrams()["life-of-a-policy"]
    edge = next(
        e for e in diagram.edges if (e["from"], e["to"]) == ("manifest", "compile")
    )
    start, end = architecture.edge_points(diagram, edge, texts)
    manifest, compile_ = _node(diagram.raw, "manifest"), _node(diagram.raw, "compile")
    assert start == (manifest["x"] + texts["node"]["w"], manifest["y"] + 28)
    assert end == (compile_["x"], compile_["y"] + 28)


# --- the cited-path check (local git repos, no network) --------------------------


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _repo(path: Path, files: list[str]) -> str:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    for name in files:
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text("x\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "fixture")
    return _git(path, "rev-parse", "HEAD")


def test_check_passes_when_every_cited_path_exists(tmp_path: Path) -> None:
    diagram = _diagrams()["life-of-a-policy"]
    clones = tmp_path / "clones"
    for repo in diagram.pins:
        files = [
            architecture.split_source(n["source"])[1]
            for n in diagram.nodes
            if n["source"].startswith(repo + "/")
        ]
        diagram.pins[repo] = _repo(clones / repo, files)
    assert architecture.missing_sources([diagram], lambda r: clones / r) == []


def test_check_names_a_missing_path_and_a_missing_commit(tmp_path: Path) -> None:
    diagram = _diagrams()["life-of-a-policy"]
    clones = tmp_path / "clones"
    for repo in diagram.pins:
        files = [
            architecture.split_source(n["source"])[1]
            for n in diagram.nodes
            if n["source"].startswith(repo + "/") and n["id"] != "verdict"
        ]
        diagram.pins[repo] = _repo(clones / repo, files)
    diagram.pins["agentseam"] = "f" * 40
    problems = architecture.missing_sources([diagram], lambda r: clones / r)
    assert (
        "life-of-a-policy: chock/src/chock/gate/runner/verdict.py is missing at chock@"
        in "\n".join(problems)
    )
    assert f"life-of-a-policy: agentseam has no commit {'f' * 40}" in problems
