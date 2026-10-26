"""ARCH-1: architecture diagrams: a box shows its card, the path toggle, both site themes, no JS."""

import json
from pathlib import Path

import pytest
from conftest import assert_clean, collect, screenshot

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "data" / "architecture"
DESKTOP = {"width": 1366, "height": 900}
MOBILE = {"width": 390, "height": 844}
IDS = [
    "whole-train",
    "life-of-a-policy",
    "lifecycle",
    "enforcement-surfaces",
    "stop-and-resume",
]


def _diagram(diagram_id: str) -> dict:
    return json.loads((ARCH / f"{diagram_id}.json").read_text(encoding="utf-8"))


def _url(site_url: str, diagram_id: str) -> str:
    return f"{site_url}/docs/architecture/{diagram_id}/"


@pytest.mark.parametrize("diagram_id", IDS)
def test_selecting_a_box_shows_its_card(page, site_url, diagram_id: str) -> None:
    diagram = _diagram(diagram_id)
    page.set_viewport_size(DESKTOP)
    page.goto(_url(site_url, diagram_id))
    panel = page.locator(".arch-panel")
    assert panel.is_hidden()
    for node in (diagram["nodes"][0], diagram["nodes"][-1]):
        page.locator(f'.arch-node[data-node="{node["id"]}"]').click()
        assert panel.is_visible()
        assert panel.locator(".arch-card-label").inner_text() == node["label"]
        assert node["card"][:40] in panel.locator(".arch-card-text").inner_text()
        assert panel.locator(".arch-card-source a").inner_text() == node["source"]
        selected = page.locator(".arch-node.is-selected")
        assert selected.count() == 1
        assert selected.get_attribute("data-node") == node["id"]
    assert page.url.endswith(f"/docs/architecture/{diagram_id}/")
    page.keyboard.press("Escape")
    assert panel.is_hidden()
    assert page.locator(".arch-node.is-selected").count() == 0
    screenshot(page, f"arch-{diagram_id}")
    assert_clean(page)


def test_a_box_opens_from_the_keyboard(page, site_url) -> None:
    page.set_viewport_size(DESKTOP)
    page.goto(_url(site_url, "life-of-a-policy"))
    node = page.locator('.arch-node[data-node="verdict"]')
    node.focus()
    page.keyboard.press("Enter")
    assert page.locator(".arch-panel .arch-card-label").inner_text() == "Verdict"
    page.locator(".arch-close").click()
    assert page.locator(".arch-panel").is_hidden()
    assert page.evaluate("document.activeElement.dataset.node") == "verdict"
    assert_clean(page)


@pytest.mark.parametrize("diagram_id", IDS)
def test_path_toggle_highlights_only_the_main_path(
    page, site_url, diagram_id: str
) -> None:
    diagram = _diagram(diagram_id)
    page.set_viewport_size(DESKTOP)
    page.goto(_url(site_url, diagram_id))
    button = page.locator(".arch-path-toggle")
    figure = page.locator(".arch-figure")
    assert button.get_attribute("aria-pressed") == "false"
    off_path = [n["id"] for n in diagram["nodes"] if n["id"] not in diagram["path"]]
    dimmed = f'.arch-node[data-node="{off_path[0]}"]'
    on = f'.arch-node[data-node="{diagram["path"][0]}"]'
    assert page.locator(dimmed).evaluate("e => getComputedStyle(e).opacity") == "1"

    button.click()
    assert button.get_attribute("aria-pressed") == "true"
    assert "show-path" in figure.get_attribute("class")
    assert page.locator(dimmed).evaluate("e => getComputedStyle(e).opacity") == "0.35"
    assert page.locator(on).evaluate("e => getComputedStyle(e).opacity") == "1"
    width = page.locator(".arch-edge.arch-on-path path").first.evaluate(
        "e => getComputedStyle(e).strokeWidth"
    )
    assert width == "3px"

    button.click()
    assert button.get_attribute("aria-pressed") == "false"
    assert page.locator(dimmed).evaluate("e => getComputedStyle(e).opacity") == "1"
    assert_clean(page)


# Text in a figure and the colour it sits on, read from the computed styles: the selector of
# the text, the property holding its colour, and the selector whose colour is its background.
TEXT_ON_SURFACE = [
    (".arch-node-label", "fill", ".arch-node rect", "fill"),
    (".arch-node-repo", "fill", ".arch-node rect", "fill"),
    (".arch-boundary-label", "fill", ".arch-figure", "backgroundColor"),
    (".arch-edge-label", "fill", ".arch-figure", "backgroundColor"),
    (".arch-legend", "color", ".arch-figure", "backgroundColor"),
    (".arch-hint-js", "color", ".arch-figure", "backgroundColor"),
    (".arch-path-toggle", "color", ".arch-path-toggle", "backgroundColor"),
    (
        "ol.arch-cards .arch-card-text",
        "color",
        "ol.arch-cards .arch-card",
        "backgroundColor",
    ),
    (
        "ol.arch-cards .arch-card-kind",
        "color",
        "ol.arch-cards .arch-card",
        "backgroundColor",
    ),
]
CONTRAST_JS = """([fg, fgProp, bg, bgProp]) => {
  const rgb = (s) => s.match(/\\d+/g).slice(0, 3).map(Number);
  const lum = (c) => {
    const l = c.map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2];
  };
  const a = lum(rgb(getComputedStyle(document.querySelector(fg))[fgProp]));
  const b = lum(rgb(getComputedStyle(document.querySelector(bg))[bgProp]));
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}"""


def test_figures_follow_the_site_theme_with_aa_text(page, site_url) -> None:
    """No per-figure theme button: each figure takes the site theme and its text passes AA."""
    page_bg = "rgb(16, 37, 74)"
    page.set_viewport_size(DESKTOP)
    for diagram_id in IDS:
        page.goto(_url(site_url, diagram_id))
        figure = page.locator(".arch-figure")
        assert figure.get_attribute("data-theme") is None
        assert page.locator(".arch-theme-toggle").count() == 0
        assert page.locator(".arch-toolbar button").count() == 1
        assert figure.evaluate("e => getComputedStyle(e).backgroundColor") == page_bg
        for pair in TEXT_ON_SURFACE:
            ratio = page.evaluate(CONTRAST_JS, list(pair))
            assert ratio >= 4.5, f"{diagram_id}: {pair[0]}: {ratio:.2f}:1"
    assert_clean(page)


@pytest.mark.parametrize("diagram_id", IDS)
def test_without_js_the_svg_and_cards_render(
    browser, site_url, diagram_id: str
) -> None:
    diagram = _diagram(diagram_id)
    context = browser.new_context(java_script_enabled=False, viewport=MOBILE)
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(_url(site_url, diagram_id))
        assert page.locator(".arch-svg").is_visible()
        assert page.locator(".arch-node").count() == len(diagram["nodes"])
        assert page.locator(".arch-toolbar").is_hidden()
        assert page.locator(".arch-panel").is_hidden()
        assert page.locator(".arch-hint-nojs").is_visible()
        cards = page.locator("ol.arch-cards > li.arch-card")
        assert cards.count() == len(diagram["nodes"])
        node = diagram["nodes"][1]
        page.locator(f'.arch-node[data-node="{node["id"]}"]').click()
        assert page.url.endswith(f"#arch-{diagram_id}-{node['id']}")
        card = page.locator(f"#arch-{diagram_id}-{node['id']}")
        assert card.is_visible()
        assert card.evaluate("e => e.matches(':target')")
        # The figure scrolls inside its own region; it never widens the docs column.
        for box in (".arch-figure", "ol.arch-cards"):
            right = page.locator(box).evaluate("e => e.getBoundingClientRect().right")
            assert right <= MOBILE["width"], f"{box} overflows: {right}px"
        region = page.locator(".arch-scroll")
        assert region.evaluate("e => e.scrollWidth > e.clientWidth")
        screenshot(page, f"arch-{diagram_id}-nojs")
        assert_clean(page)
    finally:
        context.close()
