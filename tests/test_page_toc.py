"""SITE-TOC: the FAQ's "On this page" list is the docs list, built from faq.yaml."""

import html
import re

from sitegen import docs
from tests.conftest import ROOT

HEADING_RE = re.compile(r'<h([23]) id="([^"]+)"')
TOC_RE = re.compile(r'<li class="docs-toc-h([23])"><a href="#([^"]+)">([^<]*)</a>')


def _page(built, path: str) -> str:
    return (built.out / path.strip("/") / "index.html").read_text(encoding="utf-8")


def test_faq_toc_lists_every_group_and_question_in_page_order(built) -> None:
    page = _page(built, "/faq/")
    toc = page[
        page.index('<nav class="docs-toc"') : page.index(
            "</nav>", page.index('<nav class="docs-toc"')
        )
    ]
    listed = [(level, id_) for level, id_, _ in TOC_RE.findall(toc)]
    article = page[
        page.index('<div class="toc-main">') : page.index('<nav class="docs-toc"')
    ]
    assert listed == HEADING_RE.findall(article)
    faq = built.site.data["faq"]
    assert len(listed) == len(faq["groups"]) + len(faq["questions"])
    texts = [html.unescape(text) for _, _, text in TOC_RE.findall(toc)]
    assert [q["q"] for q in faq["questions"]] == [
        t for (level, _), t in zip(listed, texts, strict=True) if level == "3"
    ]


def test_faq_toc_title_comes_from_data_and_docs_js_loads(built) -> None:
    page = _page(built, "/faq/")
    title = html.escape(built.site.data["faq"]["toc_title"])
    assert f'<nav class="docs-toc" aria-label="{title}">' in page
    assert '<script type="module" src="/js/docs.js"></script>' in page


def test_toc_markup_is_the_docs_partial(built) -> None:
    rendered = str(
        docs.toc_nav(ROOT / "templates", "T<", [(2, "a", "A&"), (3, "b", "B")])
    )
    assert rendered.rstrip("\n") == (
        '<nav class="docs-toc" aria-label="T&lt;"><details class="docs-toc-box" open>'
        '<summary class="docs-toc-title mono">T&lt;</summary><ul>'
        '<li class="docs-toc-h2"><a href="#a">A&amp;</a></li>'
        '<li class="docs-toc-h3"><a href="#b">B</a></li></ul></details></nav>'
    )


def test_pages_without_the_empty_right_half_get_no_toc(built) -> None:
    for path in (
        "/security/",
        "/for-agents/",
        "/report/",
        "/general/",
        "/coding/",
        "/repos/",
    ):
        assert 'class="docs-toc"' not in _page(built, path), path
