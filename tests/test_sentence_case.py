"""SITE-CAPS: no sentence on the built site starts with a lowercase letter, unless it is code."""

import json

import pytest
import yaml

from tests.conftest import DATA
from tests.sentence_case import html_blocks, lowercase_starts, md_blocks

RULES = yaml.safe_load((DATA / "sentence-case.yaml").read_text(encoding="utf-8"))
UPSTREAM = [
    (start, row["source"]) for row in RULES["upstream"] for start in row["starts"]
]


def _names(built) -> frozenset[str]:
    """Names that keep their lowercase spelling: the data list and every policy id."""
    site = json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))
    return frozenset(RULES["names"]) | {p["id"] for p in site["policies"]}


def _findings(built) -> list[tuple[str, str]]:
    """(page, sentence) for every lowercase sentence start in the HTML pages and Markdown twins."""
    names = _names(built)
    found = []
    for path in sorted(built.out.rglob("*")):
        if path.suffix == ".html":
            blocks = html_blocks(path.read_text(encoding="utf-8"))
        elif path.suffix == ".md":
            blocks = md_blocks(path.read_text(encoding="utf-8"))
        else:
            continue
        page = path.relative_to(built.out).as_posix()
        found += [(page, s) for block in blocks for s in lowercase_starts(block, names)]
    return found


def _upstream(sentence: str) -> bool:
    return any(sentence.startswith(start) for start, _ in UPSTREAM)


def test_site_owned_sentences_start_uppercase(built) -> None:
    """Every sentence the site writes starts with a capital letter or with code."""
    bad = sorted({(p, s) for p, s in _findings(built) if not _upstream(s)})
    assert not bad, f"{len(bad)} sentences start lowercase:\n" + "\n".join(
        f"{p}: {s}" for p, s in bad[:200]
    )


def test_upstream_list_is_current(built) -> None:
    """Each listed upstream sentence still appears, so a fix upstream shortens the list."""
    found = [s for _, s in _findings(built)]
    stale = [
        f"{source}: {start}"
        for start, source in UPSTREAM
        if not any(s.startswith(start) for s in found)
    ]
    assert not stale, (
        "no longer on the site, remove from data/sentence-case.yaml:\n"
        + "\n".join(stale)
    )


@pytest.mark.parametrize(
    "page, expected",
    [
        ("<p>chock does not ask a model.</p>", ["chock does not ask a model."]),
        ("<p>Friction. chock stops mistakes.</p>", ["chock stops mistakes."]),
        ("<li>not graded yet for Grok</li>", ["not graded yet for Grok"]),
        ("<td>Done? then run it.</td>", ["then run it."]),
        ("<h2>three steps</h2>", ["three steps"]),
        ("<p>Run it.</p><p>then stop.</p>", ["then stop."]),
    ],
)
def test_finds_lowercase_sentence(page: str, expected: list[str]) -> None:
    """A lowercase word that starts a paragraph, item, cell, heading or sentence is found."""
    found = [s for b in html_blocks(page) for s in lowercase_starts(b)]
    assert found == expected


@pytest.mark.parametrize(
    "page",
    [
        "<p>Run <code>chock install</code> first.</p>",
        "<p><code>chock install</code> builds the plugin.</p>",
        "<pre>chock sync\nchock check</pre>",
        "<p>Done. <kbd>ctrl c</kbd> stops it.</p>",
        "<p>See chock.sh for more.</p>",
        "<p>chock.sh serves the pages.</p>",
        "<p>https://github.com/open-coder-ai is the org.</p>",
        "<p>Install it, then chock blocks the action.</p>",
        "<p>Each label, e.g. blocks or warns, is shown.</p>",
        "<td>yes</td>",
        '<p><a class="mono" href="/x/">block-no-verify</a> refuses it.</p>',
        "<p>block-no-verify refuses it.</p>",
        "<p>goose runs the hooks.</p>",
        "<title>chock install · chock.sh</title>",
        "<script>if (a) { b(); } else { c(); }</script>",
        "<p>Policies <span>Keeps</span> it.</p>",
    ],
)
def test_ignores_code_urls_names_and_mid_sentence(page: str) -> None:
    """Code, URLs, domains, policy ids, names, one-word values and mid-sentence words pass."""
    names = frozenset({"block-no-verify", "goose"})
    assert [s for b in html_blocks(page) for s in lowercase_starts(b, names)] == []


@pytest.mark.parametrize(
    "page, expected",
    [
        ('<td><span class="docs-state">untested</span></td>', ["untested"]),
        ('<p class="stat-label">presets</p>', ["presets"]),
        ('<p class="docs-nav-group">agentseam</p>', ["agentseam"]),
        ('<span class="chip">blocks</span>', ["blocks"]),
        ('<div class="pill"><p>tested</p></div>', ["tested"]),
        ("<h3>run</h3>", ["run"]),
        ("<dt>sha256</dt>", ["sha256"]),
        ("<button>copy</button>", ["copy"]),
        (
            '<li>Claude Code <span class="client-state">untested</span></li>',
            ["untested"],
        ),
    ],
)
def test_finds_lowercase_one_word_label(page: str, expected: list[str]) -> None:
    """SITE-CAPS-2: a one-word heading, button, fact term, badge, pill, chip or label is judged."""
    assert [s for b in html_blocks(page) for s in lowercase_starts(b)] == expected


@pytest.mark.parametrize(
    "page",
    [
        '<td><span class="docs-state">Untested</span></td>',
        "<h3><code>run</code></h3>",
        "<dt><code>sha256</code></dt>",
        "<h1>goose</h1>",
        "<td>yes</td><td>string</td>",
        "<dl><dt>Engine</dt><dd>open</dd></dl>",
        "<th>dco</th>",
        '<p class="stat-label">Policies</p><p>presets</p>',
        '<td><span class="docs-state">Tested</span></td><td>yes</td>',
        '<li>Claude Code <span class="client-state">Tested</span></li>',
        '<p class="docs-nav-group">Guides</p><ul><li>overview</li></ul>',
    ],
)
def test_ignores_one_word_data_values(page: str) -> None:
    """One-word data values (cells, fact values), code labels and names stay unjudged."""
    names = frozenset({"goose"})
    assert [s for b in html_blocks(page) for s in lowercase_starts(b, names)] == []


def test_markdown_twin_blocks() -> None:
    """Markdown: fenced code and backticks are skipped; items, headings and cells are judged."""
    text = (
        "---\nlabel: blocks\n---\n\n# chock.sh\n\nchock blocks it. `chock install` builds it.\n\n"
        "```bash\nchock sync\n```\n\n- not graded yet\n- `pre_tool` runs first\n\n"
        "| Agent | State |\n|---|---|\n| Claude Code | not graded |\n"
        "| Flags | Use a \\| b in one cell |\n\n"
        "A paragraph that wraps\nonto a second line.\n\n    pip install chock\n\n"
        "- an item\n\n    with a lowercase second paragraph\n"
    )
    found = [s for b in md_blocks(text) for s in lowercase_starts(b)]
    assert found == [
        "chock blocks it.",
        "not graded yet",
        "not graded",
        "an item",
        "with a lowercase second paragraph",
    ]


def test_markdown_one_word_heading() -> None:
    """SITE-CAPS-2: a one-word Markdown heading is judged; as code, or a cell, it is not."""
    text = "### run\n\n### `handle`\n\n## Dispatch\n\n| Field | Type |\n|---|---|\n| `a` | string |\n"
    assert [s for b in md_blocks(text) for s in lowercase_starts(b)] == ["run"]
