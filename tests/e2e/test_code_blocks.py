"""UT-1 finding 6: boxes in text flow get equal space above and below; code never breaks inside a token."""

import pytest
from conftest import assert_clean, collect, walk_paths

from tests.fixtures.untested import CLIENT

# Code blocks and boxed notes that sit in text flow (the classes site.css spaces alike).
BOXES = (
    "pre, .quiz-note, .client-untested, .client-evidence, .note-card,"
    " .noscript-note, .friction-note, .author-errors"
)

# Every box with a flow neighbour on both sides, and the gaps to them. A side with no
# visible sibling climbs through unboxed wrappers; a boxed container's edge ends the climb.
_GAPS = """selector => {
    const main = document.querySelector("main");
    const shown = e => e && e.getClientRects().length > 0
        && getComputedStyle(e).position !== "absolute";
    const boxed = e => {
        const cs = getComputedStyle(e);
        return parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.paddingTop) > 0
            || cs.backgroundColor !== "rgba(0, 0, 0, 0)" || cs.display !== "block";
    };
    const near = (e, step) => {
        for (let x = e; x && x !== main; x = x.parentElement) {
            for (let s = x[step]; s; s = s[step]) if (shown(s)) return s;
            if (boxed(x.parentElement)) return null;
        }
        return null;
    };
    const out = [];
    for (const box of document.querySelectorAll(`main :is(${selector})`)) {
        if (!shown(box)) continue;
        const prev = near(box, "previousElementSibling");
        const next = near(box, "nextElementSibling");
        if (!prev || !next) continue;
        const r = box.getBoundingClientRect();
        const name = e => `${e.tagName}.${e.className}`;
        out.push({
            where: `${name(prev)} > ${name(box)} > ${name(next)}`,
            above: Math.round((r.top - prev.getBoundingClientRect().bottom) * 10) / 10,
            below: Math.round((next.getBoundingClientRect().top - r.bottom) * 10) / 10,
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


def _gap_problems(page, where: str) -> list[str]:
    """Each box on the page whose gap above and gap below differ by more than 2 px."""
    return [
        f"{where} {gap['where']}: {gap['above']} above, {gap['below']} below"
        for gap in page.evaluate(_GAPS, BOXES)
        if abs(gap["above"] - gap["below"]) > 2
    ]


def test_boxes_have_equal_space_above_and_below(
    browser, site_url, untested_site_url
) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    problems: list[str] = []
    try:
        page = context.new_page()
        collect(page, site_url)
        for path in walk_paths(page, site_url):
            page.goto(site_url + path)
            page.wait_for_load_state("networkidle")
            problems += _gap_problems(page, path)
        # Notes that only show in a state: a quiz answer with a note.
        page.goto(site_url + "/repos/builder/")
        page.get_by_role("radio", name="GitLab").check()
        page.wait_for_selector(".quiz-note:not([hidden])")
        problems += _gap_problems(page, "repos quiz, GitLab")
        assert_clean(page)
        # An untested agent's notes, on the test-only site where CLIENT is untested.
        other = context.new_page()
        collect(other, untested_site_url)
        other.goto(untested_site_url + "/coding/builder/#preset=git-hygiene")
        other.wait_for_selector(".sel-item")
        other.locator(f"label[for='client-{CLIENT}']").click()
        other.wait_for_selector(".client-untested:not([hidden])")
        other.wait_for_selector(".client-evidence:not([hidden])")
        problems += _gap_problems(other, f"builder, untested {CLIENT}")
        other.goto(untested_site_url + "/coding/install/")
        other.wait_for_load_state("networkidle")
        problems += _gap_problems(other, f"install, untested {CLIENT}")
        assert_clean(other)
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
