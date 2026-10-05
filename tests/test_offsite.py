"""Offsite rules: no external requests, no inline handlers, script hygiene."""

import re
from html.parser import HTMLParser
from pathlib import Path

EXTERNAL_RE = re.compile(r"^(?:https?:)?//")
# rel values whose href is fetched by the browser; canonical/alternate are not.
FETCHING_RELS = {
    "stylesheet",
    "icon",
    "manifest",
    "preload",
    "modulepreload",
    "prefetch",
    "apple-touch-icon",
}


class ResourceParser(HTMLParser):
    """Collects src attributes, fetching link hrefs, scripts and bad attrs."""

    def __init__(self) -> None:
        super().__init__()
        self.srcs: list[str] = []
        self.link_hrefs: list[str] = []
        self.scripts: list[tuple[str, str]] = []  # (src or "", type)
        self.bad_attrs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        for name in attrs:
            if name == "style" or name.startswith("on"):
                self.bad_attrs.append(f"<{tag} {name}>")
        if "src" in attrs:
            self.srcs.append(attrs["src"])
        if tag == "link":
            rels = set((attrs.get("rel") or "").split())
            if rels & FETCHING_RELS:
                self.link_hrefs.append(attrs.get("href", ""))
        if tag == "script":
            self.scripts.append((attrs.get("src", ""), attrs.get("type", "")))


def _html_files(built) -> list[Path]:
    return sorted(built.out.rglob("*.html"))


def test_no_external_src_or_fetching_link(built) -> None:
    for page in _html_files(built):
        parser = ResourceParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for src in parser.srcs:
            assert not EXTERNAL_RE.match(src), f"{page}: external src {src}"
        for href in parser.link_hrefs:
            assert not EXTERNAL_RE.match(href), f"{page}: external link {href}"


def test_scripts_are_same_origin_or_jsonld(built) -> None:
    for page in _html_files(built):
        parser = ResourceParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for src, type_ in parser.scripts:
            if src:
                assert src.startswith("/"), f"{page}: script src {src}"
            else:
                assert type_ == "application/ld+json", f"{page}: inline script"


def test_no_style_or_event_attributes(built) -> None:
    for page in _html_files(built):
        parser = ResourceParser()
        parser.feed(page.read_text(encoding="utf-8"))
        assert not parser.bad_attrs, f"{page}: {parser.bad_attrs[:5]}"


def test_css_has_no_urls_or_imports(built) -> None:
    for css in built.out.rglob("*.css"):
        text = css.read_text(encoding="utf-8")
        assert "url(" not in text, css
        assert "@import" not in text, css
        assert "http" not in text, css


def test_js_has_no_urls_eval_or_innerhtml(built) -> None:
    banned = ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function")
    for js in built.out.rglob("*.js"):
        for line in js.read_text(encoding="utf-8").splitlines():
            code = line.split("//", 1)[0] if not line.strip().startswith("//") else ""
            assert "http://" not in code and "https://" not in code, js
            for needle in banned:
                assert needle not in code, f"{js}: {needle}"


def test_no_leftover_tokens(built) -> None:
    # JSON payloads legitimately carry the engine's message templates
    # (__PRESENT__, __ABSENT__, __FILE__); the scan covers rendered docs.
    for page in built.out.rglob("*"):
        if page.suffix in (".html", ".md", ".txt", ".xml"):
            text = page.read_text(encoding="utf-8")
            assert not re.search(r"__[A-Z0-9_]+__", text), page
