"""COPY-2: the "Where Chock sits" page attributes every vendor claim and quotes chock for its own."""

import html
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
LANDSCAPE = yaml.safe_load((DATA / "landscape.yaml").read_text(encoding="utf-8"))
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
        texts += [layer["heading"], layer["layer"], layer["chock"]]
        texts += [p["says"] for p in layer["products"]]
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


def test_every_vendor_claim_names_its_vendor_and_links_its_source(built) -> None:
    page, twin = _page(built), _page(built, "index.md")
    for layer in LANDSCAPE["layers"]:
        for product in layer["products"]:
            assert product["says"].startswith(product["vendor"] + " "), product["name"]
            assert product["url"].startswith("https://"), product["name"]
            assert f'href="{html.escape(product["url"])}"' in page, product["name"]
            assert f"]({product['url']})" in twin, product["name"]
    assert LANDSCAPE["fetched"] in page and LANDSCAPE["fetched"] in twin


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


def test_loader_refuses_an_unattributed_or_insecure_claim(tmp_path: Path) -> None:
    shutil.copy(DATA / "landscape.yaml", tmp_path / "landscape.yaml")
    data = yaml.safe_load((tmp_path / "landscape.yaml").read_text(encoding="utf-8"))
    data["layers"][0]["products"][0]["says"] = "Agent identities are accounts."
    (tmp_path / "landscape.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(PageError, match="must open with"):
        docs.load_landscape(tmp_path)
    data["layers"][0]["products"][0]["says"] = "Microsoft says so."
    data["layers"][0]["products"][0]["url"] = "http://example.com"
    (tmp_path / "landscape.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(PageError, match="https"):
        docs.load_landscape(tmp_path)


def _ctx(prose: dict[str, str]) -> tuple[docs.Ctx, docs.Body]:
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
