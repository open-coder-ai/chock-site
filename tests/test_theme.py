"""Theme checks: WCAG AA contrast of the one palette, self-hosted fonts, no third-party loads."""

import re
from pathlib import Path

TOKEN_RE = re.compile(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;")
FONT_URL_RE = re.compile(r'url\("(/fonts/[^"]+)"\)\s*format\("woff2"\)')

# Text on its background: WCAG AA for body text (4.5:1). Every foreground token is checked
# on every surface it sits on in site.css.
CONTRAST_PAIRS = [
    ("text", "bg"),
    ("text", "bg-2"),
    ("text", "panel"),
    ("text", "panel-2"),
    ("text", "pill"),
    ("body", "bg"),
    ("body", "bg-2"),
    ("body", "panel"),
    ("body", "panel-2"),
    ("body", "pill"),
    ("muted", "bg"),
    ("muted", "bg-2"),
    ("muted", "panel"),
    ("muted", "panel-2"),
    ("muted", "pill"),
    ("accent", "bg"),
    ("accent", "bg-2"),
    ("accent", "panel"),
    ("accent", "panel-2"),
    ("accent", "pill"),
    ("on-accent", "accent"),
    ("on-accent", "accent-2"),
    ("on-primary", "primary"),
    ("on-highlight", "highlight"),
    ("highlight-text", "bg"),
    ("highlight-text", "bg-2"),
    ("highlight-text", "panel"),
    ("highlight-text-2", "bg"),
    ("on-accent", "highlight-text"),
    ("warn-fg", "warn-bg"),
    ("warn-fg", "warns-bg"),
    ("warn-text", "bg"),
    ("warn-text", "panel"),
    ("ok", "bg"),
    ("ok", "panel"),
    ("info", "bg"),
    ("info", "panel"),
]

# Non-text UI on its background (input borders, dashed outlines, glyphs): 3:1.
UI_PAIRS = [
    ("line-2", "bg"),
    ("line-2", "panel"),
    ("dash", "bg"),
    ("dash", "bg-2"),
    ("dash", "panel"),
    ("accent", "bg"),
]


def _block(css: str, selector: str) -> str:
    """The body of the first rule that opens with `selector {`."""
    start = css.index(selector + " {") + len(selector) + 2
    return css[start : css.index("}", start)]


def _palette(built) -> dict[str, str]:
    """The one palette, declared on :root."""
    css = (built.out / "css" / "site.css").read_text(encoding="utf-8")
    return {n: v.upper() for n, v in TOKEN_RE.findall(_block(css, ":root"))}


def _luminance(hexcolor: str) -> float:
    channels = [int(hexcolor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(foreground: str, background: str) -> float:
    high = max(_luminance(foreground), _luminance(background))
    low = min(_luminance(foreground), _luminance(background))
    return (high + 0.05) / (low + 0.05)


def test_one_palette_on_root_and_no_theme_switch(built) -> None:
    """site.css has dark on :root, no data-theme selector, no prefers-color-scheme rule."""
    css = (built.out / "css" / "site.css").read_text(encoding="utf-8")
    assert "color-scheme: dark;" in _block(css, ":root")
    assert "data-theme" not in css
    assert "prefers-color-scheme" not in css
    assert "theme-toggle" not in css


def test_no_page_has_a_theme_script_or_toggle(built) -> None:
    """No built page loads /js/theme.js or carries a theme toggle, and the file is gone."""
    assert not (built.out / "js" / "theme.js").exists()
    for page in built.out.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert "/js/theme.js" not in text, page
        assert "theme-toggle" not in text, page


def test_tokens_meet_contrast(built) -> None:
    """Every text pair passes 4.5:1 and every UI pair passes 3:1."""
    tokens = _palette(built)
    for pairs, minimum in ((CONTRAST_PAIRS, 4.5), (UI_PAIRS, 3.0)):
        for foreground, background in pairs:
            assert foreground in tokens, f"--{foreground} missing"
            assert background in tokens, f"--{background} missing"
            ratio = _ratio(tokens[foreground], tokens[background])
            assert ratio >= minimum, f"{foreground} on {background}: {ratio:.2f}:1"


def test_font_faces_resolve_to_self_hosted_woff2(built) -> None:
    css = (built.out / "css" / "site.css").read_text(encoding="utf-8")
    urls = FONT_URL_RE.findall(css)
    families = re.findall(r'font-family:\s*"([^"]+)"', css)
    assert set(families[:6]) == {"Schibsted Grotesk", "JetBrains Mono"}
    assert len(urls) == 6
    for url in urls:
        path = built.out / url.lstrip("/")
        assert path.is_file(), url
        assert path.read_bytes()[:4] == b"wOF2", url
    licenses = {p.name for p in Path(built.out / "fonts").glob("OFL-*.txt")}
    assert licenses == {"OFL-SchibstedGrotesk.txt", "OFL-JetBrainsMono.txt"}


def test_no_page_loads_a_stylesheet_script_or_font_from_elsewhere(built) -> None:
    """No built file names a font CDN or loads an https:// stylesheet, script or font."""
    loads = re.compile(
        r"""<script\b[^>]*src=["']https?://"""
        r"""|<link\b[^>]*rel=["'](?:stylesheet|preload|modulepreload)["'][^>]*href=["']https?://""",
        re.IGNORECASE,
    )
    css_url = re.compile(
        r"""url\(\s*["']?https?://|@import\s+(?:url\()?["']?https?://""", re.IGNORECASE
    )
    for path in built.out.rglob("*"):
        if not path.is_file() or path.suffix not in {".html", ".css", ".js"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "fonts.googleapis.com" not in text, path
        assert "fonts.gstatic.com" not in text, path
        if path.suffix == ".html":
            assert not loads.search(text), path
        if path.suffix == ".css":
            assert not css_url.search(text), path


def test_note_boxes_keep_text_readable_on_the_amber_tint(built) -> None:
    """Warning boxes tint the amber over the panel; every text colour they use stays at 4.5:1."""
    css = (built.out / "css" / "site.css").read_text(encoding="utf-8")
    rule = re.search(
        r"\.report-security,[^{]*\{[^}]*color-mix\(in srgb, var\(--warn-bg\) (\d+)%, var\(--panel\)\)",
        css,
    )
    assert rule, "the note-box tint rule is missing"
    share = int(rule.group(1)) / 100
    tokens = _palette(built)

    def channel(color: str, i: int) -> int:
        return int(color[1 + 2 * i : 3 + 2 * i], 16)

    tint = "#" + "".join(
        f"{round(channel(tokens['warn-bg'], i) * share + channel(tokens['panel'], i) * (1 - share)):02X}"
        for i in range(3)
    )
    for name in ("text", "body", "warn-text", "highlight-text"):
        ratio = _ratio(tokens[name], tint)
        assert ratio >= 4.5, f"{name} on the tint {tint}: {ratio:.2f}:1"
