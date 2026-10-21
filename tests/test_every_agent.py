"""BV-S1b: no page or Markdown twin speaks of schema 1 or of Claude Code as the only agent."""

import json
import re
from dataclasses import replace
from html import escape
from pathlib import Path

from sitegen.clientpage import agent_note
from sitegen.pageparts import status_badge

STALE = ("schema 1", "builds for claude code", "claude code refuses")


def _pages(built):
    """Every rendered page, Markdown twin and llms text file."""
    return [
        path
        for path in sorted(built.out.rglob("*"))
        if path.suffix in (".html", ".md", ".txt")
    ]


def test_no_page_or_twin_has_stale_claude_only_text(built) -> None:
    pages = _pages(built)
    assert any(p.suffix == ".md" for p in pages)
    for path in pages:
        text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower())
        for phrase in STALE:
            assert phrase not in text, f"{path.relative_to(built.out)}: {phrase!r}"


def test_install_page_lists_every_agent_from_builder_clients(built) -> None:
    site = json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))
    block = site["builder_clients"]
    html = (built.out / "coding" / "install" / "index.html").read_text("utf-8")
    twin = (built.out / "coding" / "install" / "index.md").read_text("utf-8")
    for client in block["order"]:
        about = block["clients"][client]
        assert f'id="agent-{client}"' in html
        assert f"--client {client}" in html and f"--client {client}" in twin
        for step in about["steps"]:
            ((kind, text),) = step.items()
            if kind == "note":
                text = agent_note(text, block["texts"]["ask_inline"])
            assert text.splitlines()[0] in twin, (client, text)
        for step in about["remove"]:
            (text,) = step.values()
            assert text.splitlines()[0] in twin, (client, text)
    assert "schema</code></th><td>2, " in html.replace("\n", "")
    assert ".claude" not in html.split('id="each-agent"')[0]


def test_agents_page_builds_for_every_agent(built) -> None:
    site = json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))
    block = site["builder_clients"]
    html = (built.out / "coding" / "clients" / "index.html").read_text("utf-8")
    for client in block["order"]:
        about = block["clients"][client]
        assert f'href="/coding/builder/#client={client}"' in html
        assert f"<code>--client {client}</code>" in html
        for step in about["steps"]:
            ((kind, text),) = step.items()
            if kind == "command":
                assert escape(text) in html, (client, text)
        assert f"state-{about['witness']}" in html


def test_policy_page_links_each_agent_to_the_builder(built) -> None:
    html = (
        built.out / "coding" / "policies" / "block-no-verify" / "index.html"
    ).read_text("utf-8")
    assert 'href="/coding/clients/"' not in html.split("<main")[1].split("</main>")[0]
    for client in ("cursor", "codex", "copilot", "devin"):
        assert f'href="/coding/builder/#client={client}&amp;p=block-no-verify"' in html


def test_policies_page_counts_the_hidden_policy(built) -> None:
    html = (built.out / "coding" / "policies" / "index.html").read_text("utf-8")
    assert "for AI coding agents" in html
    assert "rtk-dangerous-actions-blocker" in html
    assert "deprecated and not shown here" in html


def test_status_badge_only_for_deprecated(built) -> None:
    """BV-C3: a badge only for deprecated; draft, production or a missing key show nothing."""
    templates = Path(__file__).resolve().parents[1] / "templates"
    policy = built.site.policies[0]
    for status, shown in (
        ("deprecated", True),
        ("draft", False),
        ("production", False),
        (None, False),
    ):
        badge = str(status_badge(built.site, templates, replace(policy, status=status)))
        assert ("DEPRECATED" in badge) is shown, status


def test_no_generated_file_links_a_plugin_repo(built) -> None:
    """The five chock-<client>-plugins repos are retired: plugins come from the builder (RP-3)."""
    retired = re.compile(r"chock-[a-z-]+-plugins", re.IGNORECASE)
    files = [
        p for p in built.out.rglob("*") if p.suffix in (".html", ".md", ".txt", ".json")
    ]
    assert files
    found = sorted(
        str(p.relative_to(built.out))
        for p in files
        if retired.search(p.read_text(encoding="utf-8"))
    )
    assert found == []
