"""favicon.ico (PNG-in-ICO) rendered at build time from static/favicon.svg, standard library only."""

import re
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

SVG_NS = "{http://www.w3.org/2000/svg}"
# Sizes browsers and crawlers ask for; one PNG image each.
SIZES = (16, 32, 48)
# Samples per pixel along each axis (anti-aliasing); 8 gives 64 samples per pixel.
SUPERSAMPLE = 8
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
_NUM = r"-?\d+(?:\.\d+)?"


class FaviconError(ValueError):
    """The SVG uses something this renderer does not draw, so no icon is written."""


def _num(text: str | None, what: str) -> float:
    """A plain decimal number attribute, or FaviconError."""
    if text is None or not re.fullmatch(_NUM, text.strip()):
        raise FaviconError(f"{what}: expected a plain number, got {text!r}")
    return float(text)


def _colour(text: str | None, what: str) -> tuple[float, float, float]:
    """A #RRGGBB colour as three floats in 0..1, or FaviconError."""
    if text is None or not _HEX.fullmatch(text):
        raise FaviconError(f"{what}: expected #RRGGBB, got {text!r}")
    return tuple(int(text[i : i + 2], 16) / 255 for i in (1, 3, 5))


def _allow(el: ET.Element, attrs: set[str]) -> None:
    """Refuse any attribute this renderer would silently ignore."""
    extra = set(el.attrib) - attrs
    if extra:
        raise FaviconError(
            f"<{el.tag.removeprefix(SVG_NS)}>: unsupported {sorted(extra)}"
        )


class _Gradient:
    """A two-or-more-stop linearGradient in objectBoundingBox units, pad spread."""

    def __init__(self, el: ET.Element) -> None:
        _allow(el, {"id", "x1", "y1", "x2", "y2"})
        self.x1, self.y1, self.x2, self.y2 = (
            _num(el.get(k, d), f"gradient {k}")
            for k, d in (("x1", "0"), ("y1", "0"), ("x2", "1"), ("y2", "0"))
        )
        self.stops = []
        for stop in el:
            if stop.tag != SVG_NS + "stop":
                raise FaviconError(f"gradient: unsupported child {stop.tag}")
            _allow(stop, {"offset", "stop-color"})
            self.stops.append(
                (
                    _num(stop.get("offset"), "stop offset"),
                    _colour(stop.get("stop-color"), "stop"),
                )
            )
        if len(self.stops) < 2:
            raise FaviconError("gradient: needs at least two stops")

    def at(self, u: float, v: float) -> tuple[float, float, float]:
        """The colour at bounding-box coordinates (u, v)."""
        dx, dy = self.x2 - self.x1, self.y2 - self.y1
        t = ((u - self.x1) * dx + (v - self.y1) * dy) / (dx * dx + dy * dy)
        t = min(max(t, self.stops[0][0]), self.stops[-1][0])
        for (o0, c0), (o1, c1) in zip(self.stops, self.stops[1:], strict=False):
            if t <= o1:
                f = 0.0 if o1 == o0 else (t - o0) / (o1 - o0)
                return tuple(a + (b - a) * f for a, b in zip(c0, c1, strict=True))
        return self.stops[-1][1]


class _Shape:
    """One filled shape: an inside test, a bounding box and a solid or gradient fill."""

    def __init__(self, inside, bbox, fill, gradients: dict[str, _Gradient]) -> None:
        self.inside = inside
        self.x0, self.y0, self.x1, self.y1 = bbox
        ref = re.fullmatch(r"url\(#([\w-]+)\)", fill or "")
        if ref:
            if ref.group(1) not in gradients:
                raise FaviconError(f"fill {fill}: no such gradient")
            self.gradient, self.colour = gradients[ref.group(1)], None
        else:
            self.gradient, self.colour = None, _colour(fill, "fill")

    def paint(self, x: float, y: float) -> tuple[float, float, float]:
        """The fill colour at viewBox point (x, y)."""
        if self.gradient is None:
            return self.colour
        u = (x - self.x0) / (self.x1 - self.x0)
        v = (y - self.y0) / (self.y1 - self.y0)
        return self.gradient.at(u, v)


def _rect(el: ET.Element, gradients: dict[str, _Gradient]) -> _Shape:
    """A <rect>, optionally with round corners (rx, ry defaults to rx)."""
    _allow(el, {"x", "y", "width", "height", "rx", "ry", "fill"})
    x, y = _num(el.get("x", "0"), "rect x"), _num(el.get("y", "0"), "rect y")
    w, h = _num(el.get("width"), "rect width"), _num(el.get("height"), "rect height")
    rx = _num(el.get("rx", el.get("ry", "0")), "rect rx")
    ry = _num(el.get("ry", el.get("rx", "0")), "rect ry")
    rx, ry = min(rx, w / 2), min(ry, h / 2)

    def inside(px: float, py: float) -> bool:
        """Whether (px, py) is in the rect, round corners included."""
        if not (x <= px <= x + w and y <= py <= y + h):
            return False
        cx = min(max(px, x + rx), x + w - rx)
        cy = min(max(py, y + ry), y + h - ry)
        if rx == 0 or ry == 0 or (cx == px or cy == py):
            return True
        return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1

    return _Shape(inside, (x, y, x + w, y + h), el.get("fill"), gradients)


def _polygon(el: ET.Element, gradients: dict[str, _Gradient]) -> _Shape:
    """A <polygon>, filled with the nonzero rule (the SVG default)."""
    _allow(el, {"points", "fill"})
    nums = re.split(r"[\s,]+", (el.get("points") or "").strip())
    if len(nums) < 6 or len(nums) % 2:
        raise FaviconError(f"polygon points: {el.get('points')!r}")
    pts = [
        (_num(a, "point"), _num(b, "point"))
        for a, b in zip(nums[::2], nums[1::2], strict=True)
    ]
    edges = list(zip(pts, pts[1:] + pts[:1], strict=True))

    def inside(px: float, py: float) -> bool:
        """Whether (px, py) is in the polygon (nonzero winding)."""
        winding = 0
        for (ax, ay), (bx, by) in edges:
            cross = (bx - ax) * (py - ay) - (px - ax) * (by - ay)
            if ay <= py < by and cross > 0:
                winding += 1
            elif by <= py < ay and cross < 0:
                winding -= 1
        return winding != 0

    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return _Shape(
        inside, (min(xs), min(ys), max(xs), max(ys)), el.get("fill"), gradients
    )


def parse(svg_text: str) -> tuple[float, list[_Shape]]:
    """The square viewBox side and the shapes in paint order, or FaviconError."""
    root = ET.fromstring(svg_text)
    if root.tag != SVG_NS + "svg":
        raise FaviconError("root element is not <svg>")
    _allow(root, {"viewBox"})
    box = [_num(n, "viewBox") for n in (root.get("viewBox") or "").split()]
    if len(box) != 4 or box[:2] != [0, 0] or box[2] != box[3]:
        raise FaviconError(f"viewBox must be '0 0 N N', got {root.get('viewBox')!r}")
    gradients: dict[str, _Gradient] = {}
    shapes: list[_Shape] = []
    for el in root:
        tag = el.tag.removeprefix(SVG_NS)
        if tag == "defs":
            _allow(el, set())
            for g in el:
                if g.tag != SVG_NS + "linearGradient":
                    raise FaviconError(f"<defs>: unsupported {g.tag}")
                gradients[g.get("id")] = _Gradient(g)
        elif tag == "rect":
            shapes.append(_rect(el, gradients))
        elif tag == "polygon":
            shapes.append(_polygon(el, gradients))
        else:
            raise FaviconError(f"unsupported element <{tag}>")
    if not shapes:
        raise FaviconError("no shapes to draw")
    return box[2], shapes


def rasterize(svg_text: str, size: int) -> bytes:
    """Straight-alpha RGBA rows (size x size x 4 bytes), anti-aliased by supersampling."""
    side, shapes = parse(svg_text)
    n = SUPERSAMPLE
    out = bytearray()
    for row in range(size):
        for col in range(size):
            r = g = b = a = 0.0
            for sy in range(n):
                y = (row + (sy + 0.5) / n) * side / size
                for sx in range(n):
                    x = (col + (sx + 0.5) / n) * side / size
                    for shape in reversed(shapes):
                        if shape.inside(x, y):
                            cr, cg, cb = shape.paint(x, y)
                            r, g, b, a = r + cr, g + cg, b + cb, a + 1
                            break
            if a:
                out += bytes(round(c / a * 255) for c in (r, g, b))
            else:
                out += b"\0\0\0"
            out.append(round(a / (n * n) * 255))
    return bytes(out)


def _png(rgba: bytes, size: int) -> bytes:
    """An 8-bit RGBA PNG of the rows, filter 0, no ancillary chunks."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        """One PNG chunk: length, type, body, CRC."""
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body))
        )

    stride = size * 4
    raw = b"".join(b"\0" + rgba[i : i + stride] for i in range(0, len(rgba), stride))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def render_ico(svg_text: str, sizes: tuple[int, ...] = SIZES) -> bytes:
    """An ICO file holding one PNG image per size, rendered from the SVG text."""
    images = [_png(rasterize(svg_text, s), s) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = len(head) + 16 * len(images)
    entries = b""
    for size, png in zip(sizes, images, strict=True):
        entries += struct.pack(
            "<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset
        )
        offset += len(png)
    return head + entries + b"".join(images)


def write(svg: Path, out: Path) -> None:
    """Write out/favicon.ico from the favicon SVG."""
    (out / "favicon.ico").write_bytes(render_ico(svg.read_text(encoding="utf-8")))
