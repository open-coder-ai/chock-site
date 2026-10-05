"""Fill __TOKEN__ placeholders in template files, escaping every value into HTML."""

import html
import re
from pathlib import Path

TOKEN_RE = re.compile(r"__[A-Z0-9_]+__")


class Safe(str):
    """A value that is itself rendered HTML and must not be escaped again."""


class Prose(str):
    """Escaped text in which `inline code` backticks become <code> elements."""


class RenderError(ValueError):
    """A template token without a value, or a value without a token."""


CODE_SPAN_RE = re.compile(r"`([^`]+)`")


def _prose(value: object) -> str:
    escaped = html.escape(str(value), quote=True)
    return CODE_SPAN_RE.sub(r"<code>\1</code>", escaped)


def _check(template: str, tokens: dict[str, object]) -> set[str]:
    """The token set after enforcing one value per token and vice versa."""
    found = {t[2:-2] for t in TOKEN_RE.findall(template)}
    missing = found - set(tokens)
    if missing:
        msg = f"template tokens with no value: {', '.join(sorted(missing))}"
        raise RenderError(msg)
    unused = set(tokens) - found
    if unused:
        msg = f"values with no token in the template: {', '.join(sorted(unused))}"
        raise RenderError(msg)
    return found


def render(template: str, **tokens: object) -> str:
    """One-pass fill: a value holding __OTHER__ is inserted literally, never rescanned."""
    _check(template, tokens)

    def _fill(match: re.Match) -> str:
        value = tokens[match.group(0)[2:-2]]
        if isinstance(value, Safe):
            return str(value)
        if isinstance(value, Prose):
            return _prose(value)
        return html.escape(str(value), quote=True)

    return TOKEN_RE.sub(_fill, template)


def render_text(template: str, **tokens: object) -> str:
    """One-pass fill for plain-text output (Markdown twins, txt files): no escaping."""
    _check(template, tokens)
    return TOKEN_RE.sub(lambda m: str(tokens[m.group(0)[2:-2]]), template)


def render_file(path: Path, **tokens: object) -> str:
    """render() on a template file's contents."""
    return render(path.read_text(encoding="utf-8"), **tokens)


def render_text_file(path: Path, **tokens: object) -> str:
    """render_text() on a template file's contents."""
    return render_text(path.read_text(encoding="utf-8"), **tokens)
