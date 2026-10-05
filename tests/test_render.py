"""Tests for render.py: one-pass token fill, escaping and token/value mismatches."""

import pytest

from sitegen.render import RenderError, Safe, render


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
