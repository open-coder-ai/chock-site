"""SITE-FIX: docs tables at phone width never break a word; wide ones scroll in a named region."""

import re

from conftest import assert_clean, collect

MOBILE = {"width": 390, "height": 844}

# Each cell's content width against its longest word, measured unwrapped in the word's own
# element so code chips keep their font. A hyphen is a legal break, so "fail-to-ask" counts
# as three words; anything else that wraps is a mid-word break.
_NARROW_CELLS = """() => {
    const out = [];
    for (const cell of document.querySelectorAll('.docs-table th, .docs-table td')) {
        const style = getComputedStyle(cell);
        const room = cell.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
        const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
        let widest = { word: '', width: 0 };
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            for (const word of node.textContent.split(/\\s+|(?<=-)/)) {
                if (!word) continue;
                const probe = document.createElement('span');
                probe.style.whiteSpace = 'nowrap';
                probe.textContent = word;
                node.parentElement.appendChild(probe);
                const width = probe.getBoundingClientRect().width;
                probe.remove();
                if (width > widest.width) widest = { word, width };
            }
        }
        if (widest.width > room + 0.5) {
            out.push(`${widest.word} needs ${widest.width.toFixed(1)}px, cell has ${room.toFixed(1)}px`);
        }
    }
    return out;
}"""


def _docs_paths(page, site_url: str) -> list[str]:
    xml = page.goto(site_url + "/sitemap.xml").body().decode("utf-8")
    paths = [
        loc[len("https://chock.sh") :] for loc in re.findall(r"<loc>([^<]+)</loc>", xml)
    ]
    return [p for p in paths if p.startswith("/docs/")]


def test_docs_tables_never_break_a_word_at_mobile_width(browser, site_url) -> None:
    context = browser.new_context(viewport=MOBILE)
    try:
        page = context.new_page()
        walked = 0
        for path in _docs_paths(page, site_url):
            page.goto(site_url + path)
            if not page.locator(".docs-table").count():
                continue
            walked += 1
            narrow = page.evaluate(_NARROW_CELLS)
            assert not narrow, f"{path}: words broken mid-word at 390px: {narrow[:5]}"
        assert walked >= 5, f"only {walked} docs pages had a table"
    finally:
        context.close()


def test_the_levels_table_keeps_its_words_whole(browser, site_url) -> None:
    """The table from the owner's report: "Level | Meaning" on /docs/."""
    context = browser.new_context(viewport=MOBILE, has_touch=True, is_mobile=True)
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + "/docs/")
        region = page.get_by_role("region", name="Table: Level, Meaning")
        assert region.count() == 1
        head = region.locator("thead th").first
        box = head.bounding_box()
        assert box is not None
        line = float(head.evaluate("e => parseFloat(getComputedStyle(e).lineHeight)"))
        # "Level" on one line: the cell is one line of text tall plus its padding.
        assert box["height"] < 2 * line + 20, f"Level header wraps: {box}"
        chip = region.locator("code", has_text="enforced-at-commit")
        chip_box = chip.bounding_box()
        assert chip_box is not None
        assert chip_box["height"] < 2 * line, f"code chip wraps: {chip_box}"
        assert page.evaluate(_NARROW_CELLS) == []
        assert_clean(page)
    finally:
        context.close()


def test_docs_tables_are_focusable_named_regions(browser, site_url) -> None:
    context = browser.new_context(viewport=MOBILE)
    try:
        page = context.new_page()
        for path in _docs_paths(page, site_url):
            page.goto(site_url + path)
            wraps = page.eval_on_selector_all(
                ".table-wrap:has(> .docs-table)",
                """ws => ws.map(w => ({
                    role: w.getAttribute('role'),
                    tabindex: w.tabIndex,
                    name: w.getAttribute('aria-label'),
                    heads: [...w.querySelectorAll('thead th')].map(th => th.textContent.trim()),
                }))""",
            )
            for wrap in wraps:
                assert wrap["role"] == "region", f"{path}: {wrap}"
                assert wrap["tabindex"] == 0, f"{path}: {wrap}"
                assert wrap["name"] == "Table: " + ", ".join(wrap["heads"]), (
                    f"{path}: {wrap}"
                )
    finally:
        context.close()


def test_a_wide_docs_table_scrolls_inside_its_region(browser, site_url) -> None:
    """Keyboard walk: Tab reaches an overflowing table and the arrow keys scroll it."""
    context = browser.new_context(viewport=MOBILE)
    try:
        page = context.new_page()
        for path in _docs_paths(page, site_url):
            page.goto(site_url + path)
            wide = page.evaluate(
                """() => [...document.querySelectorAll('.table-wrap:has(> .docs-table)')]
                    .findIndex(w => w.scrollWidth > w.clientWidth + 1)"""
            )
            if wide >= 0:
                break
        else:
            raise AssertionError("no docs table overflows at 390px to walk")
        region = page.locator(".table-wrap:has(> .docs-table)").nth(wide)
        assert not page.evaluate(
            "document.scrollingElement.scrollWidth > window.innerWidth"
        ), f"{path}: the page itself scrolls sideways"
        for _ in range(400):
            page.keyboard.press("Tab")
            if region.evaluate("e => e === document.activeElement"):
                break
        else:
            raise AssertionError(f"{path}: Tab never reached the wide table")
        page.keyboard.press("ArrowRight")
        page.wait_for_function(
            "e => e.scrollLeft > 0", arg=region.element_handle(), timeout=2000
        )
    finally:
        context.close()
