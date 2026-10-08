"""UT-1 1b: card grids align. Small grids share one height on desktop; long lists and phones align per row."""

import pytest
from conftest import assert_clean, collect, walk_paths

PHONE = 760
VIEWPORTS = (
    {"width": 1280, "height": 900},
    {"width": 1900, "height": 1000},
    {"width": 390, "height": 844},
)
# Marked grids the walk must find somewhere.
EXPECTED = {"cards", "rows", "kind-options", "fact-tiles", "steps", "stats"}

# Every .card-grid (one height) and .card-rows (per row), plus any unmarked grid that lays out two or more columns of
# visible children sharing one class list and drawing a border or background.
_CARD_GRIDS = """() => {
    const visible = e => e.getClientRects().length > 0;
    const drawn = e => {
        const cs = getComputedStyle(e);
        return parseFloat(cs.borderTopWidth) > 0 || cs.backgroundColor !== "rgba(0, 0, 0, 0)";
    };
    const grids = [];
    for (const grid of document.querySelectorAll("*")) {
        if (getComputedStyle(grid).display !== "grid") continue;
        const kids = [...grid.children].filter(visible);
        if (kids.length < 2) continue;
        const kind = kids[0].tagName + "." + kids[0].className;
        const whole = grid.classList.contains("card-grid");
        const marked = whole || grid.classList.contains("card-rows");
        const columns = new Set(kids.map(k => Math.round(k.getBoundingClientRect().left))).size;
        const cards = kids.every(k => k.tagName + "." + k.className === kind && drawn(k));
        if (!marked && !(cards && columns > 1)) continue;
        grids.push({
            grid: [...grid.classList],
            marked,
            whole,
            kind,
            boxes: kids.map(k => {
                const r = k.getBoundingClientRect();
                return {top: r.top, height: r.height};
            }),
        });
    }
    return grids;
}"""


@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: f"{v['width']}px")
def test_every_card_grid_has_one_height(browser, site_url, viewport) -> None:
    context = browser.new_context(viewport=viewport)
    found: set[str] = set()
    problems: list[str] = []
    try:
        page = context.new_page()
        collect(page, site_url)
        for path in walk_paths(page, site_url):
            page.goto(site_url + path)
            page.wait_for_load_state("networkidle")
            for grid in page.evaluate(_CARD_GRIDS):
                found.update(grid["grid"])
                where = f"{path} .{'.'.join(grid['grid'])} > {grid['kind']}"
                if not grid["marked"]:
                    problems.append(f"{where}: card grid without .card-grid")
                    continue
                rows: dict[int, list[dict]] = {}
                for box in grid["boxes"]:
                    rows.setdefault(round(box["top"] / 8), []).append(box)
                groups = list(rows.values())
                if grid["whole"] and viewport["width"] > PHONE:
                    groups = [grid["boxes"]]
                for group in groups:
                    heights = [box["height"] for box in group]
                    if max(heights) - min(heights) > 1:
                        problems.append(f"{where}: heights {sorted(set(heights))}")
                for row in rows.values():
                    tops = [box["top"] for box in row]
                    if max(tops) - min(tops) > 1:
                        problems.append(f"{where}: row tops differ")
        assert_clean(page)
    finally:
        context.close()
    assert EXPECTED <= found, f"card grids not found: {EXPECTED - found}"
    assert not problems, "\n".join(problems)
