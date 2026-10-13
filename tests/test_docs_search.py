"""SITE-SEARCH: the build-time docs search index, its byte budget and the search box markup."""

import json
import re
from pathlib import Path

import pytest
import yaml

from sitegen import docs
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
SEARCH = yaml.safe_load((ROOT / "data" / "docs.yaml").read_text(encoding="utf-8"))[
    "texts"
]["search"]
SCRIPT = ROOT / "static" / "js" / "search.js"


def _index_bytes(built) -> bytes:
    return (built.out / SEARCH["index"].lstrip("/")).read_bytes()


def _index(built) -> dict:
    return json.loads(_index_bytes(built))


def _docs_pages(built) -> list[Path]:
    return sorted((built.out / "docs").rglob("index.html"))


def test_index_is_within_its_byte_budget(built) -> None:
    size = len(_index_bytes(built))
    assert 0 < size <= SEARCH["budget_bytes"], f"{SEARCH['index']}: {size} bytes"


def test_build_refuses_an_index_over_budget(built, tmp_path: Path) -> None:
    texts = {"search": {**SEARCH, "budget_bytes": 10}}
    ctx = docs.Ctx(built.site, ROOT / "templates", {}, texts, {}, [], [])
    rows = [{"title": "t", "url": "/docs/", "excerpt": "e", "headings": []}]
    with pytest.raises(PageError, match="over its budget of 10"):
        docs._search_index(ctx, tmp_path, rows)
    assert not (tmp_path / SEARCH["index"].lstrip("/")).exists()


def test_index_has_one_row_per_docs_page(built) -> None:
    api = json.loads((built.out / "api" / "docs" / "index.json").read_text("utf-8"))
    index = _index(built)
    assert index["schema_version"] == 1
    assert [p["url"] for p in index["pages"]] == [p["path"] for p in api["pages"]]
    assert [p["title"] for p in index["pages"]] == [p["title"] for p in api["pages"]]
    assert len(index["pages"]) == len(_docs_pages(built))
    for page in index["pages"]:
        assert set(page) == {"title", "url", "excerpt", "headings"}


def test_every_row_points_at_a_built_page_and_its_headings(built) -> None:
    for page in _index(built)["pages"]:
        assert re.fullmatch(r"/docs/(?:[a-z0-9-]+/)*", page["url"]), page["url"]
        html = (built.out / page["url"].strip("/") / "index.html").read_text("utf-8")
        ids = re.findall(r'<h[23] id="([^"]+)"', html)
        assert [h["id"] for h in page["headings"]] == [
            i for i in ids if i in {h["id"] for h in page["headings"]}
        ]
        for heading in page["headings"]:
            assert heading["id"] in ids, f"{page['url']}#{heading['id']}"
            assert heading["text"].strip()


def test_excerpts_are_short_plain_text(built) -> None:
    for page in _index(built)["pages"]:
        excerpt = page["excerpt"]
        assert excerpt, page["url"]
        assert len(excerpt) <= SEARCH["excerpt_chars"] + 1, page["url"]
        # Plain text: no Markdown code marks and no runs of whitespace or newlines.
        assert not re.search(r"`|\s{2}|\n", excerpt), page["url"]


def test_policy_rows_use_the_policy_summary(built) -> None:
    rows = {p["url"]: p for p in _index(built)["pages"]}
    for policy in built.site.policies:
        row = rows.get(f"/docs/policies/{policy.id}/")
        if row is None:
            continue
        summary = " ".join(policy.description.replace("`", "").split())
        assert summary.startswith(row["excerpt"].removesuffix("…")), policy.id


def test_excerpt_is_cut_at_a_word_boundary() -> None:
    ctx = docs.Ctx(None, ROOT, {}, {"search": {"excerpt_chars": 12}}, {}, [], [])
    assert docs._excerpt(ctx, "short `one`") == "short one"
    assert docs._excerpt(ctx, "alpha beta, gamma delta") == "alpha beta…"


def test_every_docs_page_carries_the_search_box(built) -> None:
    for path in _docs_pages(built):
        html = path.read_text(encoding="utf-8")
        nav = html[html.index('<nav class="docs-nav"') :]
        nav = nav[: nav.index("</nav>")]
        assert f'data-index="{SEARCH["index"]}"' in nav, path
        assert (
            f'<p class="docs-search-fallback"><a href="/docs/">{SEARCH["fallback"]}</a>'
            in nav
        ), path
        assert '<div class="docs-search-box" hidden>' in nav, path
        assert '<label class="docs-search-label" for="docs-search-input">' in nav
        assert re.search(
            r'<input id="docs-search-input"[^>]* role="combobox" '
            r'aria-autocomplete="list" aria-expanded="false" '
            r'aria-controls="docs-search-list"',
            nav,
        ), path
        listbox = '<ul id="docs-search-list" class="docs-search-list" role="listbox"'
        assert listbox in nav, path
        status = '<p id="docs-search-status" class="visually-hidden" role="status">'
        assert status in nav, path
        assert '<script type="module" src="/js/search.js"></script>' in html, path


def test_search_box_only_on_docs_pages(built) -> None:
    for path in built.out.rglob("*.html"):
        if "docs" in path.relative_to(built.out).parts[:1]:
            continue
        html = path.read_text(encoding="utf-8")
        assert "docs-search" not in html and "/js/search.js" not in html, path


def test_index_url_is_a_site_path() -> None:
    assert re.fullmatch(r"/api/docs/[a-z]+\.json", SEARCH["index"])


def test_script_fetches_only_the_index_and_sends_nothing() -> None:
    code = SCRIPT.read_text(encoding="utf-8")
    assert code.count("fetch(") == 1
    assert "fetch(url.href" in code and "url.origin !== location.origin" in code
    for needle in ("sendBeacon", "XMLHttpRequest", "track(", "localStorage", "import "):
        assert needle not in code, needle
