"""IR-F68: the built site serves /favicon.ico, a valid PNG-in-ICO rendered from static/favicon.svg."""

import re
import struct
import zlib
from pathlib import Path

import pytest

from sitegen import favicon

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "static" / "favicon.svg"


def _images(ico: bytes) -> list[tuple[int, int, bytes]]:
    """The (width, height, PNG bytes) entries of an ICO, checking the header bytes."""
    reserved, kind, count = struct.unpack_from("<HHH", ico, 0)
    assert (reserved, kind) == (0, 1), "not an ICO header (00 00 01 00)"
    assert ico[:4] == b"\x00\x00\x01\x00"
    out = []
    for i in range(count):
        w, h, colours, res, planes, bits, size, offset = struct.unpack_from(
            "<BBBBHHII", ico, 6 + 16 * i
        )
        assert (colours, res, planes, bits) == (0, 0, 1, 32)
        assert offset + size <= len(ico)
        out.append((w or 256, h or 256, ico[offset : offset + size]))
    return out


def _rgba(png: bytes) -> tuple[int, int, bytes]:
    """Width, height and RGBA rows of an 8-bit RGBA, filter-0 PNG (what sitegen writes)."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, ihdr = 8, b"", b""
    while pos < len(png):
        (length,) = struct.unpack_from(">I", png, pos)
        kind, body = png[pos + 4 : pos + 8], png[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack_from(">I", png, pos + 8 + length)
        assert crc == zlib.crc32(kind + body), kind
        if kind == b"IHDR":
            ihdr = body
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    w, h, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", ihdr)
    assert (depth, colour, interlace) == (8, 6, 0)
    raw = zlib.decompress(idat)
    stride = w * 4 + 1
    assert all(raw[r * stride] == 0 for r in range(h))
    return w, h, b"".join(raw[r * stride + 1 : (r + 1) * stride] for r in range(h))


def _pixel(rows: bytes, w: int, x: int, y: int) -> tuple[int, int, int, int]:
    """One RGBA pixel."""
    i = (y * w + x) * 4
    return tuple(rows[i : i + 4])


def _hex(c: str) -> tuple[int, int, int]:
    """#RRGGBB as an (r, g, b) tuple."""
    return tuple(int(c[i : i + 2], 16) for i in (1, 3, 5))


def test_built_site_has_a_valid_favicon_ico(built) -> None:
    ico = (built.out / "favicon.ico").read_bytes()
    images = _images(ico)
    assert [(w, h) for w, h, _ in images] == [(s, s) for s in favicon.SIZES]
    assert set(favicon.SIZES) >= {16, 32, 48}
    for w, h, png in images:
        assert _rgba(png)[:2] == (w, h)


def test_built_favicon_ico_is_rendered_from_the_svg_source(built) -> None:
    """The built bytes are exactly the render of static/favicon.svg, so the SVG is the one source."""
    ico = (built.out / "favicon.ico").read_bytes()
    assert ico == favicon.render_ico(SVG.read_text(encoding="utf-8"))
    assert not (ROOT / "static" / "favicon.ico").exists(), (
        "no hand-made copy in static/"
    )


def test_favicon_pixels_follow_the_svg_colours() -> None:
    svg = SVG.read_text(encoding="utf-8")
    background = re.search(r'<rect [^>]*fill="(#[0-9A-Fa-f]{6})"', svg).group(1)
    stops = re.findall(r'stop-color="(#[0-9A-Fa-f]{6})"', svg)
    images = _images(favicon.render_ico(svg))
    w, _, rows = _rgba(images[-1][2])
    # Round corner (rx=6 of 32): transparent.
    assert _pixel(rows, w, 0, 0)[3] == 0
    # Middle of the left edge: the rect's fill, opaque.
    assert _pixel(rows, w, 2, w // 2) == (*_hex(background), 255)
    # Inside the wedge near its bottom-left tip and its top-right tip: close to the
    # first and last gradient stops (x1,y1 = 0,1 to x2,y2 = 1,0).
    near_first = _pixel(rows, w, round(w * 9 / 32), round(w * 25 / 32))
    near_last = _pixel(rows, w, round(w * 25 / 32), round(w * 9 / 32))
    for got, want in ((near_first, stops[0]), (near_last, stops[-1])):
        assert got[3] == 255
        assert max(abs(a - b) for a, b in zip(got[:3], _hex(want), strict=True)) <= 12


def test_favicon_changes_when_the_svg_changes() -> None:
    svg = SVG.read_text(encoding="utf-8")
    changed = svg.replace('fill="#0B1B33"', 'fill="#000000"')
    assert changed != svg
    w, _, rows = _rgba(_images(favicon.render_ico(changed))[-1][2])
    assert _pixel(rows, w, 2, w // 2) == (0, 0, 0, 255)


@pytest.mark.parametrize(
    "svg",
    [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle r="4" fill="#000000"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#000000" transform="scale(2)"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="red"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 16"><rect width="32" height="16" fill="#000000"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><polygon points="1,1 2,2 3,3" fill="url(#nope)"/></svg>',
    ],
    ids=["circle", "transform", "named-colour", "not-square", "missing-gradient"],
)
def test_favicon_refuses_svg_it_cannot_draw(svg: str) -> None:
    """A favicon.svg change the renderer would draw wrongly fails the build instead."""
    with pytest.raises(favicon.FaviconError):
        favicon.render_ico(svg)


def test_pages_link_the_ico_beside_the_svg(built) -> None:
    html = (built.out / "index.html").read_text(encoding="utf-8")
    assert '<link rel="icon" href="/favicon.ico" sizes="any">' in html
    assert '<link rel="icon" href="/favicon.svg" type="image/svg+xml">' in html
