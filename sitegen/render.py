"""Fill __TOKEN__ placeholders in template files, escaping every value into HTML."""

import html
import re
from pathlib import Path

TOKEN_RE = re.compile(r"__[A-Z0-9_]+__")


class Safe(str):
    """A value that is itself rendered HTML and must not be escaped again."""


def render(template: str, **tokens: object) -> str:
    """The template with every __TOKEN__ replaced; non-Safe values are html.escaped."""
    for name, value in tokens.items():
        if not isinstance(value, Safe):
            value = Safe(html.escape(str(value), quote=True))
        template = template.replace(f"__{name}__", value)
    return template


def render_file(path: Path, **tokens: object) -> str:
    """render() on a template file's contents."""
    return render(path.read_text(encoding="utf-8"), **tokens)
