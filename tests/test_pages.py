"""Per-page structure: one h1, lang, CSP, footer sentence, labels, a11y ids."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import yaml

from tests.conftest import DATA

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' "
    "data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
    "base-uri 'none'; form-action 'none'"
)
FOOTER = "Friction, not a security boundary."


class PageParser(HTMLParser):
    """Collects the facts a page test needs from one HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.h1 = 0
        self.titles: list[str] = []
        self.csp = ""
        self.lang = ""
        self.labels_for: set[str] = set()
        self.controls: list[tuple[str, str]] = []  # (tag, id)
        self.in_title = False
        self._title = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang", "")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            if attrs.get("http-equiv") == "Content-Security-Policy":
                self.csp = attrs.get("content", "")
        elif tag == "label" and attrs.get("for"):
            self.labels_for.add(attrs["for"])
        elif tag in ("input", "select", "textarea"):
            self.controls.append((tag, attrs.get("id", "")))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self._title.append(data)

    @property
    def title(self) -> str:
        return "".join(self._title)


def _pages(built) -> list[Path]:
    return sorted(built.out.rglob("*.html"))


def _policy_ids(built) -> list[str]:
    data = json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))
    return [p["id"] for p in data["policies"]]


def _docs_pages(built) -> int:
    """Docs pages: one per docs.yaml page, agentseam agent, visible policy, architecture diagram and CLI command."""
    docs = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
    api = json.loads((built.out / "api" / "docs" / "index.json").read_text("utf-8"))
    diagrams = len(list((DATA / "architecture").glob("*.json")))
    return (
        len(docs["pages"])
        + len(api["agents"])
        + len(_policy_ids(built))
        + diagrams
        + len(docs["cli_pages"])
    )


def test_every_visible_policy_has_a_page(built) -> None:
    for pid in _policy_ids(built):
        page = built.out / "coding" / "policies" / pid / "index.html"
        assert page.is_file(), pid


def test_every_page_has_one_h1_lang_csp_title(built) -> None:
    pages = _pages(built)
    # shared + sections + 404, plus the docs section (DOC-1)
    assert len(pages) == len(_policy_ids(built)) + 15 + _docs_pages(built)
    for page in pages:
        parser = PageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        rel = page.relative_to(built.out)
        assert parser.h1 == 1, f"{rel}: {parser.h1} h1 elements"
        assert parser.lang == "en", rel
        assert parser.csp == CSP, rel
        assert parser.title.strip().endswith("chock.sh"), rel
        assert FOOTER in page.read_text(encoding="utf-8"), rel


def test_every_input_and_select_has_a_label(built) -> None:
    for page in _pages(built):
        parser = PageParser()
        text = page.read_text(encoding="utf-8")
        parser.feed(text)
        for tag, cid in parser.controls:
            assert cid, f"{page}: {tag} without id"
            labelled = cid in parser.labels_for or re.search(
                rf'<label[^>]*>\s*<input[^>]*id="{re.escape(cid)}"', text
            )
            assert labelled, f"{page}: {tag}#{cid} has no label"


def test_label_chip_carries_word_glyph_and_title(built) -> None:
    html = (
        built.out / "coding" / "policies" / "block-no-verify" / "index.html"
    ).read_text(encoding="utf-8")
    assert 'class="label label-block"' in html
    assert 'title="blocks: The agent refuses the action."' in html
    assert 'aria-hidden="true">■' in html


def test_block_no_verify_page_content(built) -> None:
    html = (
        built.out / "coding" / "policies" / "block-no-verify" / "index.html"
    ).read_text(encoding="utf-8")
    assert "<title>Block No-Verify: blocks refuses a matched" in html
    assert 'id="what-it-does"' in html
    assert 'id="misses"' in html
    assert 'id="label"' in html
    assert 'id="examples"' in html
    assert 'id="provenance"' in html
    assert 'id="latest-change"' in html
    assert "git commit --no-verify -m wip" in html
    assert "107 of 107 pass" in html
    assert "older aliases, scripts, $VARs." in html
    assert "/coding/builder/#add=block-no-verify" in html
    assert "/coding/builder/#preset=git-hygiene" in html
    assert 'type="application/ld+json"' in html
    assert 'type="text/markdown" href="index.md"' in html
    assert (
        'type="application/json" href="/api/coding/policies/block-no-verify.json"'
        in html
    )


def test_plugin_note_only_on_advisory_enforced_at_commit(built) -> None:
    note = "Advisory inside the agent"
    protect = (
        built.out / "coding" / "policies" / "protect-main-branch" / "index.html"
    ).read_text(encoding="utf-8")
    assert note in protect
    assert "enforced at commit" in protect
    block = (
        built.out / "coding" / "policies" / "block-no-verify" / "index.html"
    ).read_text(encoding="utf-8")
    assert note not in block


def test_advisory_policy_without_execute_cases_has_no_examples(built) -> None:
    data = json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))
    no_examples = [p for p in data["policies"] if not p["examples"]]
    assert no_examples, "expected at least one policy with no execute cases"
    for policy in no_examples:
        html = (
            built.out / "coding" / "policies" / policy["id"] / "index.html"
        ).read_text(encoding="utf-8")
        assert 'id="examples"' not in html, policy["id"]
        assert "This policy does not state what it misses." in html or policy["misses"]


def test_page_weights(built) -> None:
    for page in _pages(built):
        size = page.stat().st_size
        assert size < 100_000, f"{page}: {size} bytes"
    site_json = built.out / "data" / "site.json"
    assert site_json.stat().st_size < 300_000


def test_skip_link_and_main(built) -> None:
    for page in _pages(built):
        text = page.read_text(encoding="utf-8")
        assert 'class="skip-link" href="#content">Skip to content' in text, page
        assert '<main id="content">' in text, page


class _FooterLinks(HTMLParser):
    """The visible text of every <a> inside <footer>."""

    def __init__(self) -> None:
        super().__init__()
        self.footer = 0
        self.in_a = False
        self.texts: list[str] = []
        self._a: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "footer":
            self.footer += 1
        elif tag == "a" and self.footer:
            self.in_a = True
            self._a = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "footer" and self.footer:
            self.footer -= 1
        elif tag == "a" and self.in_a:
            self.in_a = False
            self.texts.append("".join(self._a))

    def handle_data(self, data: str) -> None:
        if self.in_a:
            self._a.append(data)


def test_footer_link_text_is_never_a_url_or_path(built) -> None:
    """A (href, label) swap shows the raw link as text; catch it on every page."""
    for page in _pages(built):
        parser = _FooterLinks()
        parser.feed(page.read_text(encoding="utf-8"))
        assert parser.texts, f"{page}: no footer links"
        for text in parser.texts:
            text = text.strip()
            assert text, f"{page}: empty footer link text"
            assert not text.startswith(("/", "http")), f"{page}: {text!r}"


class _TextOutsideCode(HTMLParser):
    """Rendered text, skipping <pre>, <code>, <script> and <style> subtrees."""

    SKIP = frozenset({"pre", "code", "script", "style"})

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self.depth += 1

    def handle_startendtag(self, tag: str, attrs) -> None:
        pass

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.depth:
            self.text.append(data)


def test_no_literal_backticks_in_rendered_text(built) -> None:
    """Backticks in prose become <code>; none survive as literal text."""
    for page in _pages(built):
        parser = _TextOutsideCode()
        parser.feed(page.read_text(encoding="utf-8"))
        assert "`" not in "".join(parser.text), page
