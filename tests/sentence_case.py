"""SITE-CAPS: find prose sentences that start with a lowercase letter in built HTML and Markdown."""

import re
from html.parser import HTMLParser

# A code span or block: never judged, and a sentence that starts with one is fine.
CODE = "\x00"
# Elements whose text starts a new block (paragraph, list item, cell, heading, caption...).
BLOCKS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "body",
        "br",
        "button",
        "caption",
        "dd",
        "details",
        "dialog",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "label",
        "legend",
        "li",
        "main",
        "nav",
        "ol",
        "option",
        "p",
        "section",
        "summary",
        "table",
        "tbody",
        "td",
        "text",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
CODE_TAGS = frozenset({"code", "pre", "kbd", "samp"})
# The site sets identifiers (policy ids, file names) in a `mono` element: code too.
CODE_CLASS = "mono"
# <title> is page metadata that cannot hold <code>; the page's h1 carries the same name.
SKIP_TAGS = frozenset({"script", "style", "template", "noscript", "title"})
# SITE-CAPS-2: a one-word UI label (heading, button, fact term, badge, pill, chip, nav
# group, stat label) is judged too; a one-word data value (a cell's "yes") is not.
LABEL_TAGS = frozenset(
    {"button", "caption", "dt", "h1", "h2", "h3", "h4", "h5", "h6", "legend", "summary"}
)
LABEL_CLASSES = frozenset(
    {
        "badge",
        "chip",
        "client-state",
        "docs-nav-group",
        "docs-state",
        "label",
        "pill",
        "stat-label",
        "status-badge",
        "track-badge",
    }
)
VOID = frozenset({"area", "br", "col", "embed", "hr", "img", "input", "source", "wbr"})
# Inline boxes the stylesheet lays out apart: their text never runs into its neighbour's.
APART = frozenset({"span"})
# Abbreviations whose full stop does not end a sentence.
ABBREV = re.compile(r"(?:\b(?:e\.g|i\.e|etc|vs|cf|approx|incl|no)\.)$", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<!\.)[.?!][\"'”’)\]]*\s+")
# A URL, domain or file name: an identifier, not a word.
IDENT = re.compile(
    r"^(?:[a-z][a-z0-9+.-]*://\S*|[a-z0-9_-]+(?:\.[a-z0-9_-]+)+(?:/\S*)?)",
    re.IGNORECASE,
)
LEAD = "\"'“‘([—–-•·*_ "


class Label(str):
    """A block whose text is a UI label: judged even when it is one word."""


def sentences(text: str) -> list[str]:
    """The sentences of one block of prose, code marked by CODE, leading quotes and dashes removed."""
    text = " ".join(text.split())
    cuts = [0]
    for m in SENTENCE_END.finditer(text):
        if not ABBREV.search(text[: m.start() + 1]):
            cuts.append(m.end())
    parts = [text[a:b] for a, b in zip(cuts, cuts[1:] + [len(text)], strict=True)]
    return [s for s in (p.lstrip(LEAD).strip() for p in parts) if s]


def is_prose(word: str, names: frozenset[str] = frozenset()) -> bool:
    """True when a sentence's first word is a prose word, not code, an identifier or a name."""
    bare = word.rstrip(".,:;!?)\"'”’")
    return not (
        word.startswith(CODE)
        or bare in names
        or IDENT.match(word)
        or any(c in bare for c in "_/+@~=<>#$`\\")
    )


def lowercase_starts(text: str, names: frozenset[str] = frozenset()) -> list[str]:
    """The sentences in one block that start with a lowercase prose word.

    A block of one word is a value (a cell's "yes", a type's "string"), not a sentence,
    unless it is a Label.
    """
    label = isinstance(text, Label)
    text = " ".join(text.split())
    if not text or (" " not in text and not label):
        return []
    bad = []
    for sentence in sentences(text):
        word = sentence.split(" ", 1)[0]
        if word[0].islower() and is_prose(word, names):
            bad.append(sentence[:80].replace(CODE, "`…`"))
    return bad


class _Blocks(HTMLParser):
    """Splits an HTML document into blocks of prose text with code spans masked."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._cur: list[str] = []
        self._code: list[str] = []
        self._skip = 0
        # Open block-level UI labels, and whether the current block has text inside one.
        self._labels: list[str] = []
        self._in_label = False
        # Open inline UI labels (a pill inside a row): (tag, text so far), each judged alone.
        self._inline: list[tuple[str, list[str]]] = []

    def _flush(self) -> None:
        text = "".join(self._cur).strip()
        if text:
            self.blocks.append(Label(text) if self._in_label else text)
        self._cur = []
        self._in_label = False

    def _add(self, text: str) -> None:
        self._cur.append(text)
        for _, parts in self._inline:
            parts.append(text)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        classes = (dict(attrs).get("class") or "").split()
        if tag in SKIP_TAGS:
            self._skip += 1
        elif self._code or tag in CODE_TAGS or CODE_CLASS in classes:
            if not self._code:
                self._add(CODE)
            self._code.append(tag)
        else:
            if tag in BLOCKS:
                self._flush()
            elif tag in APART:
                self._add(" ")
            if tag in VOID or not (tag in LABEL_TAGS or LABEL_CLASSES & set(classes)):
                return
            if tag in BLOCKS:
                self._labels.append(tag)
            else:
                self._inline.append((tag, []))

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif self._code:
            if tag in self._code:
                del self._code[len(self._code) - 1 - self._code[::-1].index(tag) :]
        elif tag in BLOCKS:
            self._flush()
            if tag in self._labels:
                del self._labels[
                    len(self._labels) - 1 - self._labels[::-1].index(tag) :
                ]
        else:
            tags = [t for t, _ in self._inline]
            if tag in tags:
                at = len(tags) - 1 - tags[::-1].index(tag)
                text = "".join(self._inline[at][1]).strip()
                del self._inline[at:]
                if text:
                    self.blocks.append(Label(text))
            if tag in APART:
                self._add(" ")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        if tag in BLOCKS and not self._code:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip and not self._code:
            self._add(data)
            self._in_label = self._in_label or bool(self._labels and data.strip())

    def close(self) -> None:
        super().close()
        self._flush()


def html_blocks(page: str) -> list[str]:
    """The prose blocks of one HTML page."""
    parser = _Blocks()
    parser.feed(page)
    parser.close()
    return parser.blocks


FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
AUTOLINK = re.compile(r"<(?:https?://|mailto:)[^>]*>")
MD_NEW_BLOCK = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>\s?|\|)")
MD_HEADING = re.compile(r"^\s*#{1,6}\s")
MD_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
MD_MARKER = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+|>\s?)")


def md_blocks(text: str) -> list[str]:
    """The prose blocks of one Markdown twin: paragraphs, list items, headings, table cells."""
    blocks: list[str] = []
    cur: list[str] = []
    fenced = False
    # An indented code block: four spaces after a blank line, outside a list.
    indented = in_list = False
    blank = True

    def flush() -> None:
        if cur:
            blocks.append(" ".join(cur))
            cur.clear()

    lines = text.splitlines()
    if lines[:1] == ["---"] and "---" in lines[1:]:
        lines = lines[lines.index("---", 1) + 1 :]  # YAML front matter is data
    for line in lines:
        if FENCE.match(line):
            flush()
            fenced = not fenced
            continue
        if fenced:
            continue
        if not line.strip():
            flush()
            blank = True
            continue
        was_blank, blank = blank, False
        if line.startswith("    ") and (indented or (was_blank and not in_list)):
            flush()
            indented = True
            continue
        indented = False
        if was_blank and not line.startswith(" "):
            in_list = bool(MD_LIST.match(line))
        line = INLINE_CODE.sub(CODE, line)
        line = AUTOLINK.sub(CODE, line)
        line = MD_LINK.sub(r"\1", line)
        if line.lstrip().startswith("|"):
            flush()
            for cell in re.split(r"(?<!\\)\|", line.strip().strip("|")):
                if cell.strip() and not re.fullmatch(r"\s*:?-+:?\s*", cell):
                    blocks.append(cell.strip())
            continue
        if MD_NEW_BLOCK.match(line):
            flush()
            if MD_HEADING.match(line):
                blocks.append(Label(MD_MARKER.sub("", line, count=1).strip()))
                continue
            line = MD_MARKER.sub("", line, count=1)
        cur.append(line.strip())
    flush()
    return blocks
