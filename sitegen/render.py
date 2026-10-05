"""Fill __TOKEN__ placeholders in template files, escaping every value into HTML."""

import html
import re
from pathlib import Path

TOKEN_RE = re.compile(r"__[A-Z0-9_]+__")


class Safe(str):
    """A value that is itself rendered HTML and must not be escaped again."""


class RenderError(ValueError):
    """A template token without a value, or a value without a token."""


def render(template: str, **tokens: object) -> str:
    """One-pass fill: a value holding __OTHER__ is inserted literally, never rescanned."""
    found = {t[2:-2] for t in TOKEN_RE.findall(template)}
    missing = found - set(tokens)
    if missing:
        msg = f"template tokens with no value: {', '.join(sorted(missing))}"
        raise RenderError(msg)
    unused = set(tokens) - found
    if unused:
        msg = f"values with no token in the template: {', '.join(sorted(unused))}"
        raise RenderError(msg)

    def _fill(match: re.Match) -> str:
        value = tokens[match.group(0)[2:-2]]
        if isinstance(value, Safe):
            return str(value)
        return html.escape(str(value), quote=True)

    return TOKEN_RE.sub(_fill, template)


def render_file(path: Path, **tokens: object) -> str:
    """render() on a template file's contents."""
    return render(path.read_text(encoding="utf-8"), **tokens)
