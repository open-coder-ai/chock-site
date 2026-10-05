"""Tests for render.py: one-pass token fill, escaping and token/value mismatches."""

import json
import re
from pathlib import Path

import pytest

from sitegen.render import Prose, RenderError, Safe, render


def test_token_inside_a_value_is_not_rescanned() -> None:
    out = render(
        "<p>__DESC__</p><p>__SECRET__</p>",
        DESC="hello __SECRET__",
        SECRET=Safe("<script>x()</script>"),
    )
    assert out == "<p>hello __SECRET__</p><p><script>x()</script></p>"


def test_template_token_without_a_value_raises() -> None:
    with pytest.raises(RenderError, match="SECRET"):
        render("<p>__DESC__</p><p>__SECRET__</p>", DESC="x")


def test_value_without_a_template_token_raises() -> None:
    with pytest.raises(RenderError, match="EXTRA"):
        render("<p>__DESC__</p>", DESC="x", EXTRA="y")


def test_plain_value_is_escaped() -> None:
    out = render("<p>__DESC__</p>", DESC='<img onerror="x">')
    assert out == "<p>&lt;img onerror=&quot;x&quot;&gt;</p>"


def test_safe_value_is_not_escaped() -> None:
    out = render("<div>__BODY__</div>", BODY=Safe("<b>ok</b>"))
    assert out == "<div><b>ok</b></div>"


def test_script_in_a_value_is_escaped() -> None:
    out = render("<p>__DESC__</p>", DESC="<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out


def test_event_handler_in_a_value_is_escaped() -> None:
    out = render('<a title="__DESC__">x</a>', DESC='"onmouseover="alert(1)')
    assert 'onmouseover="alert' not in out
    assert "&quot;onmouseover=&quot;alert(1)" in out


def test_render_text_never_escapes() -> None:
    from sitegen.render import render_text

    out = render_text("# __TITLE__\n\n__BODY__", TITLE="T", BODY="a & b < c")
    assert out == "# T\n\na & b < c"


def test_render_text_enforces_tokens_too() -> None:
    from sitegen.render import render_text

    with pytest.raises(RenderError, match="MISSING"):
        render_text("__A__ __MISSING__", A="x")


def test_prose_backticks_become_code() -> None:
    out = render("<p>__BODY__</p>", BODY=Prose("run `chock install` then <b>x</b>"))
    assert "<code>chock install</code>" in out
    assert "&lt;b&gt;x&lt;/b&gt;" in out
    assert "`" not in out


def test_jsonld_escapes_parser_breakouts(built, tmp_path) -> None:
    """A name/description with `<!--<script>` or `</script>` stays inside JSON-LD."""
    from html.parser import HTMLParser

    from sitegen.pageparts import write_page

    evil_name = "<!--<script>"
    evil_desc = "close </script><h1>defaced</h1>"
    write_page(
        built.site,
        tmp_path,
        Path(__file__).resolve().parents[1] / "templates",
        path="/x/",
        title="t",
        description="d",
        content=Safe("<h1>real</h1>"),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": evil_name,
            "description": evil_desc,
        },
    )
    page = (tmp_path / "x" / "index.html").read_text(encoding="utf-8")

    body = re.search(
        r'<script type="application/ld\+json">\n(.*?)\n</script>', page, re.DOTALL
    ).group(1)
    assert "<" not in body
    data = json.loads(body)
    assert data["name"] == evil_name
    assert data["description"] == evil_desc

    class Count(HTMLParser):
        h1 = 0

        def handle_starttag(self, tag, attrs):
            if tag == "h1":
                self.h1 += 1

    counter = Count()
    counter.feed(page)
    assert counter.h1 == 1
    assert "Friction, not a security boundary." in page


def test_data_fill_is_one_pass() -> None:
    from sitegen.pageparts import data_fill

    out = data_fill("__A__ and __B__", {"__A__": "x __B__", "__B__": "y"})
    assert out == "x __B__ and y"
