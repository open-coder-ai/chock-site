"""R-1 theme checks: WCAG contrast of the dusk tokens and self-hosted fonts."""

import re
from pathlib import Path

TOKEN_RE = re.compile(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;")
FONT_URL_RE = re.compile(r'url\("(/fonts/[^"]+)"\)\s*format\("woff2"\)')

# The pairs the redesign plan lists; every pair must pass WCAG AA (4.5:1).
CONTRAST_PAIRS = [
    ("text", "bg"),
    ("body", "bg"),
    ("body", "panel"),
    ("muted", "bg"),
    ("muted", "panel"),
    ("accent", "bg"),
    ("accent", "panel"),
    ("on-accent", "accent"),
    ("warn-fg", "warn-bg"),
    ("ok", "bg"),
    ("text", "panel"),
    ("accent", "panel-2"),
    ("body", "panel-2"),
]


def _tokens(built) -> dict[str, str]:
    css = (built.out / "css" / "site.css").read_text(encoding="utf-8")
    return {name: value.upper() for name, value in TOKEN_RE.findall(css)}


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


def test_dusk_tokens_meet_contrast(built) -> None:
    tokens = _tokens(built)
    for foreground, background in CONTRAST_PAIRS:
        assert foreground in tokens, f"--{foreground} missing"
        assert background in tokens, f"--{background} missing"
        ratio = _ratio(tokens[foreground], tokens[background])
        assert ratio >= 4.5, f"{foreground} on {background}: {ratio:.2f}:1"


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
