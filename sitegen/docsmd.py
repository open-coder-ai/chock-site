"""Markdown from chock's docs as escaped HTML, one template per element, links resolved by the caller."""

import html
import re
from collections.abc import Callable
from pathlib import Path

from .pageparts import PageError, slug
from .render import Safe, render_file

FENCE_RE = re.compile(r"^(\s*)(```+|~~~+)\s*([\w+-]*)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
HR_RE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
CALLOUT_RE = re.compile(r"^\[!([A-Za-z]+)\]\s*$")
INLINE_RE = re.compile(
    r"(?P<tick>`+)(?P<code>.+?)(?P=tick)"
    r"|!?\[(?P<text>[^\]]+)\]\((?P<href>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|(?<![\w*])\*(?P<em>[^*\s](?:[^*]*?[^*\s])?)\*(?![\w*])"
    r"|(?<![\w_])_(?P<em2>[^_\s](?:[^_]*?[^_\s])?)_(?![\w_])"
)
Resolve = Callable[[str], str]


class Renderer:
    """Renders one page's Markdown: heading ids stay unique across every call."""

    def __init__(
        self,
        templates: Path,
        resolve: Resolve,
        shift: int = 0,
        callouts: dict[str, str] | None = None,
    ) -> None:
        self.dir = templates / "docs" / "md"
        self.resolve = resolve
        self.shift = shift
        self.callouts = callouts or {}
        self.ids: set[str] = set()
        # (level, id, text) of each h2 and h3, for the page's "On this page" list.
        self.toc: list[tuple[int, str, str]] = []

    def _t(self, name: str, **tokens: object) -> str:
        return render_file(self.dir / f"{name}.html", **tokens)

    def heading_id(self, text: str) -> str:
        """A heading slug not used on the page yet."""
        base = slug(text) or "section"
        found, n = base, 2
        while found in self.ids:
            found, n = f"{base}-{n}", n + 1
        self.ids.add(found)
        return found

    def toc_heading(self, level: int, text: str) -> str:
        """A new heading id, listed in the page's table of contents when it is an h2 or h3."""
        found = self.heading_id(text)
        if level in (2, 3):
            self.toc.append((level, found, text))
        return found

    def inline(self, text: str) -> Safe:
        """Escaped text with code spans, links, bold and emphasis as elements."""
        out: list[str] = []
        pos = 0
        for m in INLINE_RE.finditer(text):
            out.append(html.escape(text[pos : m.start()], quote=True))
            pos = m.end()
            if m.group("tick"):
                out.append(self._t("code", TEXT=m.group("code").strip()))
            elif m.group("href"):
                out.append(
                    self._t(
                        "a",
                        HREF=self.resolve(m.group("href")),
                        TEXT=self.inline(m.group("text")),
                    )
                )
            elif m.group("bold") is not None:
                out.append(self._t("strong", TEXT=self.inline(m.group("bold"))))
            else:
                em = m.group("em") if m.group("em") is not None else m.group("em2")
                out.append(self._t("em", TEXT=self.inline(em)))
        out.append(html.escape(text[pos:], quote=True))
        return Safe("".join(out))

    def blocks(self, text: str) -> Safe:
        """Every block in `text` as HTML."""
        return Safe("".join(self._blocks(text.splitlines())))

    def _blocks(self, lines: list[str], tight: bool = False) -> list[str]:
        out: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            if fence := FENCE_RE.match(line):
                i = self._fence(lines, i, fence, out)
            elif heading := HEADING_RE.match(line):
                level = min(len(heading.group(1)) + self.shift, 6)
                text = heading.group(2)
                out.append(
                    self._t(
                        "h",
                        LEVEL=str(level),
                        ID=self.toc_heading(level, _plain(text)),
                        TEXT=self.inline(text),
                    )
                )
                i += 1
            elif HR_RE.match(line):
                out.append(self._t("hr"))
                i += 1
            elif line.lstrip().startswith(">"):
                i = self._quote(lines, i, out)
            elif LIST_RE.match(line):
                i = self._list(lines, i, out)
            elif (
                line.lstrip().startswith("|")
                and i + 1 < len(lines)
                and TABLE_SEP_RE.match(lines[i + 1])
            ):
                i = self._table(lines, i, out)
            else:
                i = self._para(lines, i, out, tight)
        return out

    def _fence(self, lines: list[str], i: int, fence: re.Match, out: list[str]) -> int:
        indent, marker, lang = len(fence.group(1)), fence.group(2), fence.group(3)
        body: list[str] = []
        i += 1
        while i < len(lines) and not lines[i].strip().startswith(marker):
            body.append(lines[i][indent:] if lines[i][:indent].isspace() else lines[i])
            i += 1
        out.append(self._t("pre", LANG=lang or "text", CODE="\n".join(body)))
        return i + 1

    def _quote(self, lines: list[str], i: int, out: list[str]) -> int:
        body: list[str] = []
        while i < len(lines) and lines[i].lstrip().startswith(">"):
            body.append(re.sub(r"^\s*> ?", "", lines[i]))
            i += 1
        if callout := CALLOUT_RE.match(body[0]):
            kind = callout.group(1).lower()
            if kind not in self.callouts:
                raise PageError(f"docs source: unknown callout [!{callout.group(1)}]")
            out.append(
                self._t(
                    "callout",
                    KIND=kind,
                    LABEL=self.callouts[kind],
                    BODY=Safe("".join(self._blocks(body[1:]))),
                )
            )
            return i
        out.append(self._t("blockquote", BODY=Safe("".join(self._blocks(body)))))
        return i

    def _list(self, lines: list[str], i: int, out: list[str]) -> int:
        first = LIST_RE.match(lines[i])
        indent = len(first.group(1))
        ordered = first.group(2)[0].isdigit()
        start = int(first.group(2)[:-1]) if ordered else 1
        items: list[list[str]] = []
        while i < len(lines):
            m = LIST_RE.match(lines[i])
            if m and len(m.group(1)) == indent and m.group(2)[0].isdigit() == ordered:
                content = len(m.group(1)) + len(m.group(2)) + 1
                items.append([m.group(3)])
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if not nxt.strip():
                        if i + 1 < len(lines) and _indent(lines[i + 1]) > indent:
                            items[-1].append("")
                            i += 1
                            continue
                        break
                    if _indent(nxt) > indent:
                        items[-1].append(nxt[min(content, _indent(nxt)) :])
                        i += 1
                    elif LIST_RE.match(nxt) or _starts_block(nxt):
                        break
                    else:
                        items[-1].append(nxt.strip())
                        i += 1
            else:
                break
        rendered = [
            self._t("li", BODY=Safe("".join(self._blocks(body, "" not in body))))
            for body in items
        ]
        if ordered:
            out.append(self._t("ol", START=str(start), ITEMS=Safe("".join(rendered))))
        else:
            out.append(self._t("ul", ITEMS=Safe("".join(rendered))))
        return i

    def _table(self, lines: list[str], i: int, out: list[str]) -> int:
        head = _cells(lines[i])
        aligns = [_align(c) for c in _cells(lines[i + 1])]
        i += 2
        rows: list[list[str]] = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            rows.append(_cells(lines[i]))
            i += 1

        def row(cells: list[str], kind: str) -> str:
            return self._t(
                "tr",
                CELLS=Safe(
                    "".join(
                        self._t(
                            kind,
                            ALIGN=aligns[n] if n < len(aligns) else "left",
                            TEXT=self.inline(cell),
                        )
                        for n, cell in enumerate(cells)
                    )
                ),
            )

        out.append(
            self._t(
                "table",
                HEAD=Safe(row(head, "th")),
                BODY=Safe("".join(row(r, "td") for r in rows)),
            )
        )
        return i

    def _para(self, lines: list[str], i: int, out: list[str], tight: bool) -> int:
        body: list[str] = []
        while (
            i < len(lines)
            and lines[i].strip()
            and not (body and _starts_block(lines[i]))
        ):
            body.append(lines[i].strip())
            i += 1
        text = self.inline(" ".join(body))
        out.append(text if tight else self._t("p", TEXT=text))
        return i


def _plain(text: str) -> str:
    """Heading text without inline Markdown, for its slug."""
    return INLINE_RE.sub(
        lambda m: (
            m.group("code")
            or m.group("text")
            or m.group("bold")
            or m.group("em")
            or m.group("em2")
            or ""
        ),
        text,
    )


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _starts_block(line: str) -> bool:
    stripped = line.lstrip()
    return bool(
        FENCE_RE.match(line)
        or HEADING_RE.match(line)
        or stripped.startswith((">", "|"))
        or LIST_RE.match(line)
        or HR_RE.match(line)
    )


def _cells(line: str) -> list[str]:
    """A table row's cells: split on pipes outside code spans, outer pipes dropped."""
    text = line.strip()
    text = text.removeprefix("|")
    text = text[:-1] if text.endswith("|") and not text.endswith("\\|") else text
    cells, cur, tick = [], [], False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "`":
            tick = not tick
        if ch == "|" and not tick:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def _align(cell: str) -> str:
    cell = cell.strip()
    if cell.startswith(":") and cell.endswith(":"):
        return "center"
    if cell.endswith(":"):
        return "right"
    return "left"


def _outside_fences(text: str) -> list[tuple[bool, str]]:
    """The text as (in_fence, line) pairs."""
    out, marker = [], None
    for line in text.splitlines():
        fence = FENCE_RE.match(line)
        if marker is None and fence:
            marker = fence.group(2)
            out.append((True, line))
        elif marker is not None:
            out.append((True, line))
            if (
                line.strip().startswith(marker)
                and not line.strip()[len(marker) :].strip()
            ):
                marker = None
        else:
            out.append((False, line))
    return out


def headings(text: str) -> list[tuple[int, str, int]]:
    """(level, text, line number) for each heading outside code fences."""
    found = []
    for n, (fenced, line) in enumerate(_outside_fences(text)):
        if not fenced and (m := HEADING_RE.match(line)):
            found.append((len(m.group(1)), m.group(2), n))
    return found


def sections(text: str, titles: list[str], level: int = 2) -> str:
    """The named level-`level` sections of `text`, in the order `titles` names them."""
    lines = text.splitlines()
    marks = headings(text)
    chunks = []
    for title in titles:
        hit = [(lv, n) for lv, t, n in marks if lv == level and t == title]
        if len(hit) != 1:
            raise PageError(f"docs source: {len(hit)} sections titled {title!r}")
        start = hit[0][1]
        end = next((n for lv, _, n in marks if n > start and lv <= level), len(lines))
        chunks.append("\n".join(lines[start:end]).strip() + "\n")
    return "\n".join(chunks)


def first_sections(text: str, count: int, level: int = 2) -> str:
    """The first `count` level-`level` sections of `text`."""
    titles = [t for lv, t, _ in headings(text) if lv == level][:count]
    return sections(text, titles, level)


def first_code(text: str) -> tuple[str, str]:
    """The language and body of the first fenced code block in `text`."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if fence := FENCE_RE.match(line):
            indent, marker = len(fence.group(1)), fence.group(2)
            body = []
            for nxt in lines[i + 1 :]:
                if nxt.strip().startswith(marker):
                    return fence.group(3) or "text", "\n".join(body)
                body.append(nxt[indent:] if nxt[:indent].isspace() else nxt)
    raise PageError("docs source: no code block where one was expected")


def rewrite_links(text: str, resolve: Resolve, before_fence: str = "") -> str:
    """The Markdown twin's copy: link targets outside code resolved, a line before each fence."""

    def _inline(line: str) -> str:
        def _one(m: re.Match) -> str:
            if not m.group("href"):
                return m.group(0)
            return f"[{m.group('text')}]({resolve(m.group('href'))})"

        return INLINE_RE.sub(_one, line)

    out: list[str] = []
    inside = False
    for fenced, line in _outside_fences(text):
        if fenced and not inside and before_fence:
            out += [before_fence, ""]
        inside = fenced
        out.append(line if fenced else _inline(line))
    return "\n".join(out) + "\n"
