"""Plan 6.7 checks: home claims, SEO tags, sitemap, robots, banned phrases."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

BANNED = (
    "trusted by",
    "#1",
    "secure your",
    "protects you",
    "guarantee",
    "unbreakable",
)
ROOT = Path(__file__).resolve().parents[1]


class MetaParser(HTMLParser):
    """Collects canonical, meta description and og:* tags."""

    def __init__(self) -> None:
        super().__init__()
        self.canonical = ""
        self.description = ""
        self.og: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href", "")
        if tag == "meta":
            if attrs.get("name") == "description":
                self.description = attrs.get("content", "")
            prop = attrs.get("property", "") or attrs.get("name", "")
            if prop.startswith(("og:", "twitter:")):
                self.og[prop] = attrs.get("content", "")


def _pages(built) -> list[Path]:
    return sorted(built.out.rglob("*.html"))


def test_home_uses_only_catalog_examples(built) -> None:
    data = json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))
    known = {p["id"] for p in data["policies"]}
    home = (ROOT / "data" / "home.yaml").read_text(encoding="utf-8")
    for pid in re.findall(r"policy: \"([\w-]+)\"", home):
        assert pid in known, f"home.yaml references unknown policy {pid}"


def test_home_hero_demo_and_stats(built) -> None:
    html = (built.out / "index.html").read_text(encoding="utf-8")
    assert "Blocks your coding agent&#x27;s" in html
    assert "wrong moves before they land." in html
    assert "OPEN SOURCE · POLICY BLOCKS FOR CODING AGENTS" in html
    assert (
        "Blocks your coding agent&#x27;s wrong moves before they land. Part of open-coder-ai."
        in html
    )
    assert (
        "<title>Blocks your coding agent&#x27;s wrong moves before they land. · chock.sh</title>"
        in html
    )
    data = json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))
    ids = {p["id"] for p in data["policies"]}
    for pid in ("block-no-verify", "protect-main-branch", "scan-secrets"):
        assert pid in ids, pid
    tested = sum(p["eval_executed"] for p in data["policies"])
    assert f"{len(ids)} POLICIES · {tested:,} TESTS" in html
    assert "git commit --no-verify -m wip" in html
    assert "Refused by block-no-verify" in html
    assert f"{data['catalog']['ref'][:12]}" in html


def test_seo_tags_on_every_page(built) -> None:
    for page in _pages(built):
        if page.name == "404.html":
            continue
        parser = MetaParser()
        parser.feed(page.read_text(encoding="utf-8"))
        rel = page.relative_to(built.out)
        assert parser.canonical.startswith("https://chock.sh"), rel
        assert len(parser.description) > 30, rel
        for prop in ("og:title", "og:description", "og:type", "og:url", "og:image"):
            assert parser.og.get(prop), f"{rel}: missing {prop}"


# A raw catalog field opening a sentence, such as "trigger:" or "avoid:".
FIELD_LABEL = re.compile(r"[a-z][a-z_-]*:\s")
JSONLD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


def test_no_link_preview_text_starts_with_a_field_label(built) -> None:
    """Meta, og:/twitter: and JSON-LD descriptions open with prose, never a field like "trigger:"."""
    checked = 0
    for page in _pages(built):
        text = page.read_text(encoding="utf-8")
        parser = MetaParser()
        parser.feed(text)
        previews = [parser.description] + [
            value for key, value in parser.og.items() if key.endswith("description")
        ]
        for block in JSONLD.findall(text):
            data = json.loads(block)
            if isinstance(data, dict) and isinstance(data.get("description"), str):
                previews.append(data["description"])
        for preview in previews:
            checked += 1
            assert not FIELD_LABEL.match(preview), (str(page), preview)
    assert checked > 500


def _has_banned(text: str) -> str | None:
    for phrase in BANNED:
        # "#1" as a ranking claim is "#1 <word>"; an item number in catalog
        # prose like "Wave 3 #1)" is not a claim.
        if phrase == "#1":
            if re.search(r"(?<![\w#])#1\s+[a-z]", text):
                return phrase
        elif re.search(rf"(?<![\w#]){re.escape(phrase)}(?![\w])", text):
            return phrase
    return None


def test_no_banned_marketing_phrases(built) -> None:
    # (?<![\w#]) keeps catalog terms like "pkcs#12" from matching "#1".
    for page in _pages(built):
        text = page.read_text(encoding="utf-8").lower()
        hit = _has_banned(text)
        assert hit is None, f"{page}: banned phrase {hit!r}"
    for data_file in (ROOT / "data").rglob("*"):
        if data_file.suffix in (".yaml", ".json"):
            text = data_file.read_text(encoding="utf-8").lower()
            hit = _has_banned(text)
            assert hit is None, f"{data_file}: banned phrase {hit!r}"


def test_jsonld_parses_and_types(built) -> None:
    for page in _pages(built):
        text = page.read_text(encoding="utf-8")
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', text, re.DOTALL
        )
        assert blocks, page
        for block in blocks:
            data = json.loads(block)
            assert data["@context"] == "https://schema.org"


def test_jsonld_types(built) -> None:
    def types(path: Path) -> list[str]:
        text = path.read_text(encoding="utf-8")
        return [
            json.loads(b)["@type"]
            for b in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', text, re.DOTALL
            )
        ]

    out = built.out
    assert "WebSite" in types(out / "index.html")
    assert "ItemList" in types(out / "coding" / "policies" / "index.html")
    assert "SoftwareSourceCode" in types(
        out / "coding" / "policies" / "block-no-verify" / "index.html"
    )
    assert "FAQPage" in types(out / "faq" / "index.html")


def test_favicon_and_og_card_local_and_sized(built) -> None:
    assert (built.out / "favicon.svg").is_file()
    png = built.out / "img" / "og-card.png"
    data = png.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    w = int.from_bytes(data[16:20], "big")
    h = int.from_bytes(data[20:24], "big")
    assert (w, h) == (1200, 630)


def test_favicon_uses_only_e10_tokens() -> None:
    """The favicon's colours are E10 tokens from site.css, and no pre-E10 colour."""
    css = (ROOT / "static" / "css" / "site.css").read_text(encoding="utf-8")
    root = css[css.index(":root {") :].split("}", 1)[0]
    tokens = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", root)}
    svg = (ROOT / "static" / "favicon.svg").read_text(encoding="utf-8")
    used = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{3,8}\b", svg)}
    assert {"#0B1B33", "#38BDF8", "#0EA5E9"} <= used
    assert used <= tokens
    assert not used & {"#D9B45C", "#0D1626"}
    assert not re.search(r"rgb|hsl", svg)
