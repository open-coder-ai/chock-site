"""The docs section at /docs/: overview, both quickstarts, agents, policies, configure, monitor, reference."""

import json
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import clientdata, clientpage, docsfacts, docsource, engine
from .docsmd import Renderer, first_code, first_sections, rewrite_links, sections
from .model import Policy, SectionResult, Site
from .pageparts import (
    PageError,
    data_fill,
    install_command,
    policies_sorted,
    write_md,
    write_page,
)
from .render import Prose, Safe, md_code, render_file, render_text_file
from .render import md as md_escape

DOCS = "docs"
MD = "md"
COMMIT_URL = "__REPO__/commit/__REF__"
BLOB_URL = "__REPO__/blob/__REF__/__PATH__"
CATALOG_COMMIT = "https://github.com/open-coder-ai/chock-catalog/commit/"


@dataclass
class Body:
    """One page's content, built as HTML and as its Markdown twin side by side."""

    renderer: Renderer
    html: list[str] = field(default_factory=list)
    md: list[str] = field(default_factory=list)


@dataclass
class Ctx:
    """What every docs page builder reads."""

    site: Site
    templates: Path
    docs: dict[str, Any]
    texts: dict[str, Any]
    prose: dict[str, str | None]
    agents: list[dict[str, Any]]
    cli: list[dict[str, str]]
    page: dict[str, Any] = field(default_factory=dict)

    def t(self, name: str, **tokens: object) -> str:
        """A docs template, filled."""
        return render_file(self.templates / DOCS / f"{name}.html", **tokens)


def _engine_url(ctx: Ctx, path: str = "") -> str:
    """A link into chock at the pinned commit: the commit, or a file in it."""
    subs = {"__REPO__": ctx.docs["engine_repo"], "__REF__": ctx.site.framework_ref}
    if not path:
        return data_fill(COMMIT_URL, subs)
    return data_fill(BLOB_URL, subs | {"__PATH__": path})


def _resolver(ctx: Ctx, source: str):
    """Resolve a link in a chock file: web links kept, repo paths sent to GitHub at the pinned commit."""

    def resolve(href: str) -> str:
        parts = urlsplit(href)
        if parts.scheme in ("http", "https", "mailto"):
            return href
        frag = f"#{parts.fragment}" if parts.fragment else ""
        if not parts.path:
            return _engine_url(ctx, source) + frag
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), parts.path))
        if path.startswith(".."):
            return _engine_url(ctx)
        return _engine_url(ctx, path) + frag

    return resolve


def _section(ctx: Ctx, body: Body, heading: str, html: str, md: str) -> None:
    """An h2 section with its Markdown twin."""
    body.html.append(
        ctx.t(
            "section",
            ID=body.renderer.toc_heading(2, heading),
            HEADING=heading,
            BODY=Safe(html),
        )
    )
    body.md.append(f"## {heading}\n\n{md.rstrip()}\n\n")


def _h3(ctx: Ctx, body: Body, heading: str) -> str:
    return ctx.t("h3", ID=body.renderer.toc_heading(3, heading), HEADING=heading)


def _para(ctx: Ctx, text: str) -> str:
    return ctx.t("para", TEXT=Prose(text))


def _list(ctx: Ctx, items: list[str | Safe]) -> str:
    cells = [ctx.t("li", TEXT=i if isinstance(i, Safe) else Prose(i)) for i in items]
    return ctx.t("list", ITEMS=Safe("".join(cells)))


def _table(ctx: Ctx, head: list[str], rows: list[list[str | Safe]]) -> str:
    """A table whose first cell in each row is the row header."""
    return ctx.t(
        "table",
        HEAD=Safe("".join(ctx.t("th", TEXT=h) for h in head)),
        ROWS=Safe(
            "".join(
                ctx.t(
                    "tr",
                    CELLS=Safe(
                        ctx.t("th-row", TEXT=row[0])
                        + "".join(ctx.t("td", TEXT=cell) for cell in row[1:])
                    ),
                )
                for row in rows
            )
        ),
    )


def _md_table(head: list[str], rows: list[list[str]]) -> str:
    cells = [head, ["---"] * len(head), *rows]
    return "".join(
        "| " + " | ".join(c.replace("|", "\\|") for c in row) + " |\n" for row in cells
    )


def _facts(ctx: Ctx, rows: list[tuple[str, str | Safe]]) -> str:
    return ctx.t(
        "facts",
        ROWS=Safe("".join(ctx.t("fact", KEY=k, VALUE=v) for k, v in rows)),
    )


def _command(ctx: Ctx, command: str) -> str:
    return render_file(ctx.templates / "partials" / "command-pre.html", COMMAND=command)


def _page_href(ctx: Ctx, key: str) -> str:
    return ctx.docs["pages"][key]["path"]


# --- blocks: each appends HTML and Markdown for one part of a page ---------------


def _tab_part(ctx: Ctx, part: str | dict[str, Any]) -> tuple[str, str]:
    """One part of a path's tab: the install command, the pick step, or engine-doc commands."""
    if part == "install":
        cmd = install_command(ctx.site)
        return _command(ctx, cmd), f"    {cmd}\n\n"
    if part == "pick":
        forms = _command_forms(ctx)
        return (
            _para(ctx, ctx.texts["pick_body"])
            + "".join(_command(ctx, f) for f in forms),
            f"{ctx.texts['pick_body']}\n\n" + "".join(f"    {f}\n\n" for f in forms),
        )
    if not isinstance(part, dict):
        raise PageError(f"docs.yaml paths: unknown tab part {part!r}")
    text = ctx.prose[part["file"]]
    if text is None:
        raise PageError(f"docs.yaml paths: {part['file']} is not in the snapshot")
    html, md = [], []
    for title in part["sections"]:
        lang, code = first_code(sections(text, [title]))
        html.append(_code(ctx, code, lang))
        md.append("".join(f"    {line}\n" for line in code.splitlines()) + "\n")
    return "".join(html), "".join(md)


def _path_tabs(ctx: Ctx, body: Body) -> tuple[str, str]:
    """Each path's commands as a tab; without JS the panels stay stacked under their h3."""
    site_url = ctx.site.data["site_url"]
    panels, md = [], []
    for path in ctx.texts["paths"]:
        page = ctx.docs["pages"][path["page"]]
        parts = [_tab_part(ctx, part) for part in path["tab"]]
        link = ctx.t("link", HREF=page["path"], TEXT=page["nav_label"])
        panels.append(
            ctx.t(
                "tab-panel",
                ID=body.renderer.heading_id(path["title"]),
                HEADING=path["title"],
                BODY=Safe(
                    "".join(h for h, _ in parts) + ctx.t("para", TEXT=Safe(link))
                ),
            )
        )
        md.append(
            f"### {path['title']}\n\n{ctx.texts['ask_code']}\n\n"
            + "".join(m for _, m in parts)
            + f"[{page['nav_label']}]({site_url}{page['path']}index.md)\n\n"
        )
    html = ctx.t("tabs", LABEL=ctx.texts["paths_heading"], PANELS=Safe("".join(panels)))
    return html, "".join(md)


def _paths(ctx: Ctx, body: Body) -> None:
    cards = [
        ctx.t(
            "card",
            HREF=_page_href(ctx, p["page"]),
            TITLE=p["title"],
            BODY=p["body"],
        )
        for p in ctx.texts["paths"]
    ]
    md = "".join(
        f"- [{p['title']}]({ctx.site.data['site_url']}{_page_href(ctx, p['page'])}index.md): "
        f"{p['body']}\n"
        for p in ctx.texts["paths"]
    )
    tabs_html, tabs_md = _path_tabs(ctx, body)
    _section(
        ctx,
        body,
        ctx.texts["paths_heading"],
        ctx.t("cards", CARDS=Safe("".join(cards))) + tabs_html,
        f"{md}\n{tabs_md}",
    )


def _labels(ctx: Ctx, body: Body) -> None:
    words = engine.label_words()
    meanings = ctx.site.data["label_meanings"]
    rows = [[word, meanings[word]] for word in words.values()]
    _section(
        ctx,
        body,
        ctx.texts["labels_heading"],
        _para(ctx, ctx.texts["labels_intro"]) + _table(ctx, ["Label", "Meaning"], rows),
        f"{ctx.texts['labels_intro']}\n\n" + _md_table(["Label", "Meaning"], rows),
    )


def _count(values: list[str]) -> list[tuple[str, int]]:
    seen: dict[str, int] = {}
    for value in values:
        seen[value] = seen.get(value, 0) + 1
    return sorted(seen.items())


def _grades(ctx: Ctx, body: Body) -> None:
    grades = [
        data_fill(ctx.texts["grade_row"], {"__GRADE__": g, "__COUNT__": str(n)})
        for g, n in _count([a["grade"] for a in ctx.agents])
    ]
    bases = [
        data_fill(ctx.texts["basis_row"], {"__BASIS__": b, "__COUNT__": str(n)})
        for b, n in _count([a["basis"] for a in ctx.agents])
    ]
    html = (
        _para(ctx, ctx.texts["grades_intro"])
        + _list(ctx, grades)
        + _h3(ctx, body, ctx.texts["basis_heading"])
        + _list(ctx, bases)
    )
    md = (
        f"{ctx.texts['grades_intro']}\n\n"
        + "".join(f"- {g}\n" for g in grades)
        + f"\n### {ctx.texts['basis_heading']}\n\n"
        + "".join(f"- {b}\n" for b in bases)
    )
    _section(ctx, body, ctx.texts["grades_heading"], html, md)


def _witness(ctx: Ctx, body: Body) -> None:
    text = data_fill(
        ctx.texts["witness_body"], {"__COUNT__": str(len(engine.witness_ledger()))}
    )
    _section(ctx, body, ctx.texts["witness_heading"], _para(ctx, text), text)


def _install(ctx: Ctx, body: Body) -> None:
    inst = ctx.site.data["install"]
    cmd = install_command(ctx.site)
    _section(
        ctx,
        body,
        ctx.texts["install_heading"],
        _command(ctx, cmd) + _para(ctx, inst["install_note"]),
        f"    {cmd}\n\n{inst['install_note']}\n",
    )


def _command_forms(ctx: Ctx) -> list[str]:
    clients = ctx.site.data["builder_clients"]
    return [
        data_fill(
            clients["commands"][state], {"__CODE__": "<code>", "__CLIENT__": "<agent>"}
        )
        for state in ("witnessed", "untested")
    ]


def _pick(ctx: Ctx, body: Body) -> None:
    forms = _command_forms(ctx)
    link = ctx.t("link", HREF="/coding/builder/", TEXT=ctx.texts["pick_link"])
    html = (
        _para(ctx, ctx.texts["pick_body"])
        + "".join(_command(ctx, f) for f in forms)
        + ctx.t("para", TEXT=Safe(link))
    )
    md = (
        f"{ctx.texts['pick_body']}\n\n"
        + "".join(f"    {f}\n\n" for f in forms)
        + f"[{ctx.texts['pick_link']}]({ctx.site.data['site_url']}/coding/builder/)\n"
    )
    _section(ctx, body, ctx.texts["pick_heading"], html, md)


def _md_note(ctx: Ctx, text: str) -> str:
    """An engine note for a twin: each sentence naming a chock command opens with the ask."""
    return " ".join(
        f"{ctx.texts['ask_note']} {part}" if "`chock " in part else part
        for part in re.split(r"(?<=[.!?])\s+", text)
    )


def _client_block(
    ctx: Ctx, body: Body, client: str, on_agent_page: bool = False
) -> tuple[str, str]:
    """One plugin client's state, command and engine steps, as HTML and Markdown."""
    clients = ctx.site.data["builder_clients"]
    about = clients["clients"][client]
    state = about["witness"]
    command = data_fill(
        clients["commands"][state], {"__CODE__": "<code>", "__CLIENT__": client}
    )
    word = clients["texts"][state]
    agent = next(
        a["id"] for a in ctx.agents if a["plugin"] and a["plugin"]["client"] == client
    )
    heading = f"{about['name']} ({client})"
    link = (
        ""
        if on_agent_page
        else " "
        + ctx.t(
            "link",
            HREF=f"/docs/agents/{docsfacts.agent_slug(agent)}/",
            TEXT=ctx.texts["agent_page_link"],
        )
    )
    html = [
        _h3(ctx, body, heading),
        ctx.t("para", TEXT=Safe(ctx.t("state", STATE=state, WORD=word) + link)),
    ]
    md = [f"### {heading}\n\n", f"State: {word}.\n\n"]
    if notice := about["evidence"]:
        html.append(
            ctx.t(
                "notice",
                LABEL=notice["label"],
                LINE=notice["line"],
                URL=notice["url"],
                LINK=notice["link"],
            )
        )
        md.append(
            f"{notice['label']} {notice['line']} [{notice['link']}]({notice['url']}).\n\n"
        )
    html += [
        _para(ctx, clients["texts"]["command_md"]),
        _command(ctx, command),
        _para(ctx, about["steps_heading"]),
        clientpage.step_blocks(ctx.templates / "coding", about["steps"]),
    ]
    md.append(
        f"{clients['texts']['command_md']}\n\n    {command}\n\n{about['steps_heading']}\n\n"
    )
    for step in about["steps"]:
        (kind, text), *_ = step.items()
        if kind == "command":
            md.append(f"    {text}\n\n")
        elif kind == "note":
            md.append(f"{_md_note(ctx, text)}\n\n")
        else:
            md.extend(f"    {line}\n" for line in text.splitlines())
            md.append("\n")
    return "".join(html), "".join(md)


def _clients(ctx: Ctx, body: Body) -> None:
    clients = ctx.site.data["builder_clients"]
    html = [_para(ctx, ctx.texts["clients_intro"])]
    md = [f"{ctx.texts['clients_intro']}\n\n"]
    for client in clients["order"]:
        h, m = _client_block(ctx, body, client)
        html.append(h)
        md.append(m)
    _section(ctx, body, ctx.texts["clients_heading"], "".join(html), "".join(md))


def _sync(ctx: Ctx, body: Body) -> None:
    wired = [a for a in ctx.agents if a["sync"]]
    rows = [
        [
            a["name"],
            a["sync"]["agents"],
            a["config"] or "",
            ctx.texts["sync_turn_end"] if a["turn_end"] else "",
            a["sync"]["word"],
        ]
        for a in wired
    ]
    html_rows = [
        [
            Safe(ctx.t("link", HREF=f"/docs/agents/{a['slug']}/", TEXT=a["name"])),
            Safe(ctx.t("code", TEXT=a["sync"]["agents"])),
            Safe(ctx.t("code", TEXT=a["config"] or "")),
            ctx.texts["sync_turn_end"] if a["turn_end"] else "",
            Safe(ctx.t("state", STATE=a["sync"]["witness"], WORD=a["sync"]["word"])),
        ]
        for a in wired
    ]
    cols = ctx.texts["sync_columns"]
    _section(
        ctx,
        body,
        ctx.texts["sync_heading"],
        _para(ctx, ctx.texts["sync_intro"]) + _table(ctx, cols, html_rows),
        f"{ctx.texts['sync_intro']}\n\n" + _md_table(cols, rows),
    )


def _route_words(ctx: Ctx, agent: dict[str, Any]) -> str:
    return ", ".join(ctx.texts["route_words"][r] for r in agent["routes"])


def _agent_table(ctx: Ctx, body: Body) -> None:
    cols = ctx.texts["agent_columns"]
    site_url = ctx.site.data["site_url"]
    rows = [
        [
            Safe(ctx.t("link", HREF=f"/docs/agents/{a['slug']}/", TEXT=a["name"])),
            _route_words(ctx, a),
            a["tier"],
            a["grade"],
            a["basis"],
            a["fail_mode"],
        ]
        for a in ctx.agents
    ]
    md_rows = [
        [
            f"[{a['name']}]({site_url}/docs/agents/{a['slug']}/index.md)",
            _route_words(ctx, a),
            a["tier"],
            a["grade"],
            a["basis"],
            a["fail_mode"],
        ]
        for a in ctx.agents
    ]
    _section(
        ctx,
        body,
        ctx.page["title"],
        _table(ctx, cols, rows),
        _md_table(cols, md_rows),
    )


def _policy_table(ctx: Ctx, body: Body) -> None:
    cols = ctx.texts["policy_columns"]
    site_url = ctx.site.data["site_url"]
    shown = policies_sorted(ctx.site)
    rows = [
        [
            Safe(ctx.t("link", HREF=f"/docs/policies/{p.id}/", TEXT=p.name)),
            p.word,
            p.status or "",
        ]
        for p in shown
    ]
    md_rows = [
        [
            f"[{md_escape(p.name)}]({site_url}/docs/policies/{p.id}/index.md)",
            p.word,
            p.status or "",
        ]
        for p in shown
    ]
    _section(
        ctx, body, ctx.page["title"], _table(ctx, cols, rows), _md_table(cols, md_rows)
    )


def _selection(ctx: Ctx, body: Body) -> None:
    inst = ctx.site.data["install"]
    clients = ctx.site.data["builder_clients"]
    subs = {
        "__SCHEMA__": str(engine.SCHEMA2),
        "__CLIENTS__": ", ".join(clients["order"]),
        "__BUNDLE_VERSION__": clients["bundle_version"],
    }
    rows = [
        [row["field"], data_fill(row["meaning"], subs)] for row in inst["file_fields"]
    ]
    html_rows = [[Safe(ctx.t("code", TEXT=f)), m] for f, m in rows]
    _section(
        ctx,
        body,
        ctx.texts["selection_heading"],
        _para(ctx, inst["file_body"]) + _table(ctx, ["Field", "Meaning"], html_rows),
        f"{inst['file_body']}\n\n"
        + _md_table(["Field", "Meaning"], [[f"`{f}`", m] for f, m in rows]),
    )


def _help_blocks(ctx: Ctx, body: Body, names: list[str]) -> tuple[str, str]:
    by_name = {c["name"]: c for c in ctx.cli}
    html, md = [], []
    for name in names:
        command = by_name.get(name)
        if command is None:
            raise PageError(
                f"docs.yaml names chock {name!r}, which the engine does not have"
            )
        heading = f"chock {name}"
        html += [
            _h3(ctx, body, heading),
            _para(ctx, command["summary"]),
            _code(ctx, command["help"]),
        ]
        md.append(
            f"### {heading}\n\n{command['summary']}\n\n{ctx.texts['ask_code']}\n\n"
            f"```text\n{command['help'].split(chr(10) * 2, 1)[0]}\n```\n\n"
            f"{ctx.texts['help_more']}\n\n"
        )
    return "".join(html), "".join(md)


def _code(ctx: Ctx, text: str, lang: str = "text") -> str:
    return render_file(
        ctx.templates / "partials" / "code-pre.html", LANG=lang, CODE=text
    )


def _toggles(ctx: Ctx, body: Body) -> None:
    html, md = _help_blocks(ctx, body, ctx.texts["toggle_commands"])
    _section(
        ctx,
        body,
        ctx.texts["toggles_heading"],
        _para(ctx, ctx.texts["toggles_intro"]) + html,
        f"{ctx.texts['toggles_intro']}\n\n{md}",
    )


def _log(ctx: Ctx, body: Body) -> None:
    paths = engine.gate_logs()
    help_html, help_md = _help_blocks(ctx, body, ctx.texts["log_commands"])
    _section(
        ctx,
        body,
        ctx.texts["log_heading"],
        _para(ctx, ctx.texts["log_body"])
        + _list(ctx, [Safe(ctx.t("code", TEXT=p)) for p in paths])
        + _para(ctx, ctx.texts["log_status"])
        + help_html,
        f"{ctx.texts['log_body']}\n\n"
        + "".join(f"- `{p}`\n" for p in paths)
        + f"\n{ctx.texts['log_status']}\n\n{help_md}",
    )


def _measured(ctx: Ctx, body: Body) -> None:
    html, md = [], []
    for item in ctx.texts["measured"]:
        html += [_h3(ctx, body, item["heading"]), _para(ctx, item["body"])]
        md.append(f"### {item['heading']}\n\n{item['body']}\n\n")
    _section(ctx, body, ctx.texts["measured_heading"], "".join(html), "".join(md))


def _client_notes(ctx: Ctx, body: Body) -> None:
    clients = ctx.site.data["builder_clients"]
    html, md = [], []
    for client in clients["order"]:
        about = clients["clients"][client]
        notes = [
            text
            for step in about["steps"]
            for kind, text in step.items()
            if kind == "note"
        ]
        if not notes:
            continue
        heading = f"{about['name']} ({client})"
        html += [_h3(ctx, body, heading), *(_para(ctx, n) for n in notes)]
        md.append(
            f"### {heading}\n\n" + "".join(f"{_md_note(ctx, n)}\n\n" for n in notes)
        )
    _section(ctx, body, ctx.texts["client_notes_heading"], "".join(html), "".join(md))


def _cli(ctx: Ctx, body: Body) -> None:
    for group, title in ctx.texts["cli_groups"].items():
        names = [c["name"] for c in ctx.cli if c["group"] == group]
        if not names:
            continue
        html, md = _help_blocks(ctx, body, names)
        _section(ctx, body, title, html, md)
    groups = {c["group"] for c in ctx.cli}
    if missing := groups - set(ctx.texts["cli_groups"]):
        raise PageError(f"docs.yaml cli_groups lacks engine groups {sorted(missing)}")


BLOCKS = {
    "paths": _paths,
    "labels": _labels,
    "grades": _grades,
    "witness": _witness,
    "install": _install,
    "pick": _pick,
    "clients": _clients,
    "sync": _sync,
    "agent_table": _agent_table,
    "policy_table": _policy_table,
    "selection": _selection,
    "toggles": _toggles,
    "log": _log,
    "measured": _measured,
    "client_notes": _client_notes,
    "cli": _cli,
}


def _prose(ctx: Ctx, body: Body, entry: dict[str, Any]) -> None:
    """Quoted sections of a chock file, from the snapshot, with links sent to GitHub."""
    text = ctx.prose[entry["file"]]
    if text is None:
        return
    quoted = (
        first_sections(text, entry["first"])
        if entry.get("first")
        else sections(text, entry["sections"])
    )
    resolve = _resolver(ctx, entry["file"])
    renderer = Renderer(ctx.templates, resolve, callouts=ctx.texts["callouts"])
    renderer.ids = body.renderer.ids
    renderer.toc = body.renderer.toc
    body.html.append(
        ctx.t(
            "prose",
            FROM=ctx.texts["prose_heading"] + ":",
            URL=_engine_url(ctx, entry["file"]),
            FILE=entry["file"],
            BODY=renderer.blocks(quoted),
        )
    )
    body.md.append(
        f"{ctx.texts['prose_heading']}: [{entry['file']}]({_engine_url(ctx, entry['file'])})\n\n"
        + rewrite_links(quoted, resolve, ctx.texts["ask_code"])
        + "\n"
    )


# --- agent and policy pages ------------------------------------------------------


def _yes(ctx: Ctx, value: bool) -> str:
    return ctx.texts["word_yes"] if value else ctx.texts["word_no"]


def _agent_body(ctx: Ctx, body: Body, agent: dict[str, Any]) -> None:
    texts = ctx.texts
    plugin, sync = agent["plugin"], agent["sync"]
    routes = []
    if plugin:
        routes.append(
            data_fill(texts["plugin_route"], {"__CLIENT__": plugin["client"]})
        )
    if sync:
        routes.append(
            data_fill(
                texts["sync_route"],
                {"__COMMAND__": sync["command"], "__CONFIG__": agent["config"] or ""},
            )
        )
    if agent["reason"]:
        routes.append(agent["reason"])
    _section(
        ctx,
        body,
        texts["routes_heading"],
        _list(ctx, routes),
        "".join(f"- {r}\n" for r in routes),
    )
    if note := agent["note"]:
        line = f"{note['text']} ({texts['note_source']}: {note['source']})"
        _section(ctx, body, texts["note_heading"], _para(ctx, line), line)
    # A plugin agent's evidence notice is in its install steps below.
    if (issue := agent["evidence"]) and not plugin:
        html = ctx.t(
            "line-link",
            LINE=texts["evidence_line"],
            URL=issue["url"],
            LINK=issue["link"],
        )
        _section(
            ctx,
            body,
            texts["evidence_heading"],
            html,
            f"{texts['evidence_line']} [{issue['link']}]({issue['url']})",
        )

    if plugin:
        h, m = _client_block(ctx, body, plugin["client"], on_agent_page=True)
        _section(ctx, body, texts["install_steps_heading"], h, m)

    fields = texts["enforcement_fields"]
    rows = [(fields[k], str(agent[k])) for k in fields]
    _section(
        ctx,
        body,
        texts["enforcement_heading"],
        _facts(ctx, rows),
        "".join(f"- {k}: {v}\n" for k, v in rows),
    )

    if agent["events"]:
        cols = texts["events_columns"]
        rows = [
            [e["event"], _yes(ctx, e["block"]), _yes(ctx, e["rewrite"]), e["fail_mode"]]
            for e in agent["events"]
        ]
        html_rows = [[Safe(ctx.t("code", TEXT=r[0])), *r[1:]] for r in rows]
        _section(
            ctx,
            body,
            texts["events_heading"],
            _table(ctx, cols, html_rows),
            _md_table(cols, rows),
        )

    claim = agent["ask"]
    ask = (
        data_fill(
            texts["ask_row"],
            {
                "__VERDICT__": claim["verdict"],
                "__HONOURS__": _yes(ctx, claim["honours"]),
                "__EVIDENCE__": claim["evidence"],
                "__TEST__": claim["test"],
            },
        )
        if claim
        else texts["ask_none"]
    )
    _section(ctx, body, texts["ask_heading"], _para(ctx, ask), ask)

    timeout = agent["timeout"]
    if timeout is None:
        line, html_extra, md_extra = texts["timeout_none"], "", ""
    else:
        line = (
            data_fill(
                texts["timeout_row"],
                {
                    "__SECONDS__": str(timeout["default_seconds"]),
                    "__FIELD__": str(timeout["field"]),
                    "__UNIT__": str(timeout["unit"]),
                },
            )
            if timeout["default_seconds"] is not None
            else texts["timeout_unknown"]
        )
        source = timeout["source"]
        url = source.split(" ", 1)[0]
        html_extra = ctx.t(
            "para",
            TEXT=Safe(
                ctx.t("link", HREF=url, TEXT=texts["timeout_source"])
                if url.startswith("https://")
                else ""
            ),
        )
        md_extra = f"{texts['timeout_source']}: {source}\n"
    _section(
        ctx,
        body,
        texts["timeout_heading"],
        _para(ctx, line) + html_extra,
        f"{line}\n\n{md_extra}",
    )

    lines = []
    if plugin:
        lines.append(
            data_fill(
                texts["plugin_state"],
                {"__CLIENT__": plugin["client"], "__STATE__": plugin["word"]},
            )
        )
    if sync:
        lines.append(data_fill(texts["sync_state"], {"__STATE__": sync["word"]}))
    lines += [
        data_fill(
            texts["ledger_row"],
            {
                "__ROUTE__": row["route"],
                "__SURFACE__": row["surface"],
                "__CLIENT__": row["client"],
                "__DATE__": row["date"],
                "__METHOD__": row["method"],
            },
        )
        for row in agent["ledger"]
    ]
    if not agent["ledger"]:
        lines.append(texts["ledger_none"])
    _section(
        ctx,
        body,
        texts["witness_route_heading"],
        _list(ctx, lines),
        "".join(f"- {line}\n" for line in lines),
    )

    notes = agent["notes"] or texts["limits_none"]
    _section(ctx, body, texts["limits_heading"], _para(ctx, notes), notes)


def _policy_body(ctx: Ctx, body: Body, policy: Policy) -> None:
    texts = ctx.texts
    clients = ctx.site.data["builder_clients"]
    _section(
        ctx,
        body,
        texts["policy_what_heading"],
        _para(ctx, policy.description),
        md_escape(policy.description),
    )
    rows = []
    for client in clients["order"]:
        about = clients["clients"][client]
        label = about["labels"][policy.id]
        graded = label["keyword"] != clients["ungraded"]
        word = (
            ctx.site.label_words["coding"][label["keyword"]]
            if graded
            else clients["texts"]["ungraded_word"]
        )
        rows.append([about["name"], word, label["says"]])
    cols = texts["policy_agent_columns"]
    _section(
        ctx,
        body,
        texts["policy_agents_heading"],
        _table(ctx, cols, rows),
        _md_table(cols, [[md_escape(cell) for cell in row] for row in rows]),
    )
    misses = policy.misses or ctx.site.data["texts"]["misses_empty"]
    _section(
        ctx, body, texts["policy_misses_heading"], _para(ctx, misses), md_escape(misses)
    )
    if policy.examples:
        html, md = [], []
        for example in policy.examples:
            html.append(_para(ctx, f"{example.word}: {example.prompt}"))
            md.append(f"{example.word}: {md_escape(example.prompt)}\n\n")
            if example.command:
                html.append(_command(ctx, example.command))
                md.append(f"{md_code(example.command)}\n\n")
        _section(
            ctx, body, texts["policy_examples_heading"], "".join(html), "".join(md)
        )
    links = [
        (texts["policy_catalog_link"], f"/coding/policies/{policy.id}/"),
        (texts["policy_source_link"], policy.source_url),
    ]
    site_url = ctx.site.data["site_url"]
    _section(
        ctx,
        body,
        texts["policy_links_heading"],
        _list(
            ctx, [Safe(ctx.t("link", HREF=href, TEXT=label)) for label, href in links]
        ),
        "".join(
            f"- [{label}]({site_url + href if href.startswith('/') else href})\n"
            for label, href in links
        ),
    )


# --- page assembly ---------------------------------------------------------------


def _nav(ctx: Ctx, current: str) -> Safe:
    groups = []
    for group in ctx.docs["nav"]:
        items = "".join(
            ctx.t(
                "nav-item",
                HREF=_page_href(ctx, key),
                LABEL=ctx.docs["pages"][key]["nav_label"],
                EXTRA=Safe(' aria-current="page"') if key == current else "",
            )
            for key in group["pages"]
        )
        groups.append(ctx.t("nav-group", TITLE=group["group"], ITEMS=Safe(items)))
    return Safe("".join(groups))


def _order(ctx: Ctx) -> list[str]:
    return [key for group in ctx.docs["nav"] for key in group["pages"]]


def _pager(ctx: Ctx, key: str) -> Safe:
    order = _order(ctx)
    i = order.index(key)
    links = []
    if i > 0:
        prev = ctx.docs["pages"][order[i - 1]]
        links.append(
            ctx.t(
                "pager-link",
                DIR="prev",
                HREF=prev["path"],
                WORD=ctx.texts["previous"],
                LABEL=prev["nav_label"],
            )
        )
    if i + 1 < len(order):
        nxt = ctx.docs["pages"][order[i + 1]]
        links.append(
            ctx.t(
                "pager-link",
                DIR="next",
                HREF=nxt["path"],
                WORD=ctx.texts["next"],
                LABEL=nxt["nav_label"],
            )
        )
    return Safe(ctx.t("pager", LINKS=Safe("".join(links)))) if links else Safe("")


def _built(ctx: Ctx) -> tuple[Safe, str]:
    """The footer line naming the engine and catalog commits, linked, and its Markdown."""
    engine_ref = ctx.site.framework_ref
    catalog_ref = ctx.site.catalog_ref
    html = ctx.t(
        "built",
        ENGINE_WORD=ctx.texts["built_engine"],
        ENGINE=Safe(ctx.t("code-link", HREF=_engine_url(ctx), TEXT=engine_ref[:12])),
        CATALOG_WORD=ctx.texts["built_catalog"],
        CATALOG=Safe(
            ctx.t("code-link", HREF=CATALOG_COMMIT + catalog_ref, TEXT=catalog_ref[:12])
        ),
    )
    md = (
        f"{ctx.texts['built_engine']} [{engine_ref[:12]}]({_engine_url(ctx)}) "
        f"{ctx.texts['built_catalog']} [{catalog_ref[:12]}]({CATALOG_COMMIT}{catalog_ref})."
    )
    return Safe(html), md


def _toc(ctx: Ctx, body: Body, html: str) -> Safe:
    """The "On this page" list: the page's h2 and h3 in document order; empty under two."""
    found = sorted(body.renderer.toc, key=lambda h: html.index(f'id="{h[1]}"'))
    if len(found) < 2:
        return Safe("")
    items = "".join(
        ctx.t("toc-item", LEVEL=str(level), HREF=f"#{id_}", TEXT=text)
        for level, id_, text in found
    )
    return Safe(ctx.t("toc", TITLE=ctx.texts["on_this_page"], ITEMS=Safe(items)))


def _write(
    ctx: Ctx,
    out_dir: Path,
    *,
    key: str,
    path: str,
    title: str,
    description: str,
    intro: str,
    crumb: str,
    body: Body,
) -> tuple[str, str]:
    """One docs page and its Markdown twin; returns the page path and the twin text."""
    built_html, built_md = _built(ctx)
    html = "".join(body.html)
    content = ctx.t(
        "layout",
        NAV=_nav(ctx, key),
        TOC=_toc(ctx, body, html),
        COPY=ctx.texts["copy"],
        CRUMB=crumb,
        TITLE=title,
        SUB=Prose(description),
        INTRO=Prose(intro),
        BODY=Safe(html),
        PAGER=_pager(ctx, key) if path == _page_href(ctx, key) else Safe(""),
        BUILT=built_html,
    )
    write_page(
        ctx.site,
        out_dir,
        ctx.templates,
        path=path,
        title=title,
        description=description,
        content=Safe(content),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "name": title,
            "description": description,
            "isPartOf": {
                "@type": "WebSite",
                "url": ctx.site.data["site_url"] + "/docs/",
            },
        },
        nav=DOCS,
        scripts=("common.js", "docs.js"),
    )
    twin = render_text_file(
        ctx.templates / MD / DOCS / "page.md",
        TITLE=md_escape(title),
        SUB=md_escape(description),
        INTRO=md_escape(intro),
        ASK=ctx.texts["ask_first"],
        BODY="".join(body.md),
        BUILT=built_md,
    )
    write_md(out_dir, path, twin)
    return path, twin


def _new_body(ctx: Ctx) -> Body:
    body = Body(
        Renderer(ctx.templates, lambda href: href, callouts=ctx.texts["callouts"])
    )
    body.renderer.ids.add("top")
    return body


def build(site: Site, out_dir: Path, templates: Path, data_dir: Path) -> SectionResult:
    """Every docs page, its twin, /api/docs/index.json and the llms.txt block."""
    docs = docsource.load_docs(data_dir)
    if [k for g in docs["nav"] for k in g["pages"]] != list(docs["pages"]):
        raise PageError("docs.yaml: nav must name every page once, in pages order")
    ctx = Ctx(
        site=site,
        templates=templates,
        docs=docs,
        texts=docs["texts"],
        prose=docsource.load(data_dir, site.framework_ref),
        agents=docsfacts.agents(docs, site.data["agent_routes"]),
        cli=engine.cli_commands(),
    )
    written: list[tuple[str, str, str]] = []

    def emit(
        key: str,
        path: str,
        title: str,
        description: str,
        intro: str,
        crumb: str,
        body: Body,
    ) -> None:
        page_path, twin = _write(
            ctx,
            out_dir,
            key=key,
            path=path,
            title=title,
            description=description,
            intro=intro,
            crumb=crumb,
            body=body,
        )
        written.append((page_path, title, twin))

    for key, page in docs["pages"].items():
        ctx.page = page
        body = _new_body(ctx)
        for block in page["blocks"]:
            if block not in BLOCKS:
                raise PageError(f"docs.yaml {key}: unknown block {block!r}")
            BLOCKS[block](ctx, body)
        for entry in page["prose"]:
            _prose(ctx, body, entry)
        group = next(g["group"] for g in docs["nav"] if key in g["pages"])
        emit(
            key,
            page["path"],
            page["title"],
            page["description"],
            page["intro"],
            group,
            body,
        )

    agents_page = docs["pages"]["agents"]
    for agent in ctx.agents:
        body = _new_body(ctx)
        _agent_body(ctx, body, agent)
        emit(
            "agents",
            f"{agents_page['path']}{agent['slug']}/",
            agent["name"],
            data_fill(ctx.texts["agent_description"], {"__NAME__": agent["name"]}),
            data_fill(
                ctx.texts["agent_intro"],
                {
                    "__ROUTES__": _route_words(ctx, agent),
                    "__TIER__": agent["tier"],
                    "__GRADE__": agent["grade"],
                },
            ),
            agents_page["title"],
            body,
        )

    policies_page = docs["pages"]["policies"]
    reference = site.data["builder_clients"]["clients"][clientdata.ENGINE_CLIENT][
        "name"
    ]
    for policy in policies_sorted(site):
        body = _new_body(ctx)
        _policy_body(ctx, body, policy)
        emit(
            "policies",
            f"{policies_page['path']}{policy.id}/",
            policy.name,
            data_fill(ctx.texts["policy_description"], {"__NAME__": policy.name}),
            data_fill(
                ctx.texts["policy_intro"],
                {
                    "__AGENT__": reference,
                    "__ID__": policy.id,
                    "__VERSION__": policy.version,
                    "__WORD__": policy.word,
                },
            ),
            policies_page["title"],
            body,
        )

    _api(ctx, out_dir, written)
    llms = "".join(
        f"- [Docs: {p['nav_label']}]({p['path']}index.md): {p['description']}\n"
        for p in docs["pages"].values()
    )
    llms += "".join(
        f"- [Docs: {md_escape(title)}]({path}index.md)\n"
        for path, title, _ in written
        if path not in {p["path"] for p in docs["pages"].values()}
    )
    return SectionResult(
        pages=[p for p, _, _ in written],
        llms=llms,
        docs=[(f"{p}index.md", twin) for p, _, twin in written],
        data_lines=(
            "- [/api/docs/index.json](/api/docs/index.json): every docs page, "
            "and each agent's routes, grade and witness rows\n"
        ),
    )


def _api(ctx: Ctx, out_dir: Path, written: list[tuple[str, str, str]]) -> None:
    """/api/docs/index.json: the docs pages and the per-agent facts they show."""
    api = out_dir / "api" / DOCS
    api.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "engine": ctx.site.framework_ref,
        "catalog": ctx.site.catalog_ref,
        "pages": [{"path": p, "md": f"{p}index.md", "title": t} for p, t, _ in written],
        "agents": [{k: v for k, v in a.items() if k != "notes"} for a in ctx.agents],
    }
    (api / "index.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
