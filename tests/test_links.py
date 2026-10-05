"""Every root-relative link resolves to a file that the build wrote."""

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

EXTERNAL_RE = re.compile(r"^(?:https?:)?//")


class LinkParser(HTMLParser):
    """Collects href and src attribute values from a page."""

    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.targets.append(value)


def _resolve(root: Path, href: str) -> Path | None:
    """Map a root-relative href to its file, or None for external/fragment links."""
    if EXTERNAL_RE.match(href) or href.startswith(("#", "mailto:")):
        return None
    path = urlsplit(href).path
    if not path or not path.startswith("/"):
        return None
    target = root / path.lstrip("/")
    return target / "index.html" if path.endswith("/") else target


def test_all_root_relative_links_resolve(built) -> None:
    out = built.out
    missing: list[str] = []
    for page in sorted(out.rglob("*.html")):
        parser = LinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for href in parser.targets:
            target = _resolve(out, href)
            if target is not None and not target.is_file():
                missing.append(f"{page.relative_to(out)} -> {href}")
    assert not missing, "\n".join(sorted(set(missing)))


def test_sitemap_lists_every_page(built) -> None:
    sitemap = (built.out / "sitemap.xml").read_text(encoding="utf-8")
    html_pages = {
        "/" + str(p.relative_to(built.out)).replace("\\", "/")
        for p in built.out.rglob("*.html")
        if p.name != "404.html"
    }
    urls = set(re.findall(r"<loc>https://chock\.sh(/[^\s<]*)</loc>", sitemap))
    # sitemap urls point at canonical directories, not index.html files.
    dirs = set()
    for rel in html_pages:
        dirs.add("/" if rel == "/index.html" else rel[: -len("index.html")])
    assert urls == dirs, f"missing: {sorted(dirs - urls)}\nextra: {sorted(urls - dirs)}"


def test_robots_disallows_all_while_not_launched(built) -> None:
    robots = (built.out / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /" in robots
    assert "Allow:" not in robots
