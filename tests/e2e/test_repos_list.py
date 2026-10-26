"""SITE-LISTS: the name + id policy list on /repos/ in both themes, at 1280 and 390 px."""

import re

import yaml
from conftest import ROOT, assert_clean, collect, screenshot
from playwright.sync_api import expect

TIERS = yaml.safe_load((ROOT / "data" / "repos.yaml").read_text(encoding="utf-8"))[
    "tiers"
]
SIZES = {
    "desktop": {"width": 1280, "height": 900},
    "mobile": {"width": 390, "height": 844},
}

_LIST = """() => {
    const rgb = c => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
    const lum = c => {
        const [r, g, b] = rgb(c).map(v => {
            v /= 255;
            return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const contrast = (a, b) => {
        const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
        return (x + 0.05) / (y + 0.05);
    };
    const backdrop = e => {
        for (let a = e; a; a = a.parentElement) {
            const bg = getComputedStyle(a).backgroundColor;
            if (bg !== "rgba(0, 0, 0, 0)" && bg !== "transparent") return bg;
        }
        return "rgb(255, 255, 255)";
    };
    const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent");
    const probe = document.createElement("span");
    probe.style.color = accent;
    document.body.append(probe);
    const accentRgb = getComputedStyle(probe).color;
    probe.remove();
    return [...document.querySelectorAll(".repos-list")].map(list => ({
        rows: [...list.children].map(li => {
            const a = li.querySelector("a");
            const id = li.querySelector(".repos-id");
            const box = li.getBoundingClientRect();
            const ab = a.getBoundingClientRect();
            const ib = id.getBoundingClientRect();
            const as = getComputedStyle(a);
            const is = getComputedStyle(id);
            return {
                left: box.left, top: box.top, height: box.height,
                divider: parseFloat(getComputedStyle(li).borderBottomWidth),
                nameContrast: contrast(as.color, backdrop(li)),
                idContrast: contrast(is.color, backdrop(li)),
                nameAccent: as.color === accentRgb,
                underlined: as.textDecorationLine.includes("underline"),
                idBelow: ib.top >= ab.bottom - 1,
                idPill: is.backgroundColor !== "rgba(0, 0, 0, 0)" || parseFloat(is.borderTopWidth) > 0,
                idMono: /mono/i.test(is.fontFamily),
                idSmaller: parseFloat(is.fontSize) < parseFloat(as.fontSize),
                nameSmaller: parseFloat(as.fontSize) < parseFloat(getComputedStyle(document.body).fontSize),
            };
        }),
    }));
}"""


def _rows_by_top(rows: list[dict]) -> list[list[dict]]:
    """List items grouped into visual rows by their top edge."""
    lines: dict[int, list[dict]] = {}
    for row in rows:
        lines.setdefault(round(row["top"]), []).append(row)
    return [lines[k] for k in sorted(lines)]


def test_list_layout_contrast_and_screenshots(browser, site_url) -> None:
    for size, viewport in SIZES.items():
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            collect(page, site_url)
            page.goto(site_url + "/repos/")
            where = size
            screenshot(page, f"repos-list-{size}")
            assert not page.evaluate(
                "document.scrollingElement.scrollWidth > window.innerWidth"
            ), where
            lists = page.evaluate(_LIST)
            assert len(lists) == len(TIERS), where
            for got in lists:
                for row in got["rows"]:
                    assert row["nameContrast"] >= 4.5, f"{where}: {row}"
                    assert row["idContrast"] >= 4.5, f"{where}: {row}"
                    assert not row["nameAccent"], f"{where}: {row}"
                    assert not row["underlined"], f"{where}: {row}"
                    assert row["idBelow"] and not row["idPill"], f"{where}: {row}"
                    assert row["idMono"] and row["idSmaller"], f"{where}: {row}"
                    assert row["nameSmaller"], f"{where}: {row}"
                    assert row["divider"] >= 1, f"{where}: {row}"
                lines = _rows_by_top(got["rows"])
                columns = 2 if size == "desktop" else 1
                assert all(len(line) <= columns for line in lines), where
                assert max(len(line) for line in lines) == columns, where
                lefts = {round(row["left"]) for row in got["rows"]}
                assert len(lefts) == columns, f"{where}: {lefts}"
                if columns == 2:
                    heights = {round(row["height"], 1) for row in got["rows"]}
                    assert len(heights) == 1, f"{where}: uneven rows {heights}"
            assert_clean(page)
        finally:
            context.close()


def test_headings_and_counts(page, site_url) -> None:
    page.goto(site_url + "/repos/")
    for tier in TIERS:
        group = page.locator(f'.repos-group[data-tier="{tier["key"]}"]')
        n = group.locator(".repos-list li").count()
        heading = group.get_by_role("heading", level=3)
        assert heading.inner_text() == f"{tier['heading']} ({n})"
        assert re.match(r"[A-Z]", heading.inner_text())
        assert group.get_attribute("aria-labelledby") == heading.get_attribute("id")


_ACCENT = """() => {
    const probe = document.createElement("span");
    probe.style.color = getComputedStyle(document.documentElement).getPropertyValue("--accent");
    document.body.append(probe);
    const accent = getComputedStyle(probe).color;
    probe.remove();
    return accent;
}"""

_STATE = """e => {
    const s = getComputedStyle(e);
    return {
        outline: s.outlineStyle,
        width: parseFloat(s.outlineWidth),
        underlined: s.textDecorationLine.includes("underline"),
    };
}"""


def test_name_hover_and_keyboard_focus(browser, site_url) -> None:
    context = browser.new_context(viewport=SIZES["desktop"])
    try:
        page = context.new_page()
        page.goto(site_url + "/repos/")
        accent = page.evaluate(_ACCENT)
        first = page.locator(".repos-list a").first
        page.locator('a.arrow-link[href="/coding/install/"]').focus()
        page.keyboard.press("Tab")
        assert first.evaluate("e => e === document.activeElement")
        focused = first.evaluate(_STATE)
        assert focused["outline"] != "none" and focused["width"] >= 2, focused
        assert focused["underlined"], focused
        expect(first).to_have_css("color", accent)
        second = page.locator(".repos-list a").nth(1)
        second.hover()
        expect(second).to_have_css("color", accent)
        expect(second).to_have_css("text-decoration-line", "underline")
        screenshot(page, "repos-list-focus")
    finally:
        context.close()
