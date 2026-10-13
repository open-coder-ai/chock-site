"""SITE-LLM: llms.txt, llms-full.txt, Markdown twins and semantic HTML on docs pages."""

import dataclasses
import re
from html.parser import HTMLParser
from itertools import pairwise
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import yaml

from sitegen import pages

ROOT = Path(__file__).resolve().parents[1]
DOCS = yaml.safe_load((ROOT / "data" / "docs.yaml").read_text(encoding="utf-8"))
# llms-full.txt was 812,017 bytes when this budget was set (2026-10-13).
LLMS_FULL_BUDGET = 1_048_576
LINK_RE = re.compile(r"\]\((/[^\s)]*)\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


class _Article(HTMLParser):
    """Headings, code blocks and language classes inside the docs article."""

    SKIP = ("docs-md", "docs-pager", "docs-built")

    def __init__(self) -> None:
        super().__init__()
        self.inside = False
        self.skip: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self.h1_count = 0
        self.code: list[str] = []
        self.pre_classes: list[str | None] = []
        self._heading: list | None = None
        self._pre: str | None = None
        self._in_pre = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        cls = dict(attrs).get("class") or ""
        if tag == "h1":
            self.h1_count += 1
        if tag == "article" and "docs-main" in cls.split():
            self.inside = True
            return
        if not self.inside:
            return
        if self.skip or any(c in cls.split() for c in self.SKIP):
            self.skip.append(tag)
            return
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = [int(tag[1]), ""]
        if tag == "pre":
            self._pre, self._in_pre = "", True
        elif tag == "code" and self._in_pre:
            self.pre_classes.append(cls or None)

    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            self.skip.pop()
            return
        if tag == "article" and self.inside:
            self.inside = False
        if self._heading and re.fullmatch(r"h[1-6]", tag):
            self.headings.append((self._heading[0], " ".join(self._heading[1].split())))
            self._heading = None
        if tag == "pre" and self._pre is not None:
            self.code.append(self._pre)
            self._pre, self._in_pre = None, False

    def handle_data(self, data: str) -> None:
        if not self.inside or self.skip:
            return
        if self._heading:
            self._heading[1] += data
        if self._pre is not None:
            self._pre += data


def _article(page: Path) -> _Article:
    parsed = _Article()
    parsed.feed(page.read_text(encoding="utf-8"))
    return parsed


def _md_headings(text: str) -> list[tuple[int, str]]:
    """ATX headings outside fenced code; indented code never starts with '#'."""
    found, fenced = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            fenced = not fenced
        elif not fenced and (m := re.match(r"^(#{1,6}) (.+)$", line)):
            found.append((len(m.group(1)), " ".join(m.group(2).split())))
    return found


def _md_unescape(text: str) -> str:
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!<>|])", r"\1", text)


def _docs_pages(built) -> list[Path]:
    return sorted((built.out / "docs").rglob("index.html"))


def _rel(built, path: Path) -> str:
    return "/" + path.relative_to(built.out).as_posix()


def test_llms_txt_follows_llmstxt_org_shape(built) -> None:
    text = (built.out / "llms.txt").read_text(encoding="utf-8")
    tagline = built.site.data["pages"]["home"]["title"]
    assert text.startswith(f"# chock.sh\n\n> {tagline}\n\n")
    assert re.search(r"^## Docs\n\n- \[", text, re.MULTILINE)


def test_every_llms_link_resolves_to_a_real_file(built) -> None:
    text = (built.out / "llms.txt").read_text(encoding="utf-8")
    links = LINK_RE.findall(text)
    assert len(links) > 100
    for link in links:
        href = link.split("#", 1)[0]
        target = built.out / href.lstrip("/")
        if href.endswith("/"):
            target = target / "index.html"
        assert target.is_file(), link


def test_every_docs_twin_has_an_llms_line_with_a_description(built) -> None:
    text = (built.out / "llms.txt").read_text(encoding="utf-8")
    for twin in sorted((built.out / "docs").rglob("index.md")):
        rel = _rel(built, twin)
        line = next((ln for ln in text.splitlines() if f"]({rel})" in ln), None)
        assert line is not None, rel
        assert re.search(rf"\]\({re.escape(rel)}\): \S", line), line


def test_llms_full_holds_every_docs_page_in_nav_order_within_budget(built) -> None:
    full = built.out / "llms-full.txt"
    size = full.stat().st_size
    assert size <= LLMS_FULL_BUDGET, f"llms-full.txt is {size} bytes"
    order = re.findall(
        r"^# (/docs/[^\n]+\.md)$", full.read_text(encoding="utf-8"), re.MULTILINE
    )
    topics = [
        DOCS["pages"][k]["path"] + "index.md" for g in DOCS["nav"] for k in g["pages"]
    ]
    assert [p for p in order if p in topics] == topics
    twins = {_rel(built, t) for t in (built.out / "docs").rglob("index.md")}
    assert set(order) == twins


def test_every_docs_page_links_its_twin(built) -> None:
    for page in _docs_pages(built):
        twin = page.parent / "index.md"
        href = _rel(built, twin)
        text = page.read_text(encoding="utf-8")
        assert twin.is_file(), href
        alternate = re.search(
            r'<link rel="alternate" type="text/markdown" href="([^"]+)">', text
        )
        assert alternate, href
        assert urljoin(_rel(built, page), alternate.group(1)) == href
        assert re.search(
            rf'<p class="docs-md mono"><a href="{re.escape(href)}" type="text/markdown" ',
            text,
        ), href


def test_twin_matches_the_page_prose(built) -> None:
    for page in _docs_pages(built):
        article = _article(page)
        twin = (page.parent / "index.md").read_text(encoding="utf-8")
        headings = [(n, _md_unescape(t)) for n, t in _md_headings(twin)]
        assert article.headings == headings, page
        for block in article.code:
            lines = [ln for ln in block.strip("\n").splitlines() if ln.strip()]
            if lines[0].startswith("usage: "):
                # Engine help: twins carry only the usage line; HTML has it all (DOC-1).
                lines = lines[:1]
            for line in lines:
                assert line.rstrip() in twin, f"{page}: {line!r}"


def test_docs_html_is_semantic(built) -> None:
    for page in _docs_pages(built):
        article = _article(page)
        assert article.h1_count == 1, page
        levels = [n for n, _ in article.headings]
        assert levels[0] == 1, page
        for before, after in pairwise(levels):
            assert after <= before + 1, f"{page}: h{before} then h{after}"
        for cls in article.pre_classes:
            assert cls and re.fullmatch(r"language-[a-z0-9-]+", cls), f"{page}: {cls}"


def test_copy_page_button_is_only_added_by_script(built) -> None:
    # Without JS the page shows the twin link; the button is the script's enhancement.
    for page in _docs_pages(built):
        assert "docs-copy-page" not in page.read_text(encoding="utf-8"), page
    script = (ROOT / "static" / "js" / "docs.js").read_text(encoding="utf-8")
    assert "fetch(url" in script
    assert script.count("fetch(") == 1
    assert "url.origin !== window.location.origin" in script


def test_robots_allows_llms_files_and_twins_once_launched(built, tmp_path) -> None:
    for launched in (False, True):
        site = dataclasses.replace(
            built.site, data={**built.site.data, "launched": launched}
        )
        pages._sitemap(site, tmp_path, ["/"])
        robots = RobotFileParser()
        robots.parse((tmp_path / "robots.txt").read_text(encoding="utf-8").splitlines())
        wanted = ["/llms.txt", "/llms-full.txt"] + [
            _rel(built, t) for t in (built.out / "docs").rglob("index.md")
        ]
        for path in wanted:
            allowed = robots.can_fetch("*", "https://chock.sh" + path)
            # Before launch every path is disallowed on purpose (test_links).
            assert allowed is launched, (launched, path)
