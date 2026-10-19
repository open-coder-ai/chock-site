"""VOICE-2: find the mechanical voice tells (semicolons, colon chains, dash asides, jargon, hedges, boasts) in built HTML."""

import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

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
SKIP_TAGS = frozenset({"script", "style", "template", "noscript", "title", "svg"})
# Abbreviations whose full stop does not end a sentence.
ABBREV = re.compile(r"(?:\b(?:e\.g|i\.e|etc|vs|cf|approx|incl|no)\.)$", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<!\.)[.?!][\"'”’)\]]*\s+")
CODE_SPAN = re.compile(r"`[^`]*`")
# Quoted text is someone else's words (an error message, a vendor's phrase): never judged.
QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|(?<!\w)'[^'\s][^']*'(?!\w)")
LEAD = "\"'“‘([—–-•·*_ "


class Blocks(HTMLParser):
    """Splits a page into blocks of text; code is wrapped in backticks, a classed span or link is its own block."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._cur: list[str] = []
        self._code: list[str] = []
        self._inline: list[tuple[str, bool]] = []
        self._skip = 0

    def flush(self) -> None:
        """End the current block."""
        text = " ".join("".join(self._cur).split())
        if text:
            self.blocks.append(text)
        self._cur = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Open code, a quotation, a block, or a classed span or link (a badge or button)."""
        classes = (dict(attrs).get("class") or "").split()
        if tag in SKIP_TAGS:
            self._skip += 1
        elif self._code or tag in CODE_TAGS or CODE_CLASS in classes:
            if not self._code:
                self._cur.append("`")
            self._code.append(tag)
        elif tag == "q":
            self._cur.append("“")
        elif tag in ("span", "a"):
            self._inline.append((tag, bool(classes)))
            if classes:
                self.flush()
            elif tag == "span":
                self._cur.append(" ")
        elif tag in BLOCKS:
            self.flush()

    def handle_endtag(self, tag: str) -> None:
        """Close what handle_starttag opened."""
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif self._code:
            if tag in self._code:
                del self._code[len(self._code) - 1 - self._code[::-1].index(tag) :]
                if not self._code:
                    self._cur.append("`")
        elif tag == "q":
            self._cur.append("”")
        elif tag in ("span", "a"):
            while self._inline:
                name, classed = self._inline.pop()
                if name == tag:
                    if classed:
                        self.flush()
                    break
        elif tag in BLOCKS:
            self.flush()

    def handle_data(self, data: str) -> None:
        """Keep text outside skipped elements."""
        if not self._skip:
            self._cur.append(data.replace("`", "'"))


def sentences(block: str) -> list[str]:
    """The sentences of one block; a full stop inside a code span never ends one."""
    masked = CODE_SPAN.sub(lambda m: "`" + "x" * (len(m.group()) - 2) + "`", block)
    cuts = [0]
    for m in SENTENCE_END.finditer(masked):
        if not ABBREV.search(masked[: m.start() + 1]):
            cuts.append(m.end())
    parts = [block[a:b] for a, b in zip(cuts, cuts[1:] + [len(block)], strict=True)]
    return [s for s in (p.lstrip(LEAD).strip() for p in parts) if s]


def prose(sentence: str, names: list[str]) -> str:
    """The sentence with code, quotations and allowed names removed."""
    text = QUOTED.sub(" ", CODE_SPAN.sub(" ", sentence))
    for name in names:
        text = text.replace(name, " ")
    return text


def tells(sentence: str, terms: dict) -> list[str]:
    """The mechanical tells one sentence shows; a sentence with under two prose words shows none."""
    text = prose(sentence, terms["names"])
    if len(re.findall(r"[A-Za-z]{2,}", text)) < 2:
        return []
    found = []
    if ";" in text:
        found.append("semicolon")
    if len(re.findall(r":(?=\s)", text)) >= 2:
        found.append("colon-chain")
    if re.search(r"—|\s–\s|\s--\s", text):
        found.append("dash-aside")
    for rule, words in (
        ("jargon", terms["jargon"]),
        ("hedge", terms["hedges"]),
        ("boast", terms["boasts"]),
    ):
        if re.search(r"\b(?:" + "|".join(words) + r")\b", text, re.IGNORECASE):
            found.append(rule)
    return found


def html_sentences(page: str) -> list[str]:
    """Every prose sentence of one HTML page, in page order."""
    parser = Blocks()
    parser.feed(page)
    parser.flush()
    return [s for block in parser.blocks for s in sentences(block)]


def flagged(dist: Path, terms: dict) -> dict[str, tuple[list[str], Counter]]:
    """Each flagged sentence on the built site: its tells and the pages it is on."""
    found: dict[str, tuple[list[str], Counter]] = {}
    for path in sorted(dist.rglob("*.html")):
        page = path.relative_to(dist).as_posix()
        for s in html_sentences(path.read_text(encoding="utf-8")):
            if s in found:
                found[s][1][page] += 1
            elif rules := tells(s, terms):
                found[s] = (rules, Counter({page: 1}))
    return found
