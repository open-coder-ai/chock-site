"""UT-1 finding 6: code blocks get equal space above and below, and never break inside a token."""

import pytest
from conftest import assert_clean, collect, walk_paths

# Every code block, with its flow siblings: the gap above and the gap below.
_GAPS = """() => {
    const shown = e => e && e.getClientRects().length > 0
        && getComputedStyle(e).position !== "absolute";
    const sibling = (e, step) => {
        for (let s = e[step]; s; s = s[step]) if (shown(s)) return s;
        return null;
    };
    const out = [];
    for (const pre of document.querySelectorAll("main pre")) {
        if (!shown(pre)) continue;
        const prev = sibling(pre, "previousElementSibling");
        const next = sibling(pre, "nextElementSibling");
        if (!prev || !next) continue;
        const box = pre.getBoundingClientRect();
        const above = box.top - prev.getBoundingClientRect().bottom;
        const below = next.getBoundingClientRect().top - box.bottom;
        out.push({
            where: `${prev.tagName}.${prev.className} > PRE.${pre.className} > ${next.tagName}.${next.className}`,
            above: Math.round(above * 10) / 10,
            below: Math.round(below * 10) / 10,
        });
    }
    return out;
}"""

# Every place a code block's text wraps between two non-space characters.
_TOKEN_BREAKS = """() => {
    const out = [];
    const range = document.createRange();
    for (const pre of document.querySelectorAll("pre")) {
        if (pre.getClientRects().length === 0) continue;
        const walker = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT);
        let prevTop = null, prevChar = "";
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const text = node.textContent;
            for (let i = 0; i < text.length; i++) {
                const ch = text[i];
                if (ch === "\\n") { prevTop = null; prevChar = ""; continue; }
                range.setStart(node, i);
                range.setEnd(node, i + 1);
                const rect = range.getClientRects()[0];
                if (!rect) continue;
                const top = Math.round(rect.top);
                if (prevTop !== null && top > prevTop && /\\S/.test(ch) && /\\S/.test(prevChar)) {
                    out.push(`PRE.${pre.className}: breaks inside "${text.slice(Math.max(0, i - 12), i + 12)}"`);
                }
                prevTop = top;
                prevChar = ch;
            }
        }
    }
    return out;
}"""


def test_code_blocks_have_equal_space_above_and_below(browser, site_url) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    problems: list[str] = []
    try:
        page = context.new_page()
        collect(page, site_url)
        for path in walk_paths(page, site_url):
            page.goto(site_url + path)
            page.wait_for_load_state("networkidle")
            for gap in page.evaluate(_GAPS):
                if abs(gap["above"] - gap["below"]) > 2:
                    problems.append(
                        f"{path} {gap['where']}: {gap['above']} above, {gap['below']} below"
                    )
        assert_clean(page)
    finally:
        context.close()
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("width", (390, 1280, 1900))
def test_code_never_breaks_inside_a_token(browser, site_url, width) -> None:
    context = browser.new_context(viewport={"width": width, "height": 900})
    problems: list[str] = []
    try:
        page = context.new_page()
        collect(page, site_url)
        for path in walk_paths(page, site_url):
            page.goto(site_url + path)
            page.wait_for_load_state("networkidle")
            problems.extend(f"{path} {p}" for p in page.evaluate(_TOKEN_BREAKS))
        assert_clean(page)
    finally:
        context.close()
    assert not problems, "\n".join(problems)
