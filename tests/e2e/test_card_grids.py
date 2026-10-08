"""UT-1 1b: on every page, every card in a grid has one height and a row shares a top edge."""

import re

import pytest
from conftest import assert_clean, collect

VIEWPORTS = (
    {"width": 1280, "height": 900},
    {"width": 1900, "height": 1000},
    {"width": 390, "height": 844},
)
# Grids marked .card-grid; the walk must find each of them somewhere.
EXPECTED = {"cards", "rows", "kind-options", "fact-tiles", "steps", "stats"}

# Every .card-grid, plus any unmarked grid that lays out two or more columns of
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
        const marked = grid.classList.contains("card-grid");
        const columns = new Set(kids.map(k => Math.round(k.getBoundingClientRect().left))).size;
        const cards = kids.every(k => k.tagName + "." + k.className === kind && drawn(k));
        if (!marked && !(cards && columns > 1)) continue;
        grids.push({
            grid: [...grid.classList],
            marked,
            kind,
            boxes: kids.map(k => {
                const r = k.getBoundingClientRect();
                return {top: r.top, height: r.height};
            }),
        });
    }
    return grids;
}"""


def _paths(page, site_url: str) -> list[str]:
    """Every sitemap URL, the 404 page and the full builder with a preset."""
    xml = page.request.get(site_url + "/sitemap.xml").text()
    paths = [
        loc[len("https://chock.sh") :] for loc in re.findall(r"<loc>([^<]+)</loc>", xml)
    ]
    return paths + ["/404.html", "/coding/builder/#preset=git-hygiene"]


@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: f"{v['width']}px")
def test_every_card_grid_has_one_height(browser, site_url, viewport) -> None:
    context = browser.new_context(viewport=viewport)
    found: set[str] = set()
    problems: list[str] = []
    try:
        page = context.new_page()
        collect(page, site_url)
        for path in _paths(page, site_url):
            page.goto(site_url + path)
            page.wait_for_load_state("networkidle")
            for grid in page.evaluate(_CARD_GRIDS):
                found.update(grid["grid"])
                where = f"{path} .{'.'.join(grid['grid'])} > {grid['kind']}"
                if not grid["marked"]:
                    problems.append(f"{where}: card grid without .card-grid")
                    continue
                heights = [box["height"] for box in grid["boxes"]]
                if max(heights) - min(heights) > 1:
                    problems.append(f"{where}: heights {sorted(set(heights))}")
                rows: dict[int, list[float]] = {}
                for box in grid["boxes"]:
                    rows.setdefault(round(box["top"] / 8), []).append(box["top"])
                if any(max(tops) - min(tops) > 1 for tops in rows.values()):
                    problems.append(f"{where}: row tops differ")
        assert_clean(page)
    finally:
        context.close()
    assert EXPECTED <= found, f"card grids not found: {EXPECTED - found}"
    assert not problems, "\n".join(problems)
