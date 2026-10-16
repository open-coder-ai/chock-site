"""COPY-2: the "Where Chock sits" page leads with each category, dates every vendor quote and quotes chock for its own."""

import datetime as dt
import html
import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from sitegen import docs
from sitegen.docsmd import Renderer
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
LANDSCAPE = docs.load_landscape(DATA)
QUOTES = json.loads((DATA / "vendor-quotes.json").read_text(encoding="utf-8"))["quotes"]
# Chock's own quotes on this page, byte for byte as COPY-2 shipped them.
CHOCK_QUOTES = [
    "Agent identity, tokens, and spend budgets.",
    "Identity platforms and gateways own runtime credentials and quotas.",
    "`commit` is a git hook or CI gate that exits non-zero.",
    "`in-agent` is the agent's pre-tool hook: best-effort, and it fails open.",
    "`commit` is a git hook or CI gate that exits non-zero.",
    "Identity platforms and gateways own runtime credentials and quotas.",
    (
        "Chock models nine: `ambient-rule`, `git-hook`, `ci-gate`, `pre-tool-use`, `stop`,"
        " `agent-hooks`, `managed-setting`, `gateway`, `mcp-gateway`."
    ),
    "`commit` is a git hook or CI gate that exits non-zero.",
    "A **policy** is a self-contained folder under `.agents/policies/<id>/`",
    (
        "`commit` is a git hook or CI gate that exits non-zero. `in-agent` is the agent's"
        " pre-tool hook: best-effort, and it fails open."
    ),
    (
        "Chock models nine: `ambient-rule`, `git-hook`, `ci-gate`, `pre-tool-use`, `stop`,"
        " `agent-hooks`, `managed-setting`, `gateway`, `mcp-gateway`."
    ),
    "Watching an agent after the fact is an EDR product's job",
    "`commit` is a git hook or CI gate that exits non-zero.",
]
PAGE = DOCS["pages"]["where-chock-sits"]
LAYERS = [
    "Agent identity",
    "OS containment",
    "Gateways",
    "Inventory and monitoring",
    "Browser and edge",
]
# Our own wording only: vendor and chock quotes are theirs.
BANNED = re.compile(
    r"\bonly\b|\bbest\b(?!-)|\bfirst\b|\bleading\b|\bunique\b|\bmost\b|\bfastest\b"
    r"|kill switch|\bprice|\bpricing\b|\$",
    re.IGNORECASE,
)


def _page(built, name: str = "index.html") -> str:
    return (built.out / PAGE["path"].strip("/") / name).read_text(encoding="utf-8")


def _own_texts() -> list[str]:
    texts = [
        PAGE["title"],
        PAGE["description"],
        PAGE["intro"],
        *LANDSCAPE["texts"].values(),
    ]
    for layer in LANDSCAPE["layers"]:
        texts += [layer["heading"], layer["controls"], layer["chock_controls"]]
        texts += [layer["layer"], layer["chock"]]
    return texts


def test_page_is_in_the_nav_once_with_one_section_per_layer(built) -> None:
    nav = [k for g in DOCS["nav"] for k in g["pages"]]
    assert nav.count("where-chock-sits") == 1
    page, twin = _page(built), _page(built, "index.md")
    assert [layer["heading"] for layer in LANDSCAPE["layers"]] == LAYERS
    for heading in LAYERS:
        assert f">{html.escape(heading)}</h2>" in page, heading
        assert f"\n## {heading}\n" in twin, heading
    closing = LANDSCAPE["texts"]["closing"]
    assert (
        closing
        == "Chock is complementary to these layers, not a substitute for any of them."
    )
    assert closing in page and closing in twin


def test_every_example_quotes_its_vendor_with_source_and_date(built) -> None:
    page, twin = _page(built), _page(built, "index.md")
    named = [key for layer in LANDSCAPE["layers"] for key in layer["examples"]]
    assert sorted(named) == sorted(q["id"] for q in QUOTES)
    for q in QUOTES:
        assert q["url"].startswith("https://"), q["id"]
        assert f'href="{html.escape(q["url"])}"' in page, q["id"]
        assert f"]({q['url']})" in twin, q["id"]
        assert f"<q>{html.escape(q['quote'])}</q>" in page, q["id"]
        assert f"as of {q['checked']}" in page, q["id"]
        assert f"as of {q['checked']}" in twin, q["id"]


def test_each_layer_leads_with_its_category_and_names_no_vendor(built) -> None:
    twin = _page(built, "index.md")
    vendors = {q["vendor"] for q in QUOTES} | {q["product"] for q in QUOTES}
    texts = LANDSCAPE["texts"]
    for layer in LANDSCAPE["layers"]:
        for key in ("controls", "chock_controls", "layer", "chock"):
            assert not any(v in layer[key] for v in vendors), (layer["heading"], key)
        part = twin.split(f"\n## {layer['heading']}\n", 1)[1].split("\n## ", 1)[0]
        order = [
            texts["controls_heading"],
            texts["layer_catches"],
            texts["chock_catches"],
            texts["examples_heading"],
        ]
        at = [part.index(f"### {h}\n") for h in order]
        assert at == sorted(at), layer["heading"]
        assert part.index(layer["controls"]) < at[1], layer["heading"]
        assert part.index(layer["chock_controls"]) < at[1], layer["heading"]


def test_chock_quotes_are_byte_exact_and_a_change_fails_the_load(
    tmp_path: Path,
) -> None:
    quotes = [
        q["quote"]
        for layer in LANDSCAPE["layers"]
        for q in layer["layer_quotes"] + layer["chock_quotes"]
    ]
    assert quotes == CHOCK_QUOTES
    shutil.copy(DATA / "vendor-quotes.json", tmp_path / "vendor-quotes.json")
    data = yaml.safe_load((DATA / "landscape.yaml").read_text(encoding="utf-8"))
    data["layers"][0]["chock_quotes"][0]["quote"] = "`commit` is a git hook."
    (tmp_path / "landscape.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(PageError, match="chock quotes changed"):
        docs.load_landscape(tmp_path)


def test_every_chock_quote_is_shown_and_its_section_is_quoted_in_full(built) -> None:
    page, twin = _page(built), _page(built, "index.md")
    for layer in LANDSCAPE["layers"]:
        for q in layer["layer_quotes"] + layer["chock_quotes"]:
            assert f"> {q['quote']}\n" in twin, q["quote"]
            entries = [e for e in PAGE["prose"] if e["file"] == q["file"]]
            assert entries and q["section"] in entries[0]["sections"], q
            assert f"\n## {q['section']}\n" in twin, q["section"]
    assert "docs-quote" in page


def test_own_wording_has_no_superlative_pricing_or_kill_switch(built) -> None:
    for text in _own_texts():
        assert not BANNED.search(text), text
    assert "kill switch" not in _page(built).lower()


def test_loader_refuses_an_unknown_example_or_insecure_quote(tmp_path: Path) -> None:
    data = yaml.safe_load((DATA / "landscape.yaml").read_text(encoding="utf-8"))
    quotes = json.loads((DATA / "vendor-quotes.json").read_text(encoding="utf-8"))
    (tmp_path / "vendor-quotes.json").write_text(json.dumps(quotes), encoding="utf-8")
    data["layers"][0]["examples"].append("nobody")
    (tmp_path / "landscape.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(PageError, match="unknown examples"):
        docs.load_landscape(tmp_path)
    data["layers"][0]["examples"].pop()
    (tmp_path / "landscape.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    quotes["quotes"][0]["url"] = "http://example.com"
    (tmp_path / "vendor-quotes.json").write_text(json.dumps(quotes), encoding="utf-8")
    with pytest.raises(PageError, match="https"):
        docs.load_landscape(tmp_path)


def _ctx(
    prose: dict[str, str], today: dt.date = dt.date(2026, 10, 16)
) -> tuple[docs.Ctx, docs.Body]:
    ctx = docs.Ctx(
        site=SimpleNamespace(framework_ref="0" * 40),
        templates=ROOT / "templates",
        docs={"engine_repo": "https://github.com/open-coder-ai/chock"},
        texts={},
        prose=prose,
        agents=[],
        cli=[],
        page={"prose": [{"file": "README.md", "sections": ["Tiers"]}]},
        landscape=LANDSCAPE,
        today=today,
    )
    return ctx, docs.Body(Renderer(ROOT / "templates", lambda href: href))


def test_a_quote_chock_does_not_say_fails_the_build() -> None:
    ctx, body = _ctx({"README.md": "## Tiers\n\n`commit` is a git hook.\n"})
    ok = {"file": "README.md", "section": "Tiers", "quote": "`commit` is a git hook."}
    html_out, md_out = docs._quotes(ctx, body, [ok])
    assert "<code>commit</code> is a git hook." in html_out and "> `commit`" in md_out
    with pytest.raises(PageError, match="lacks"):
        docs._quotes(ctx, body, [ok | {"quote": "`commit` always blocks."}])
    with pytest.raises(PageError, match="not quoted on the page"):
        docs._quotes(ctx, body, [ok | {"section": "Other"}])


def test_a_quote_last_checked_over_183_days_ago_renders_an_out_of_date_note() -> None:
    quote = LANDSCAPE["quotes"]["island"] | {"checked": "2026-01-01"}
    fresh, _ = _ctx({}, today=dt.date(2026, 7, 3))  # 183 days later
    html_out, md_out = docs._example(fresh, quote)
    assert "as of 2026-01-01" in html_out and "docs-stale" not in html_out
    assert "out of date" not in md_out
    old, _ = _ctx({}, today=dt.date(2026, 7, 4))  # 184 days later
    html_out, md_out = docs._example(old, quote)
    note = "May be out of date: last checked 2026-01-01."
    assert f'<span class="docs-stale">{note}</span>' in html_out
    assert f"*{note}*" in md_out


def test_a_layer_reads_right_with_its_examples_removed() -> None:
    ctx, body = _ctx(
        {
            "README.md": "## Guardrails, not guarantees\n\n"
            "`commit` is a git hook or CI gate that exits non-zero. "
            "`in-agent` is the agent's pre-tool hook: best-effort, and it fails open.\n"
        }
    )
    layer = LANDSCAPE["layers"][1] | {"examples": []}
    ctx.page = {
        "prose": [{"file": "README.md", "sections": ["Guardrails, not guarantees"]}]
    }
    ctx.landscape = LANDSCAPE | {"layers": [layer]}
    ctx.site = SimpleNamespace(
        framework_ref="0" * 40, data={"site_url": "https://example.test"}
    )
    ctx.docs |= {"pages": {"agents": {"path": "/docs/agents/"}}}
    docs._landscape(ctx, body)
    md = "".join(body.md)
    assert layer["controls"] in md and layer["chock"] in md
    assert LANDSCAPE["texts"]["examples_heading"] not in md
