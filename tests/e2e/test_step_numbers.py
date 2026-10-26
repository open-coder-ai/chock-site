"""The how-it-works numerals: each digit sits in the centre of its chamfered square, 1280 and 390 px."""

import base64

import pytest

CIRCLES = ".how-steps .step-num"
SIZES = {
    "desktop": {"width": 1280, "height": 900},
    "phone": {"width": 390, "height": 844},
}
# Added through the CSSOM, which the CSP allows: hide the digit, then paint the circle solid.
NO_DIGIT = f"{CIRCLES} {{ color: transparent !important; }}"
SOLID = (
    f"{CIRCLES} {{ color: transparent !important; background: #ff00ff !important; }}"
)
SIZE_JS = "(el) => { const s = getComputedStyle(el); return [s.width, s.height]; }"
# In the page: the box of pixels that differ between two screenshots, per region.
BOXES_JS = """async ([a, b, regions]) => {
  const load = (src) => new Promise((ok) => { const i = new Image(); i.onload = () => ok(i); i.src = src; });
  const pixels = async (src) => {
    const img = await load("data:image/png;base64," + src);
    const c = document.createElement("canvas");
    c.width = img.width; c.height = img.height;
    const ctx = c.getContext("2d");
    ctx.drawImage(img, 0, 0);
    return ctx.getImageData(0, 0, c.width, c.height);
  };
  const pa = await pixels(a), pb = await pixels(b);
  return regions.map(([x0, y0, x1, y1]) => {
    let box = null;
    for (let y = y0; y < y1; y++) {
      for (let x = x0; x < x1; x++) {
        const i = (y * pa.width + x) * 4;
        const d = Math.abs(pa.data[i] - pb.data[i]) + Math.abs(pa.data[i + 1] - pb.data[i + 1])
          + Math.abs(pa.data[i + 2] - pb.data[i + 2]);
        if (d > 24) {
          box = box ? [Math.min(box[0], x), Math.min(box[1], y), Math.max(box[2], x + 1), Math.max(box[3], y + 1)]
            : [x, y, x + 1, y + 1];
        }
      }
    }
    return box;
  });
}"""


def _add_rule(page, rule: str) -> None:
    page.evaluate(
        "(rule) => { const s = new CSSStyleSheet(); s.replaceSync(rule);"
        " document.adoptedStyleSheets = [...document.adoptedStyleSheets, s]; }",
        rule,
    )


def _shot(page) -> str:
    return base64.b64encode(page.screenshot(animations="disabled")).decode()


def _centre(box: list[int]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


@pytest.mark.parametrize("size", sorted(SIZES))
def test_step_digit_is_centred_in_its_numeral(page, site_url, size) -> None:
    page.emulate_media(reduced_motion="reduce")
    page.set_viewport_size(SIZES[size])
    page.goto(site_url + "/")
    items = page.locator(CIRCLES)
    assert items.count() == 3
    checked = 0
    for n in range(items.count()):
        item = items.nth(n)
        item.scroll_into_view_if_needed()
        page.evaluate("document.adoptedStyleSheets = []")
        box = item.bounding_box()
        # The numeral is the item's whole box; look a little past it on every side.
        region = [
            max(0, int(box["x"]) - 4),
            max(0, int(box["y"]) - 4),
            int(box["x"] + box["width"]) + 4,
            int(box["y"] + box["height"]) + 4,
        ]
        plain = _shot(page)
        _add_rule(page, NO_DIGIT)
        no_digit = _shot(page)
        _add_rule(page, SOLID)
        solid = _shot(page)
        digit, circle = (
            page.evaluate(BOXES_JS, [plain, no_digit, [region]])[0],
            page.evaluate(BOXES_JS, [no_digit, solid, [region]])[0],
        )
        assert digit and circle, f"step {n + 1}: digit {digit}, circle {circle}"
        assert item.evaluate(SIZE_JS) == ["40px", "40px"], f"step {n + 1}: numeral size"
        (dx, dy), (cx, cy) = _centre(digit), _centre(circle)
        assert abs(dx - cx) <= 1 and abs(dy - cy) <= 1, (
            f"{size} step {n + 1}: digit centre ({dx}, {dy}), circle centre ({cx}, {cy})"
        )
        checked += 1
    assert checked == 3
