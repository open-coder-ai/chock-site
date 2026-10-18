"""Theme checks: WCAG AA contrast of the light and dark tokens, and self-hosted fonts."""

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
    ("text", "warn-bg"),
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
    ("accent", "warn-bg"),
    ("on-accent", "accent"),
    ("on-primary", "primary"),
    ("on-highlight", "highlight"),
    ("highlight-text", "bg-2"),
    ("highlight-text", "panel"),
    ("on-accent", "highlight-text"),
    ("warn-fg", "warn-bg"),
    ("warn-fg", "bg"),
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


def _palettes(built) -> dict[str, dict[str, str]]:
    """The light tokens on :root and the dark set: :root overlaid by the dark rule."""
    css = (built.out / "css" / "site.css").read_text(encoding="utf-8")
    light = {n: v.upper() for n, v in TOKEN_RE.findall(_block(css, ":root"))}
    dark_rule = _block(css, ':root[data-theme="dark"]')
    dark = light | {n: v.upper() for n, v in TOKEN_RE.findall(dark_rule)}
    return {"light": light, "dark": dark}


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


def test_light_is_default_and_dark_rules_agree(built) -> None:
    """:root is light; the system-dark rule and the data-theme rule hold the same dark set."""
    css = (built.out / "css" / "site.css").read_text(encoding="utf-8")
    assert "color-scheme: light;" in _block(css, ":root")
    dark_rule = _block(css, ':root[data-theme="dark"]')
    system_rule = _block(css, ":root:not([data-theme])")
    assert "color-scheme: dark;" in dark_rule
    assert TOKEN_RE.findall(system_rule) == TOKEN_RE.findall(dark_rule)
    assert set(dict(TOKEN_RE.findall(dark_rule))) == set(_palettes(built)["light"])


def test_tokens_meet_contrast(built) -> None:
    """In both themes every text pair passes 4.5:1 and every UI pair passes 3:1."""
    for theme, tokens in _palettes(built).items():
        for pairs, minimum in ((CONTRAST_PAIRS, 4.5), (UI_PAIRS, 3.0)):
            for foreground, background in pairs:
                assert foreground in tokens, f"--{foreground} missing"
                assert background in tokens, f"--{background} missing"
                ratio = _ratio(tokens[foreground], tokens[background])
                assert ratio >= minimum, (
                    f"{theme}: {foreground} on {background}: {ratio:.2f}:1"
                )


def test_font_faces_resolve_to_self_hosted_woff2(built) -> None:
    css = (built.out / "css" / "site.css").read_text(encoding="utf-8")
    urls = FONT_URL_RE.findall(css)
    families = re.findall(r'font-family:\s*"([^"]+)"', css)
    assert set(families[:2]) <= {"Instrument Sans", "JetBrains Mono"}
    assert len(urls) == 7
    for url in urls:
        path = built.out / url.lstrip("/")
        assert path.is_file(), url
        assert path.read_bytes()[:4] == b"wOF2", url
    licenses = {p.name for p in Path(built.out / "fonts").glob("OFL-*.txt")}
    assert licenses == {"OFL-InstrumentSans.txt", "OFL-JetBrainsMono.txt"}


def test_theme_script_runs_before_the_stylesheet(built) -> None:
    """Every page loads theme.js as a classic script ahead of site.css, so nothing flashes."""
    tag = '<script src="/js/theme.js"></script>'
    for page in built.out.rglob("*.html"):
        head = page.read_text(encoding="utf-8").split("</head>", 1)[0]
        if "/css/site.css" not in head:
            continue
        assert tag in head, page
        assert head.index(tag) < head.index('href="/css/site.css"'), page
