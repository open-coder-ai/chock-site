"""IR-F68: /favicon.ico is served, and each of its images matches Chromium's own render of /favicon.svg."""

import base64
import struct

import pytest

COMPARE = """async ([svgUrl, pngUrl, size]) => {
  const load = (src) => new Promise((ok, fail) => {
    const img = new Image(); img.onload = () => ok(img); img.onerror = fail; img.src = src;
  });
  const pixels = async (src) => {
    const canvas = document.createElement("canvas");
    canvas.width = size; canvas.height = size;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(await load(src), 0, 0, size, size);
    return ctx.getImageData(0, 0, size, size).data;
  };
  const a = await pixels(svgUrl), b = await pixels(pngUrl);
  let sum = 0, max = 0;
  // Colour is compared premultiplied by alpha: the colour of a nearly transparent
  // edge pixel is noise, and what is seen is colour times coverage.
  for (let i = 0; i < a.length; i++) {
    const k = i % 4 === 3 ? 255 : null;
    const pa = k ? a[i] : a[i] * a[i - i % 4 + 3] / 255;
    const pb = k ? b[i] : b[i] * b[i - i % 4 + 3] / 255;
    const d = Math.abs(pa - pb); sum += d; if (d > max) max = d;
  }
  return {mean: sum / a.length, max: max};
}"""


def _png_of_size(ico: bytes, size: int) -> bytes:
    """The PNG image of one size inside an ICO."""
    (count,) = struct.unpack_from("<H", ico, 4)
    for i in range(count):
        w, _, _, _, _, _, length, offset = struct.unpack_from(
            "<BBBBHHII", ico, 6 + 16 * i
        )
        if w == size:
            return ico[offset : offset + length]
    raise AssertionError(f"no {size}px image")


@pytest.mark.parametrize("size", [16, 32, 48])
def test_favicon_ico_is_served_and_matches_the_svg(page, site_url, size) -> None:
    response = page.goto(site_url + "/favicon.ico")
    assert response.status == 200
    ico = response.body()
    assert ico[:4] == b"\x00\x00\x01\x00"
    png = "data:image/png;base64," + base64.b64encode(_png_of_size(ico, size)).decode()
    page.goto(site_url + "/")
    diff = page.evaluate(COMPARE, [site_url + "/favicon.svg", png, size])
    # Measured 2026-11-09 (Playwright 1.63 Chromium): mean 0.64 / 0.42 / 0.37 and max
    # 24 / 37 / 79 for 16 / 32 / 48px. The max is alpha on a round-corner pixel, where
    # Chromium approximates coverage (120 of 255) and sitegen's 8x8 supersampling
    # gives 199, against 199.7 from exact integration. A wrong shape or colour moves
    # the mean well past 1.5; a fully wrong pixel differs by 255.
    assert diff["mean"] < 1.5, diff
    assert diff["max"] < 128, diff
