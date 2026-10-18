"""DOCS-2: How Chock works: its pages, and the diagrams and tables checked against the engine's code."""

import html
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from sitegen import architecture, docs, docsource, engine
from sitegen.docsmd import Renderer
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
HOW = DOCS["texts"]["how"]
REF = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
NEW_DIAGRAMS = ["lifecycle", "enforcement-surfaces", "stop-and-resume"]
EMITTERS = "chock/src/chock/compile/emitters/"


def _page(built, key: str, name: str = "index.html") -> str:
    path = DOCS["pages"][key]["path"].strip("/")
    return (built.out / path / name).read_text(encoding="utf-8")


def _diagram(diagram_id: str) -> architecture.Diagram:
    return next(d for d in architecture.load() if d.id == diagram_id)


def _ctx(prose: dict[str, str | None]) -> SimpleNamespace:
    return SimpleNamespace(
        prose=prose,
        texts=DOCS["texts"],
        docs=DOCS,
        site=SimpleNamespace(framework_ref=REF),
        templates=ROOT / "templates",
        t=lambda name, **tokens: docs.render_file(
            ROOT / "templates" / "docs" / f"{name}.html", **tokens
        ),
    )


def _body() -> docs.Body:
    return docs.Body(Renderer(ROOT / "templates", lambda href: href))


def test_how_chock_works_group_holds_its_pages_and_architecture() -> None:
    group = next(g for g in DOCS["nav"] if g["group"] == "How Chock works")
    assert group["pages"] == ["how-it-works", "surfaces", "stop", "architecture"]
    for key in group["pages"][:3]:
        assert DOCS["pages"][key]["path"].startswith("/docs/how-it-works/")


def test_new_diagrams_pin_chock_at_the_framework_ref() -> None:
    for diagram_id in NEW_DIAGRAMS:
        assert _diagram(diagram_id).pins["chock"] == REF, diagram_id


def test_new_diagrams_cite_files_the_installed_engine_has() -> None:
    for diagram_id in NEW_DIAGRAMS:
        for node in _diagram(diagram_id).nodes:
            repo, path = architecture.split_source(node["source"])
            if repo == "chock":
                assert engine.engine_source(path), node["source"]


def test_surface_diagram_follows_the_compilers_emitters() -> None:
    """Each emitter file has a box, and the arrow to it names exactly the surfaces it writes."""
    diagram = _diagram("enforcement-surfaces")
    by_source = {n["source"]: n["id"] for n in diagram.nodes}
    wanted: dict[str, list[str]] = {}
    for row in engine.surface_rows():
        if row["emitter"]:
            wanted.setdefault(row["emitter"], []).append(row["surface"])
    emitter_nodes = {s for s in by_source if s.startswith(EMITTERS)}
    assert emitter_nodes == {f"chock/{path}" for path in wanted}
    labels = {(e["from"], e["to"]): e["label"] for e in diagram.edges}
    for path, surfaces in wanted.items():
        assert labels[("compile", by_source[f"chock/{path}"])] == ", ".join(surfaces)
    compile_card = next(n["card"] for n in diagram.nodes if n["id"] == "compile")
    for row in engine.surface_rows():
        if not row["emitter"]:
            assert f"The {row['surface']} hook point has no emitter" in compile_card


def test_lifecycle_check_step_names_every_check_in_order() -> None:
    card = next(n["card"] for n in _diagram("lifecycle").nodes if n["id"] == "check")
    assert ", ".join(engine.check_names()) in card


def test_how_it_works_lists_the_lifecycle_steps_and_the_diagrams(built) -> None:
    page, twin = _page(built, "how-it-works"), _page(built, "how-it-works", "index.md")
    lifecycle = _diagram("lifecycle")
    nodes = {n["id"]: n for n in lifecycle.nodes}
    for step in lifecycle.path:
        label = nodes[step]["label"]
        if nodes[step].get("code"):
            assert f"><code>{html.escape(label)}</code></a>" in page, step
            assert f"[`{label}`](" in twin, step
        else:
            assert f">{html.escape(label)}</a>" in page, step
            assert f"[{label}](" in twin, step
    for diagram_id in HOW["diagrams"]:
        assert f'href="/docs/architecture/{diagram_id}/"' in page
        assert f"/docs/architecture/{diagram_id}/index.md)" in twin
    assert "/docs/decision-log.md" in page


def test_surfaces_page_has_every_engine_surface_and_its_emitter(built) -> None:
    page, twin = _page(built, "surfaces"), _page(built, "surfaces", "index.md")
    for row in engine.surface_rows():
        assert f"<code>{row['surface']}</code>" in page, row["surface"]
        assert f"| `{row['surface']}` |" in twin, row["surface"]
        if row["emitter"]:
            assert f"/blob/{REF}/{row['emitter']}" in page, row["emitter"]


def test_a_surface_the_docs_do_not_list_fails_the_build(monkeypatch) -> None:
    prose = docsource.load(DATA, REF)
    ctx = _ctx(prose)
    rows = engine.surface_rows()
    docs._surfaces(ctx, _body())
    monkeypatch.setattr(
        engine,
        "surface_rows",
        lambda: [
            *rows,
            {"surface": "new-one", "emitter": None, "agents": [], "credited": True},
        ],
    )
    with pytest.raises(PageError, match="lists surfaces"):
        docs._surfaces(ctx, _body())


def test_stop_page_shows_both_commands_and_the_engines_limits(built) -> None:
    page, twin = _page(built, "stop"), _page(built, "stop", "index.md")
    facts = engine.stop_facts()
    assert html.escape(facts["limits"]) in page and facts["limits"] in twin
    for name in HOW["help_commands"]:
        usage = next(c for c in engine.cli_commands() if c["name"] == name)["help"]
        assert html.escape(usage) in page
        assert usage.split("\n\n", 1)[0] in twin
    assert f"/blob/{REF}/{HOW['stop_file']}" in page


def test_every_stop_fact_quote_stands_in_its_source() -> None:
    prose = docsource.load(DATA, REF)
    for item in HOW["facts"]:
        for source in item["sources"]:
            if "quote" not in source:
                continue
            path = source["file"]
            text = (
                engine.engine_source(path) if path.startswith("src/") else prose[path]
            )
            assert docs._flat(source["quote"]) in docs._flat(text), source


def test_a_quote_the_engine_does_not_say_fails_the_build() -> None:
    ctx = _ctx(docsource.load(DATA, REF))
    with pytest.raises(PageError, match="does not say"):
        docs._check_quotes(
            ctx, [{"file": "src/chock/stop.py", "quote": "never refused"}]
        )
    with pytest.raises(PageError, match="does not say"):
        docs._check_quotes(ctx, [{"file": "docs/stop.md", "quote": "never refused"}])


def test_stop_facts_must_name_the_engines_files(monkeypatch) -> None:
    ctx = _ctx(docsource.load(DATA, REF))
    facts = engine.stop_facts()
    monkeypatch.setattr(
        engine, "stop_facts", lambda: facts | {"confirm_word": "anywhere"}
    )
    with pytest.raises(PageError, match="never names"):
        docs._stop_facts(ctx, _body())


def test_engine_source_refuses_paths_outside_the_engine() -> None:
    for path in ("README.md", "src/chock/../../etc/passwd"):
        with pytest.raises(ValueError):
            engine.engine_source(path)
