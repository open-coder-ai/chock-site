"""COPY-3: "What Chock doesn't stop" lists every known bypass, each sourced from chock's own files."""

import html
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from sitegen import docs, docsource, engine
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
PAGE = DOCS["pages"]["bypasses"]
TEXTS = DOCS["texts"]["bypass"]
REF = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()


def _page(built, name: str = "index.html") -> str:
    return (built.out / PAGE["path"].strip("/") / name).read_text(encoding="utf-8")


def _section(page: str, heading: str) -> str:
    """The HTML of the docs section under one h2."""
    start = page.index(f">{html.escape(heading)}</h2>")
    return page[start : page.index("</section>", start)]


def test_page_has_one_nav_entry_and_every_item(built) -> None:
    assert sum(g["pages"].count("bypasses") for g in DOCS["nav"]) == 1
    page, twin = _page(built), _page(built, "index.md")
    for item in TEXTS["items"]:
        assert f">{html.escape(item['heading'])}</h2>" in page, item["heading"]
        assert f"## {item['heading']}\n" in twin, item["heading"]
    overview = (built.out / "docs" / "index.html").read_text(encoding="utf-8")
    assert f'href="{PAGE["path"]}"' in overview
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    assert f"]({PAGE['path']}index.md)" in llms


def test_every_quote_stands_in_the_snapshot() -> None:
    prose = docsource.load(DATA, REF)
    for item in TEXTS["items"]:
        for source in item["sources"]:
            if "quote" in source:
                text = prose[source["file"]]
                assert text is not None, source["file"]
                assert docs._flat(source["quote"]) in docs._flat(text), source


def _ctx(prose: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        prose=prose,
        texts=DOCS["texts"],
        docs=DOCS,
        site=SimpleNamespace(framework_ref=REF),
        t=lambda name, **tokens: docs.render_file(
            ROOT / "templates" / "docs" / f"{name}.html", **tokens
        ),
    )


def test_a_quote_chock_does_not_say_fails_the_build() -> None:
    ctx = _ctx({"SECURITY.md": "Git hooks\n> are bypassable."})
    html_out, md = docs._sources(
        ctx, [{"file": "SECURITY.md", "quote": "hooks are bypassable."}]
    )
    assert f"/blob/{REF}/SECURITY.md" in html_out and f"/blob/{REF}/SECURITY.md" in md
    with pytest.raises(PageError, match="does not say"):
        docs._sources(ctx, [{"file": "SECURITY.md", "quote": "hooks are airtight."}])
    with pytest.raises(PageError, match="does not say"):
        docs._sources(ctx, [{"file": "README.md", "quote": "anything"}])


def test_fail_open_hosts_come_from_agentseam_tier_data(built) -> None:
    section = _section(_page(built), "Hosts whose hook fails open")
    for agent in engine.matrix_agents():
        shown = f'href="/docs/agents/{agent.replace("_", "-")}/"' in section
        fails_open = engine.tier_row(agent)["fail_mode"] == TEXTS["fail_open"]
        assert shown == fails_open, agent


def test_agents_without_a_route_show_the_engines_reason(built) -> None:
    section = _section(_page(built), "Agents with no hook, or not wired")
    routes = built.site.data["agent_routes"]["agents"]
    for route in routes:
        shown = f'href="/docs/agents/{route["agent"].replace("_", "-")}/"' in section
        assert shown == bool(route["reason"]), route["agent"]
        if route["reason"]:
            assert html.escape(route["reason"]) in section


def test_turn_end_counts_come_from_each_agents_labels(built) -> None:
    section = _section(_page(built), "Writes judged only at turn end")
    clients = built.site.data["builder_clients"]
    seen = 0
    for client in clients["order"]:
        about = clients["clients"][client]
        count = sum(
            TEXTS["turn_end_marker"] in label["says"]
            for label in about["labels"].values()
        )
        row = f'<th scope="row">{html.escape(about["name"])}</th>'
        assert (row in section) == bool(count), client
        seen += bool(count)
    assert seen


def test_page_never_overclaims(built) -> None:
    text = _page(built) + _page(built, "index.md")
    assert not re.search(r"kill[ -]?switch", text, re.IGNORECASE)
    assert "friction, not a security boundary" in text
    assert "stop switch" not in text.lower()


def test_checked_sections_are_snapshotted_but_not_shown(built) -> None:
    files = docsource.wanted(DOCS)
    for entry in PAGE["checked"]:
        assert set(entry["sections"]) <= set(files[entry["file"]]["sections"])
    assert "Threat model" in docsource.load(DATA, REF)["SECURITY.md"]
    assert "Threat model" not in _page(built)
