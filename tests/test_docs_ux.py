"""SITE-UX: callouts, path tabs, copy buttons and the "On this page" list on docs pages."""

import re
from pathlib import Path

import pytest
import yaml

from sitegen.docsmd import Renderer, first_code
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
DOCS = yaml.safe_load((ROOT / "data" / "docs.yaml").read_text(encoding="utf-8"))
TEXTS = DOCS["texts"]
LABELS = TEXTS["callouts"]
HEADING_RE = re.compile(r'<h([23]) id="([^"]+)"')
TOC_RE = re.compile(r'<li class="docs-toc-h([23])"><a href="#([^"]+)">')


def _render(text: str, callouts: dict[str, str] | None = LABELS) -> str:
    return str(Renderer(TEMPLATES, lambda href: href, callouts=callouts).blocks(text))


def _page(built, path: str, name: str = "index.html") -> str:
    return (built.out / path.strip("/") / name).read_text(encoding="utf-8")


def _docs_pages(built) -> list[Path]:
    return sorted((built.out / "docs").rglob("index.html"))


# ----- callouts -----


@pytest.mark.parametrize("kind", ["note", "tip", "warning"])
def test_callout_is_a_labelled_note(kind: str) -> None:
    out = _render(f"> [!{kind.upper()}]\n> Read *this* <b>first</b>.\n")
    assert out == (
        f'<div class="callout callout-{kind}" role="note">'
        f'<p class="callout-title">{LABELS[kind]}</p>'
        "<p>Read <em>this</em> &lt;b&gt;first&lt;/b&gt;.</p>\n</div>\n"
    )


def test_callout_keeps_its_blocks() -> None:
    out = _render("> [!Tip]\n> one\n>\n> - a\n> - b\n")
    assert out.startswith('<div class="callout callout-tip" role="note">')
    assert "<p>one</p>" in out and "<ul><li>a</li><li>b</li></ul>" in out


def test_plain_blockquote_is_not_a_callout() -> None:
    out = _render("> [!NOTE] inline\n> text\n")
    assert out.startswith("<blockquote>") and "callout" not in out


def test_unknown_callout_is_refused() -> None:
    with pytest.raises(PageError, match=r"\[!CAUTION\]"):
        _render("> [!CAUTION]\n> x\n")
    with pytest.raises(PageError):
        _render("> [!NOTE]\n> x\n", callouts=None)


def test_evidence_notice_is_a_warning_callout(built) -> None:
    page = _page(built, "/docs/quickstart/plugin/")
    notices = re.findall(
        r'<div class="callout callout-warning" role="note">'
        r'<p class="callout-title">[^<]+</p><p>[^<]+<a href="https://',
        page,
    )
    clients = built.site.data["builder_clients"]["clients"].values()
    assert len(notices) == len([c for c in clients if c["evidence"]]) > 0
    assert "docs-notice" not in page


# ----- tabs -----


def test_first_code_takes_the_first_fenced_block() -> None:
    text = "## A\n\nx\n\n  ```bash\n  ls <a>\n  pwd\n  ```\n\n```\nlater\n```\n"
    assert first_code(text) == ("bash", "ls <a>\npwd")
    with pytest.raises(PageError):
        first_code("## A\n\nno code\n")


def test_overview_has_a_tab_per_path_with_its_commands(built) -> None:
    page = _page(built, "/docs/")
    tabs = re.search(
        r'<div class="docs-tabs" data-label="([^"]+)">(.*?)\n</div>\s*</section>',
        page,
        re.DOTALL,
    )
    assert tabs and tabs.group(1) == TEXTS["paths_heading"]
    panels = re.findall(
        r'<div class="docs-tab-panel" id="([^"]+)"><h3 class="docs-tab-heading">([^<]+)</h3>',
        tabs.group(2),
    )
    assert [title for _, title in panels] == [p["title"] for p in TEXTS["paths"]]
    plugin, repo = tabs.group(2).split('<div class="docs-tab-panel"')[1:]
    install = "pip install &quot;chock @ git+https://github.com/open-coder-ai/chock@"
    assert install in plugin and install in repo
    assert "--client &lt;agent&gt;" in plugin and "chock init" not in plugin
    assert "chock init ." in repo and "chock sync --repo ." in repo
    for path in TEXTS["paths"]:
        href = DOCS["pages"][path["page"]]["path"]
        assert f'<a href="{href}">' in (
            plugin if path["page"].endswith("plugin") else repo
        )


def test_tab_headings_stay_out_of_the_toc(built) -> None:
    page = _page(built, "/docs/")
    for path in TEXTS["paths"]:
        panel_id = re.search(
            rf'<div class="docs-tab-panel" id="([^"]+)"><h3 class="docs-tab-heading">{path["title"]}<',
            page,
        ).group(1)
        assert f'href="#{panel_id}"' not in page


def test_overview_twin_asks_before_each_tabs_commands(built) -> None:
    twin = _page(built, "/docs/", "index.md")
    for path in TEXTS["paths"]:
        block = twin.split(f"### {path['title']}\n\n", 1)[1]
        assert block.startswith(f"{TEXTS['ask_code']}\n\n    pip install ")
    assert "    chock init .\n" in twin


# ----- copy buttons and the "On this page" list -----


def test_every_docs_page_loads_docs_js_and_names_the_copy_label(built) -> None:
    for page in _docs_pages(built):
        text = page.read_text(encoding="utf-8")
        assert '<script type="module" src="/js/docs.js"></script>' in text, page
        assert f'<article class="docs-main" data-copy-label="{TEXTS["copy"]}">' in text
    js = (built.out / "js" / "docs.js").read_text(encoding="utf-8")
    assert "track(" not in js and "sendBeacon" not in js


def test_toc_lists_the_pages_h2_and_h3_in_order(built) -> None:
    pages = _docs_pages(built)
    with_toc = 0
    for page in pages:
        text = page.read_text(encoding="utf-8")
        article = text.split('<article class="docs-main"', 1)[1]
        headings = [(int(lv), i) for lv, i in HEADING_RE.findall(article)]
        toc = [(int(lv), i) for lv, i in TOC_RE.findall(text)]
        if len(headings) < 2:
            assert '<nav class="docs-toc"' not in text, page
            continue
        with_toc += 1
        assert toc == headings, page
        assert text.count('<nav class="docs-toc" aria-label="On this page">') == 1
        # The list sits between the docs nav and the article, open until docs.js says otherwise.
        assert text.index('class="docs-nav"') < text.index('class="docs-toc"')
        assert text.index('class="docs-toc"') < text.index('class="docs-main"')
        assert '<details class="docs-toc-box" open>' in text
    assert with_toc >= len(pages) - 2


def test_toc_headings_from_engine_docs_are_listed(built) -> None:
    page = _page(built, "/docs/quickstart/repo/")
    for anchor in ("prerequisites", "2-onboard-a-repository", "3-install-a-policy"):
        assert f'<a href="#{anchor}">' in page
