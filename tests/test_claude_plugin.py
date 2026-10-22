"""CC-4: the builder and install pages offer the Claude Code plugin exactly where chock does."""

import html
import json
import re
from pathlib import Path

import chock.install.claude_plugin as chock_offer

from sitegen import engine

HEADING = "Use the Claude Code plugin"
TILDE_QUOTED = re.compile(r"'(~[^']*)'")


def _site(built) -> dict:
    return json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))


def _chock_offers() -> list[str]:
    """The install clients chock's own data and agentseam's witness offer the Claude build to."""
    return [
        client
        for client in chock_offer.settings()["clients"]
        if chock_offer.routes(client)
    ]


def _agent_sections(html: str) -> dict[str, str]:
    """Each install-page agent section's HTML, keyed by client id."""
    return dict(
        re.findall(
            r'<section class="install-agent" aria-labelledby="agent-([\w-]+)">(.*?)</section>',
            html,
            re.DOTALL,
        )
    )


def _builder_panels(html: str) -> dict[str, str]:
    """Each builder steps panel's HTML, keyed by client id."""
    return dict(
        re.findall(
            r'<div class="client-steps" data-client="([\w-]+)"[^>]*>(.*?)\n</div>\n(?=<div class="client-steps"|</div>)',
            html,
            re.DOTALL,
        )
    )


def test_site_offers_match_chock(built) -> None:
    """site.json lists the option for exactly the clients chock offers it to."""
    clients = _site(built)["builder_clients"]["clients"]
    shown = [
        c
        for c, about in clients.items()
        if (about["claude_plugin"] or {}).get("routes")
    ]
    assert sorted(shown) == sorted(_chock_offers())
    assert shown, "chock offers the Claude Code plugin to no client: check the pin"


def test_install_page_shows_the_option_where_chock_offers_it(built) -> None:
    """The install page's heading appears in each offered agent's section and nowhere else."""
    sections = _agent_sections(
        (built.out / "coding" / "install" / "index.html").read_text(encoding="utf-8")
    )
    assert sorted(c for c, html in sections.items() if HEADING in html) == sorted(
        _chock_offers()
    )


def test_builder_shows_the_option_where_chock_offers_it(built) -> None:
    """The builder's per-agent steps panel carries the option for exactly chock's offers."""
    panels = _builder_panels(
        (built.out / "coding" / "builder" / "index.html").read_text(encoding="utf-8")
    )
    assert sorted(panels) == sorted(engine.client_ids())
    assert sorted(c for c, html in panels.items() if HEADING in html) == sorted(
        _chock_offers()
    )


def test_labels_and_warnings_are_chocks(built) -> None:
    """Every route keeps chock's where, label and native advice; the warnings are chock's."""
    data = chock_offer.settings()
    clients = _site(built)["builder_clients"]["clients"]
    for client in _chock_offers():
        offer = clients[client]["claude_plugin"]
        assert offer["heading"] == data["heading"]
        assert offer["warnings"] == data["warnings"]
        want = [
            (r["where"], r["label"], r.get("prefer_native"))
            for r in chock_offer.routes(client)
        ]
        assert [
            (r["where"], r["label"], r["prefer_native"]) for r in offer["routes"]
        ] == want


def test_twin_carries_every_line_chock_prints(built) -> None:
    """Each line `chock install` prints about the Claude build appears in the install twin."""
    ask = _site(built)["builder_clients"]["texts"]["ask_inline"]
    twin = (built.out / "coding" / "install" / "index.md").read_text(encoding="utf-8")
    twin = twin.replace(ask, "")
    sections = dict(
        re.findall(
            r"^### .*?\(`([\w-]+)`, \w+\)\n(.*?)(?=^### |\Z)",
            twin,
            re.MULTILINE | re.DOTALL,
        )
    )
    code = _site(built)["builder_clients"]["texts"]["code_placeholder"]
    filled = engine.claude_plugin_tokens() | {"__SELECTION__": f"`{code}`"}
    for client in _chock_offers():
        body = sections[client]
        for line in chock_offer.lines(client, filled):
            # The site leaves a leading ~ unquoted for the shell to expand (engine._shell_line).
            text = TILDE_QUOTED.sub(r"\1", line.strip().removeprefix("warning: "))
            assert text in body, f"{client}: {text!r} not in the install twin"


def test_cursor_gets_no_option_only_chocks_caveat(built) -> None:
    """Cursor is never offered the build; the page shows chock's own reason instead."""
    reason = chock_offer.settings()["clients"]["cursor"]["not_offered"]
    about = _site(built)["builder_clients"]["clients"]["cursor"]
    assert about["claude_plugin"] == {"not_offered": reason}
    section = _agent_sections(
        (built.out / "coding" / "install" / "index.html").read_text(encoding="utf-8")
    )["cursor"]
    assert HEADING not in section
    assert "Not offered for Cursor:" in section


def test_clients_chock_is_silent_on_show_nothing(built) -> None:
    """A client chock neither offers nor explains gets no block at all."""
    data = chock_offer.settings()
    silent = [
        c
        for c in engine.client_ids()
        if not chock_offer.routes(c) and "not_offered" not in data["clients"].get(c, {})
    ]
    sections = _agent_sections(
        (built.out / "coding" / "install" / "index.html").read_text(encoding="utf-8")
    )
    assert silent
    for client in silent:
        assert (
            _site(built)["builder_clients"]["clients"][client]["claude_plugin"] is None
        )
        assert 'class="claude-plugin"' not in sections[client]


def test_no_page_shows_an_ellipsis_for_the_selection_code(built) -> None:
    """Without a selection, the build line shows the site's placeholder, never a literal "…"."""
    code = _site(built)["builder_clients"]["texts"]["code_placeholder"]
    for page in ("install", "builder"):
        for name in ("index.html", "index.md"):
            text = (built.out / "coding" / page / name).read_text(encoding="utf-8")
            builds = [
                line for line in text.splitlines() if "Build it: chock install" in line
            ]
            assert builds, (page, name)
            for line in builds:
                assert "…" not in line, (page, name, line)
                assert code in line or "&lt;code&gt;" in line, (page, name, line)


def _command_lines(path: Path) -> list[str]:
    """Every command line on one page: shell code blocks and inline `chock` code, comments left out."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".html":
        blocks = [
            html.unescape(b)
            for b in re.findall(
                r'<code class="language-(?:bash|sh|shell)">(.*?)</code>',
                text,
                re.DOTALL,
            )
        ]
        blocks += [
            html.unescape(b)
            for b in re.findall(r"<code[^>]*>(chock [^<]*)</code>", text)
        ]
    else:
        blocks = re.findall(r"```(?:bash|sh|shell)\n(.*?)```", text, re.DOTALL)
        blocks += [
            line.strip() for line in text.splitlines() if line.startswith("    chock ")
        ]
        blocks += re.findall(r"`(chock [^`]*)`", text)
    return [
        line
        for block in blocks
        for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_no_command_block_on_any_page_shows_an_ellipsis(built) -> None:
    """No command a page shows, in HTML or its Markdown twin, has a literal "…" in it."""
    pages = [p for p in built.out.rglob("*") if p.suffix in (".html", ".md")]
    checked = 0
    for path in pages:
        for line in _command_lines(path):
            checked += 1
            assert "…" not in line, (str(path.relative_to(built.out)), line)
    assert checked > 100


def test_install_commands_show_the_placeholder_and_link_the_builder(built) -> None:
    """Each agent's command on the install page names the placeholder and links the builder."""
    data = _site(built)["builder_clients"]
    code = data["texts"]["code_placeholder"]
    hint = data["texts"]["code_hint"].replace("__CODE__", code)
    link = data["texts"]["code_hint_link"]
    page = (built.out / "coding" / "install" / "index.html").read_text(encoding="utf-8")
    twin = (built.out / "coding" / "install" / "index.md").read_text(encoding="utf-8")
    sections = _agent_sections(page)
    for client in engine.client_ids():
        assert (
            f"--selection {html.escape(code)} --client {client}" in sections[client]
        ), client
        assert (
            f'<a href="/coding/builder/#client={client}">{link}</a>' in sections[client]
        ), client
        assert f"--selection {code} --client {client}" in twin, client
        assert f"{hint} [{link}](/coding/builder/#client={client})." in twin, client
