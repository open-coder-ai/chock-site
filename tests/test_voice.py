"""VOICE-2: no site-owned sentence shows a mechanical voice tell; upstream ones are listed by source."""

import pytest
import yaml

from tests.conftest import DATA
from tests.voicecheck import flagged, html_sentences, tells

TERMS = yaml.safe_load((DATA / "voice.yaml").read_text(encoding="utf-8"))
UPSTREAM = {s: row["source"] for row in TERMS["upstream"] for s in row["sentences"]}


@pytest.fixture(scope="module")
def found(built) -> dict:
    """Every flagged sentence on the built site, with its tells and pages."""
    return flagged(built.out, TERMS)


def test_site_owned_sentences_pass(found) -> None:
    """Every sentence the site writes is free of semicolons, colon chains, dash asides, jargon and hedges."""
    bad = sorted(
        f"{min(pages)}: {','.join(rules)}: {s}"
        for s, (rules, pages) in found.items()
        if s not in UPSTREAM
    )
    assert not bad, f"{len(bad)} sentences show a voice tell:\n" + "\n".join(bad[:200])


def test_upstream_list_is_current(found) -> None:
    """Each listed upstream sentence is still flagged on the site, so a fix upstream shortens the list."""
    stale = sorted(f"{src}: {s}" for s, src in UPSTREAM.items() if s not in found)
    assert not stale, "no longer flagged, remove from data/voice.yaml:\n" + "\n".join(
        stale
    )


def test_upstream_entries_are_unique() -> None:
    """A sentence is listed once, under one source."""
    listed = [s for row in TERMS["upstream"] for s in row["sentences"]]
    assert len(listed) == len(set(listed))


def _tells(page: str) -> list[list[str]]:
    return [t for s in html_sentences(page) if (t := tells(s, TERMS))]


@pytest.mark.parametrize(
    "page, expected",
    [
        ("<p>The hook runs; the call passes.</p>", [["semicolon"]]),
        ("<p>Client: the versions: all of them.</p>", [["colon-chain"]]),
        ("<p>Chock blocks it — nothing else.</p>", [["dash-aside"]]),
        ("<p>Flags it -- and moves on.</p>", [["dash-aside"]]),
        ("<p>Most clients fail open on a crash.</p>", [["jargon"]]),
        ("<p>The label on each surface says it.</p>", [["jargon"]]),
        ("<p>A person witnessed the refusal.</p>", [["jargon"]]),
        ("<p>The engine's ledger has rows.</p>", [["jargon"]]),
        ("<p>The plugin route is tested.</p>", [["jargon"]]),
        ("<p>This is honest by design.</p>", [["hedge"]]),
        ("<p>It is deliberately left out.</p>", [["hedge"]]),
        ("<p>Each label says exactly how far a policy goes.</p>", [["boast"]]),
        ("<p>This site is the catalog's front door.</p>", [["boast"]]),
        (
            "<p>Hooks judge each call; the gate re-runs it.</p>",
            [["semicolon", "jargon"]],
        ),
    ],
)
def test_finds_each_tell(page: str, expected: list[list[str]]) -> None:
    """Each mechanical tell is found in prose."""
    assert _tells(page) == expected


@pytest.mark.parametrize(
    "page",
    [
        "<p>Run <code>a; b</code> first.</p>",
        "<pre>chock sync; chock check</pre>",
        '<p>It writes <span class="mono">.chock/compiled/&lt;id&gt;/&lt;surface&gt;/</span>.</p>',
        "<p>Run <kbd>x -- y</kbd> to see it.</p>",
        '<p>Deno says "use a; b" in its docs.</p>',
        "<p>The vendor says <q>it sits where AI is used: browser, endpoint, network.</q></p>",
        "<p>OWASP ASI01 — Agent Goal Hijack</p>",
        "<p>Install method: plugin.</p>",
        "<p>Routes</p>",
        "<p>Tested means a person saw it work in a live run.</p>",
        "<p>If the hook crashes, the action goes through.</p>",
        "<p>Each policy says what it stops and what it misses.</p>",
        "<script>if (a) { b(); } else { c(); }</script>",
    ],
)
def test_ignores_code_quotes_names_and_plain_prose(page: str) -> None:
    """Code, quoted words, standard titles, one-word labels and plain sentences pass."""
    assert _tells(page) == []
