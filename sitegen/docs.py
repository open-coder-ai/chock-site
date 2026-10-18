"""The docs section at /docs/: overview, both quickstarts, agents, policies, configure, monitor, reference."""

import datetime as dt
import hashlib
import json
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import yaml

from . import (
    architecture,
    clientdata,
    clientpage,
    cliexamples,
    docsfacts,
    docsource,
    engine,
    vendorquotes,
)
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
from .render import (
    Prose,
    Safe,
    md_code,
    render_file,
    render_text_file,
    sentence_start,
)
from .render import md as md_escape

DOCS = "docs"
MD = "md"
ACTIONS_YAML = "page_actions.yaml"
LANDSCAPE_YAML = "landscape.yaml"
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
    actions: dict[str, Any] = field(default_factory=dict)
    landscape: dict[str, Any] = field(default_factory=dict)
    today: dt.date = field(default_factory=lambda: dt.datetime.now(dt.UTC).date())
    data_dir: Path = architecture.DATA
    cli_tree: list[dict[str, Any]] = field(default_factory=list)
    cli_examples: dict[str, dict[str, Any]] = field(default_factory=dict)

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
            HEADING=Prose(heading),
            BODY=Safe(html),
        )
    )
    body.md.append(f"## {heading}\n\n{md.rstrip()}\n\n")


def _h3(ctx: Ctx, body: Body, heading: str) -> str:
    return ctx.t("h3", ID=body.renderer.toc_heading(3, heading), HEADING=Prose(heading))


def _para(ctx: Ctx, text: str) -> str:
    return ctx.t("para", TEXT=Prose(text))


def _list(ctx: Ctx, items: list[str | Safe]) -> str:
    cells = [ctx.t("li", TEXT=i if isinstance(i, Safe) else Prose(i)) for i in items]
    return ctx.t("list", ITEMS=Safe("".join(cells)))


def _table(ctx: Ctx, head: list[str], rows: list[list[str | Safe]]) -> str:
    """A table whose first cell in each row is the row header."""
    return ctx.t(
        "table",
        COLUMNS=", ".join(head),
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
        sentence_start(
            data_fill(ctx.texts["grade_row"], {"__GRADE__": g, "__COUNT__": str(n)})
        )
        for g, n in _count([a["grade"] for a in ctx.agents])
    ]
    bases = [
        sentence_start(
            data_fill(ctx.texts["basis_row"], {"__BASIS__": b, "__COUNT__": str(n)})
        )
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
        ctx.t(
            "para",
            TEXT=Safe(ctx.t("state", STATE=state, WORD=sentence_start(word)) + link),
        ),
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
            sentence_start(a["sync"]["word"]),
        ]
        for a in wired
    ]
    html_rows = [
        [
            Safe(ctx.t("link", HREF=f"/docs/agents/{a['slug']}/", TEXT=a["name"])),
            Safe(ctx.t("code", TEXT=a["sync"]["agents"])),
            Safe(ctx.t("code", TEXT=a["config"] or "")),
            ctx.texts["sync_turn_end"] if a["turn_end"] else "",
            Safe(
                ctx.t(
                    "state",
                    STATE=a["sync"]["witness"],
                    WORD=sentence_start(a["sync"]["word"]),
                )
            ),
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
            sentence_start(_route_words(ctx, a)),
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
            sentence_start(_route_words(ctx, a)),
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
        parent, _, sub = name.partition(" ")
        command = by_name.get(parent)
        if command is None:
            raise PageError(
                f"docs.yaml names chock {name!r}, which the engine does not have"
            )
        if sub:
            command = command | {"help": engine.subcommand_help(parent, sub)}
        heading = md_code(f"chock {name}")
        summary = sentence_start(command["summary"])
        html += [
            _h3(ctx, body, heading),
            _para(ctx, summary),
            _code(ctx, command["help"]),
        ]
        md.append(
            f"### {heading}\n\n{summary}\n\n{ctx.texts['ask_code']}\n\n"
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
    files = engine.gate_logs()
    routes = ctx.texts["log_routes"]
    if set(files) != set(routes):
        raise PageError(f"docs.yaml log_routes must name the routes {sorted(files)}")
    help_html, help_md = _help_blocks(ctx, body, ctx.texts["log_commands"])
    items: list[str | Safe] = [
        Safe(
            ctx.t(
                "route-files",
                ROUTE=Prose(routes[route]),
                FILES=Safe(", ".join(ctx.t("code", TEXT=p) for p in paths)),
            )
        )
        for route, paths in files.items()
    ]
    _section(
        ctx,
        body,
        ctx.texts["log_heading"],
        _para(ctx, ctx.texts["log_body"])
        + _list(ctx, items)
        + _para(ctx, ctx.texts["log_status"])
        + help_html,
        f"{ctx.texts['log_body']}\n\n"
        + "".join(
            f"- {routes[route]}: " + ", ".join(f"`{p}`" for p in paths) + "\n"
            for route, paths in files.items()
        )
        + f"\n{ctx.texts['log_status']}\n\n{help_md}",
    )


def _summary(ctx: Ctx, body: Body) -> None:
    command = ctx.texts["summary_command"]
    _section(
        ctx,
        body,
        ctx.texts["summary_heading"],
        _para(ctx, ctx.texts["summary_body"])
        + _command(ctx, command)
        + _list(ctx, ctx.texts["summary_items"]),
        f"{ctx.texts['summary_body']}\n\n{ctx.texts['ask_code']}\n\n"
        f"    {command}\n\n"
        + "".join(f"- {item}\n" for item in ctx.texts["summary_items"]),
    )


def _export(ctx: Ctx, body: Body) -> None:
    html, md = _help_blocks(ctx, body, ctx.texts["export_commands"])
    _section(
        ctx,
        body,
        ctx.texts["export_heading"],
        _para(ctx, ctx.texts["export_body"]) + html,
        f"{ctx.texts['export_body']}\n\n{md}",
    )


def _person_only(ctx: Ctx, body: Body) -> None:
    want = ctx.texts["person_only_policy"]
    policy = next((p for p in ctx.site.policies if p.id == want), None)
    if policy is None:
        raise PageError(f"docs.yaml person_only_policy {want!r} is not in the catalog")
    text = data_fill(
        ctx.texts["person_only_body"],
        {"__ID__": policy.id, "__VERSION__": policy.version},
    )
    link = ctx.t(
        "link", HREF=f"/docs/policies/{policy.id}/", TEXT=ctx.texts["person_only_link"]
    )
    _section(
        ctx,
        body,
        ctx.texts["person_only_heading"],
        _para(ctx, text) + ctx.t("para", TEXT=Safe(link)),
        f"{text}\n\n[{ctx.texts['person_only_link']}]"
        f"({ctx.site.data['site_url']}/docs/policies/{policy.id}/index.md)\n",
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


def _doctor(ctx: Ctx, body: Body) -> None:
    texts = ctx.texts
    help_html, help_md = _help_blocks(ctx, body, texts["doctor_commands"])
    url = _engine_url(ctx, texts["doctor_source_file"])
    link = ctx.t("link", HREF=url, TEXT=texts["doctor_source"])
    _section(
        ctx,
        body,
        texts["doctor_heading"],
        _para(ctx, texts["doctor_intro"])
        + _list(ctx, texts["doctor_items"])
        + _para(ctx, texts["doctor_exit"])
        + help_html
        + ctx.t("para", TEXT=Safe(link)),
        f"{_md_note(ctx, texts['doctor_intro'])}\n\n"
        + "".join(f"- {item}\n" for item in texts["doctor_items"])
        + f"\n{texts['doctor_exit']}\n\n{help_md}"
        + f"[{texts['doctor_source']}]({url})\n",
    )


def _diagnose(ctx: Ctx, body: Body) -> None:
    items = ctx.texts["diagnose_items"]
    _section(
        ctx,
        body,
        ctx.texts["diagnose_heading"],
        _para(ctx, ctx.texts["diagnose_intro"]) + _list(ctx, items),
        f"{ctx.texts['diagnose_intro']}\n\n"
        + "".join(f"- {_md_note(ctx, item)}\n" for item in items),
    )


def _flat(text: str) -> str:
    """Text with blockquote marks dropped and each run of whitespace made one space."""
    return " ".join(re.sub(r"(?m)^\s*>", "", text).split())


def _sources(ctx: Ctx, sources: list[dict[str, str]]) -> tuple[str, str]:
    """An item's chock files as links; each quote must stand word for word in its file's snapshot."""
    for source in sources:
        if "quote" not in source:
            continue
        text = ctx.prose.get(source["file"])
        if text is None or _flat(source["quote"]) not in _flat(text):
            raise PageError(
                f"docs.yaml bypass: {source['file']} at .framework-ref does not say "
                f"{source['quote']!r}"
            )
    files = list(dict.fromkeys(s["file"] for s in sources))
    urls = [_engine_url(ctx, f) for f in files]
    label = ctx.texts["bypass"]["sources"]
    links = [Safe(ctx.t("link", HREF=u, TEXT=f)) for f, u in zip(files, urls)]
    return (
        _para(ctx, label) + _list(ctx, links),
        f"{label}\n\n" + "".join(f"- [{f}]({u})\n" for f, u in zip(files, urls)),
    )


def _agent_cell(ctx: Ctx, agent: dict[str, Any]) -> tuple[Safe, str]:
    """An agent's name linked to its docs page, as HTML and as Markdown."""
    href = f"/docs/agents/{agent['slug']}/"
    return (
        Safe(ctx.t("link", HREF=href, TEXT=agent["name"])),
        f"[{agent['name']}]({ctx.site.data['site_url']}{href}index.md)",
    )


def _agent_rows(
    ctx: Ctx, cols: list[str], picked: list[tuple[dict[str, Any], list[str]]]
) -> tuple[str, str]:
    """A table of agents, each row its linked name and the given cells."""
    cells = [(_agent_cell(ctx, a), rest) for a, rest in picked]
    return (
        _table(ctx, cols, [[h, *rest] for (h, _), rest in cells]),
        _md_table(cols, [[m, *rest] for (_, m), rest in cells]),
    )


def _no_hook_table(ctx: Ctx) -> tuple[str, str]:
    """Agents with no route, or missing one, and the engine's reason why."""
    texts = ctx.texts["bypass"]
    picked = [
        (a, [sentence_start(_route_words(ctx, a)), sentence_start(a["reason"])])
        for a in ctx.agents
        if a["reason"]
    ]
    return _agent_rows(ctx, texts["no_hook_columns"], picked)


def _fail_open_table(ctx: Ctx) -> tuple[str, str]:
    """Agents whose agentseam fail mode before a tool runs is open."""
    texts = ctx.texts["bypass"]
    picked = [
        (a, [sentence_start(_route_words(ctx, a)), a["tier"]])
        for a in ctx.agents
        if a["fail_mode"] == texts["fail_open"]
    ]
    if not picked:
        raise PageError(f"no agent's fail mode reads {texts['fail_open']!r}")
    return _agent_rows(ctx, texts["fail_open_columns"], picked)


def _turn_end_table(ctx: Ctx) -> tuple[str, str]:
    """Per agent, how many policy labels judge a write only at the turn's end."""
    texts = ctx.texts["bypass"]
    clients = ctx.site.data["builder_clients"]
    rows = []
    for client in clients["order"]:
        about = clients["clients"][client]
        count = sum(
            texts["turn_end_marker"] in label["says"]
            for label in about["labels"].values()
        )
        if count:
            rows.append([about["name"], str(count)])
    if not rows:
        raise PageError(f"no agent's label says {texts['turn_end_marker']!r}")
    cols = texts["turn_end_columns"]
    return _table(ctx, cols, rows), _md_table(cols, rows)


def _limits_table(ctx: Ctx) -> tuple[str, str]:
    """The advisory count, and links to every policy whose entry lists what it misses."""
    texts = ctx.texts["bypass"]
    clients = ctx.site.data["builder_clients"]
    reference = clients["clients"][clientdata.ENGINE_CLIENT]["name"]
    keyword = texts["advisory_keyword"]
    if keyword not in ctx.site.label_words["coding"]:
        raise PageError(f"docs.yaml bypass: {keyword!r} is no engine label keyword")
    line = data_fill(
        texts["advisory_line"],
        {
            "__COUNT__": str(sum(p.keyword == keyword for p in ctx.site.policies)),
            "__TOTAL__": str(len(ctx.site.policies)),
            "__WORD__": ctx.site.label_words["coding"][keyword],
            "__AGENT__": reference,
        },
    )
    site_url = ctx.site.data["site_url"]
    shown = [p for p in policies_sorted(ctx.site) if p.misses]
    links = [
        Safe(ctx.t("link", HREF=f"/docs/policies/{p.id}/#what-it-misses", TEXT=p.name))
        for p in shown
    ]
    return (
        _para(ctx, line) + _para(ctx, texts["misses_intro"]) + _list(ctx, links),
        f"{line}\n\n{texts['misses_intro']}\n\n"
        + "".join(
            f"- [{md_escape(p.name)}]({site_url}/docs/policies/{p.id}/index.md)\n"
            for p in shown
        ),
    )


BYPASS_TABLES = {
    "no_hook": _no_hook_table,
    "fail_open": _fail_open_table,
    "turn_end": _turn_end_table,
    "limits": _limits_table,
}


def _bypasses(ctx: Ctx, body: Body) -> None:
    """What Chock doesn't stop: one section per known bypass, each with its chock sources."""
    for item in ctx.texts["bypass"]["items"]:
        html = "".join(_para(ctx, text) for text in item["body"])
        md = "".join(f"{text}\n\n" for text in item["body"])
        if table := item.get("table"):
            if table not in BYPASS_TABLES:
                raise PageError(f"docs.yaml bypass: unknown table {table!r}")
            h, m = BYPASS_TABLES[table](ctx)
            html, md = html + h, f"{md}{m}\n"
        if see := item.get("see"):
            page = ctx.docs["pages"][see]
            label = ctx.texts["bypass"]["see"]
            html += ctx.t("line-link", LINE=label, URL=page["path"], LINK=page["title"])
            md += f"{label} [{page['title']}]({ctx.site.data['site_url']}{page['path']}index.md)\n\n"
        h, m = _sources(ctx, item["sources"])
        _section(ctx, body, item["heading"], html + h, md + m)


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


def _quotes(ctx: Ctx, body: Body, quotes: list[dict[str, str]]) -> tuple[str, str]:
    """Chock's own words behind a claim, refused unless this page quotes a section holding them."""
    texts = ctx.landscape["texts"]
    html, md = [], []
    for q in quotes:
        quoted = [
            e
            for e in ctx.page["prose"]
            if e["file"] == q["file"] and q["section"] in e.get("sections", [])
        ]
        text = ctx.prose.get(q["file"])
        if not quoted or text is None:
            raise PageError(
                f"{LANDSCAPE_YAML}: {q['file']} {q['section']!r} is not quoted on the page"
            )
        if " ".join(q["quote"].split()) not in " ".join(
            sections(text, [q["section"]]).split()
        ):
            raise PageError(
                f"{LANDSCAPE_YAML}: {q['file']} {q['section']!r} lacks {q['quote']!r}"
            )
        url = _engine_url(ctx, q["file"])
        source = data_fill(texts["quote"], {"__FILE__": q["file"]})
        html.append(
            ctx.t(
                "quote",
                QUOTE=body.renderer.inline(q["quote"]),
                SOURCE=source,
                URL=url,
                SECTION=q["section"],
            )
        )
        md.append(f"> {q['quote']}\n>\n> {source} [{q['section']}]({url})\n\n")
    return "".join(html), "".join(md)


def _example(ctx: Ctx, quote: dict[str, str]) -> tuple[str, str]:
    """One vendor example: its quoted sentence, source and date, noted when out of date."""
    texts = ctx.landscape["texts"]
    link = data_fill(texts["vendor_link"], {"__VENDOR__": quote["vendor"]})
    as_of = data_fill(texts["as_of"], {"__DATE__": quote["checked"]})
    stale = (
        data_fill(texts["stale"], {"__DATE__": quote["checked"]})
        if vendorquotes.is_stale(quote["checked"], ctx.today)
        else ""
    )
    html = ctx.t(
        "example",
        NAME=quote["product"],
        VENDOR=quote["vendor"],
        QUOTE=quote["quote"],
        HREF=quote["url"],
        LINK=link,
        ASOF=as_of,
        STALE=Safe(ctx.t("stale", TEXT=stale)) if stale else "",
    )
    md = (
        f"- **{md_escape(quote['product'])}** ({md_escape(quote['vendor'])}): "
        f"\u201c{md_escape(quote['quote'])}\u201d [{link}]({quote['url']}), {as_of}."
        + (f" *{stale}*" if stale else "")
        + "\n"
    )
    return html, md


def _landscape(ctx: Ctx, body: Body) -> None:
    """Where Chock sits: per layer, what it and Chock control, both directions, then examples."""
    data = ctx.landscape
    texts = data["texts"]
    how = texts["how"]
    agents = _page_href(ctx, "agents")
    _section(
        ctx,
        body,
        texts["how_heading"],
        ctx.t(
            "line-link",
            LINE=body.renderer.inline(how),
            URL=agents,
            LINK=texts["agents_link"],
        ),
        f"{how} [{texts['agents_link']}]({ctx.site.data['site_url']}{agents}index.md)\n",
    )
    for layer in data["layers"]:
        examples = [_example(ctx, data["quotes"][key]) for key in layer["examples"]]
        layer_html, layer_md = _quotes(ctx, body, layer["layer_quotes"])
        chock_html, chock_md = _quotes(ctx, body, layer["chock_quotes"])
        html = (
            _h3(ctx, body, texts["controls_heading"])
            + ctx.t("para", TEXT=body.renderer.inline(layer["controls"]))
            + ctx.t("para", TEXT=body.renderer.inline(layer["chock_controls"]))
            + _h3(ctx, body, texts["layer_catches"])
            + ctx.t("para", TEXT=body.renderer.inline(layer["layer"]))
            + layer_html
            + _h3(ctx, body, texts["chock_catches"])
            + ctx.t("para", TEXT=body.renderer.inline(layer["chock"]))
            + chock_html
        )
        md = (
            f"### {texts['controls_heading']}\n\n{layer['controls']}\n\n"
            f"{layer['chock_controls']}\n\n"
            f"### {texts['layer_catches']}\n\n{layer['layer']}\n\n{layer_md}"
            f"### {texts['chock_catches']}\n\n{layer['chock']}\n\n{chock_md}"
        )
        if examples:
            html += _h3(ctx, body, texts["examples_heading"]) + ctx.t(
                "list", ITEMS=Safe("".join(h for h, _ in examples))
            )
            md += f"### {texts['examples_heading']}\n\n" + "".join(
                m for _, m in examples
            )
        _section(ctx, body, layer["heading"], html, md)
    _section(
        ctx,
        body,
        texts["closing_heading"],
        _para(ctx, texts["closing"]),
        f"{texts['closing']}\n",
    )


def _architecture(ctx: Ctx, body: Body) -> None:
    """The Architecture page: its list of diagrams (data/architecture/)."""
    texts = architecture.load_texts(ctx.data_dir)
    diagrams = architecture.load(ctx.data_dir, texts)
    architecture.index(ctx, body, _section, diagrams, texts, ctx.page["path"])


# --- DOCS-1: one page per command and subcommand, from the engine's parsers ------


def cli_page_key(node: dict[str, Any]) -> str:
    """A CLI node's key: its command words joined by "/" ("bundle/status")."""
    return "/".join(node["path"])


def _cli_href(ctx: Ctx, node: dict[str, Any]) -> str:
    return f"{_page_href(ctx, 'cli')}{cli_page_key(node)}/"


def _cli_name(node: dict[str, Any]) -> str:
    return " ".join([engine.CLI_PROG, *node["path"]])


def _cli_covered(ctx: Ctx) -> None:
    """Refuse a build whose docs.yaml cli_pages list differs from the engine's parser tree."""
    listed = ctx.docs["cli_pages"]
    found = [" ".join(n["path"]) for n in ctx.cli_tree]
    if listed != found:
        missing = [n for n in found if n not in listed]
        extra = [n for n in listed if n not in found]
        raise PageError(
            "docs.yaml cli_pages differs from the engine's commands: "
            f"not listed {missing}, not in the engine {extra}"
            + ("" if missing or extra else ", order differs")
        )
    unknown = sorted(set(ctx.cli_examples) - {cli_page_key(n) for n in ctx.cli_tree})
    if unknown:
        raise PageError(f"data/cli-examples/ has recordings for no command: {unknown}")
    for page, recording in ctx.cli_examples.items():
        if recording["engine"] != ctx.site.framework_ref:
            raise PageError(
                f"data/cli-examples/{page}.json was recorded at {recording['engine']}, "
                f".framework-ref is {ctx.site.framework_ref}: "
                "run python -m sitegen.cliexamples --record"
            )


def _cli_index(ctx: Ctx, body: Body) -> None:
    """The CLI reference's index: a link to every command's and subcommand's page."""
    _cli_covered(ctx)
    texts = ctx.texts["cli"]
    groups = ctx.texts["cli_groups"]
    head = texts["index_head"]
    html_rows: list[list[str | Safe]] = []
    md_rows = []
    for node in ctx.cli_tree:
        name = _cli_name(node)
        href = _cli_href(ctx, node)
        html_rows.append(
            [
                Safe(ctx.t("code-link", HREF=href, TEXT=name)),
                groups[node["group"]],
                Prose(sentence_start(node["summary"])),
            ]
        )
        md_rows.append(
            [
                f"[{md_code(name)}]({ctx.site.data['site_url']}{href}index.md)",
                groups[node["group"]],
                sentence_start(node["summary"]),
            ]
        )
    dispatcher = _engine_url(ctx, texts["dispatcher_file"])
    _section(
        ctx,
        body,
        texts["index_heading"],
        _para(ctx, texts["index_intro"])
        + _table(ctx, head, html_rows)
        + ctx.t(
            "line-link",
            LINE=Prose(texts["unknown_command"]),
            URL=dispatcher,
            LINK=texts["dispatcher_file"],
        ),
        f"{texts['index_intro']} {ctx.texts['ask_code']}\n\n{_md_table(head, md_rows)}\n"
        f"{texts['unknown_command']} [{texts['dispatcher_file']}]({dispatcher})\n",
    )


def _cli_argument_cell(ctx: Ctx, argument: dict[str, Any]) -> tuple[str, str]:
    """An argument as argparse prints it (`--repo REPO`), then its choices and "required"."""
    texts = ctx.texts["cli"]
    code = argument["name"]
    if argument["value"] and not argument["choices"]:
        code = f"{code} {argument['value']}"
    tail = []
    if argument["choices"]:
        tail.append(
            data_fill(texts["choices"], {"__LIST__": ", ".join(argument["choices"])})
        )
    if argument["required"]:
        tail.append(texts["required"])
    return code, "".join(f" {part}" for part in tail)


def _cli_arguments(ctx: Ctx, body: Body, node: dict[str, Any]) -> None:
    texts = ctx.texts["cli"]
    head = texts["arguments_head"]
    if not node["arguments"]:
        _section(
            ctx,
            body,
            texts["arguments_heading"],
            _para(ctx, texts["no_arguments"]),
            texts["no_arguments"],
        )
        return
    html_rows: list[list[str | Safe]] = []
    md_rows = []
    for argument in node["arguments"]:
        code, tail = _cli_argument_cell(ctx, argument)
        default = argument["default"]
        html_rows.append(
            [
                Safe(ctx.t("cli-argument", CODE=code, TAIL=tail)),
                Safe(ctx.t("cli-code", TEXT=default)) if default else "",
                Prose(sentence_start(argument["help"])),
            ]
        )
        # The twin leaves out the engine's help wording, as it does for --help (DOC-1).
        md_rows.append(
            [md_code(code) + md_escape(tail), md_code(default) if default else ""]
        )
    _section(
        ctx,
        body,
        texts["arguments_heading"],
        _para(ctx, texts["arguments_intro"]) + _table(ctx, head, html_rows),
        f"{texts['arguments_intro']} {texts['arguments_md']}\n\n"
        f"{_md_table(head[:-1], md_rows)}",
    )


def _cli_subcommands(ctx: Ctx, body: Body, node: dict[str, Any]) -> None:
    texts = ctx.texts["cli"]
    head = texts["subcommands_head"]
    html_rows: list[list[str | Safe]] = []
    md_rows = []
    for sub in node["subcommands"]:
        child = {**node, "path": [*node["path"], sub["name"]]}
        href = _cli_href(ctx, child)
        name = _cli_name(child)
        html_rows.append(
            [
                Safe(ctx.t("code-link", HREF=href, TEXT=name)),
                Prose(sentence_start(sub["summary"])),
            ]
        )
        md_rows.append(
            [
                f"[{md_code(name)}]({ctx.site.data['site_url']}{href}index.md)",
                sentence_start(sub["summary"]),
            ]
        )
    _section(
        ctx,
        body,
        texts["subcommands_heading"],
        _table(ctx, head, html_rows),
        _md_table(head, md_rows),
    )


def _cli_exit(ctx: Ctx, body: Body, node: dict[str, Any], recorded: bool) -> None:
    texts = ctx.texts["cli"]
    lines = [texts["exit_usage"] if node["parser"] else texts["exit_own_parser"]]
    lines.append(texts["exit_recorded"] if recorded else texts["exit_unrecorded"])
    _section(
        ctx,
        body,
        texts["exit_heading"],
        _list(ctx, list(lines)),
        "".join(f"- {line}\n" for line in lines),
    )


def _cli_examples(ctx: Ctx, body: Body, recording: dict[str, Any]) -> None:
    texts = ctx.texts["cli"]
    script = ctx.texts["cli"]["script_file"]
    setup = data_fill(texts["examples_setup"], {"__SCRIPT__": script})
    html = [_para(ctx, setup)]
    md = [f"{setup}\n\n"]
    for example in recording["examples"]:
        step = data_fill(
            texts["examples_step"],
            {
                "__STEP__": str(example["step"]),
                "__OF__": str(example["of"]),
                "__EXIT__": str(example["exit"]),
            },
        )
        shown = f"$ {example['command']}"
        if example["output"]:
            shown += f"\n{example['output']}"
        html += [_para(ctx, step), _code(ctx, shown)]
        md.append(f"{step} {ctx.texts['ask_code']}\n\n```text\n{shown}\n```\n\n")
    _section(ctx, body, texts["examples_heading"], "".join(html), "".join(md))


def _cli_body(ctx: Ctx, body: Body, node: dict[str, Any]) -> None:
    """One command's page: syntax, arguments, subcommands, exit codes, examples, --help."""
    texts = ctx.texts["cli"]
    recording = ctx.cli_examples.get(cli_page_key(node))
    if node["parser"]:
        _section(
            ctx,
            body,
            texts["syntax_heading"],
            _para(ctx, texts["syntax_intro"]) + _code(ctx, node["usage"]),
            f"{texts['syntax_intro']} {ctx.texts['ask_code']}\n\n"
            f"```text\n{node['usage']}\n```\n",
        )
        _cli_arguments(ctx, body, node)
    if node["subcommands"]:
        _cli_subcommands(ctx, body, node)
    _cli_exit(ctx, body, node, recording is not None)
    if recording is not None:
        _cli_examples(ctx, body, recording)
    intro = texts["help_parser"] if node["parser"] else texts["help_own_parser"]
    # A twin carries argparse's usage line only; the table above holds the rest (DOC-1).
    printed = node["help"]
    if node["parser"]:
        printed = printed.split("\n\n", 1)[0]
    _section(
        ctx,
        body,
        texts["help_heading"],
        _para(ctx, intro) + _code(ctx, node["help"]),
        f"{intro} {ctx.texts['ask_code']}\n\n```text\n{printed}\n```\n"
        + (f"\n{ctx.texts['help_more']}\n" if node["parser"] else ""),
    )


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
    "summary": _summary,
    "export": _export,
    "person_only": _person_only,
    "doctor": _doctor,
    "diagnose": _diagnose,
    "measured": _measured,
    "client_notes": _client_notes,
    "bypasses": _bypasses,
    "cli": _cli,
    "landscape": _landscape,
    "cli_index": _cli_index,
    "architecture": _architecture,
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
        _para(ctx, sentence_start(policy.description)),
        md_escape(sentence_start(policy.description)),
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
        rows.append(
            [about["name"], sentence_start(word), sentence_start(label["says"])]
        )
    cols = texts["policy_agent_columns"]
    _section(
        ctx,
        body,
        texts["policy_agents_heading"],
        _table(ctx, cols, rows),
        _md_table(cols, [[md_escape(cell) for cell in row] for row in rows]),
    )
    misses = sentence_start(policy.misses or ctx.site.data["texts"]["misses_empty"])
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


def toc_nav(templates: Path, title: str, headings: list[tuple[int, str, str]]) -> Safe:
    """The "On this page" list for (level, id, text) headings; docs and the FAQ share it."""
    items = "".join(
        render_file(
            templates / DOCS / "toc-item.html",
            LEVEL=str(level),
            HREF=f"#{id_}",
            TEXT=Prose(text),
        )
        for level, id_, text in headings
    )
    return Safe(
        render_file(templates / DOCS / "toc.html", TITLE=title, ITEMS=Safe(items))
    )


def _toc(ctx: Ctx, body: Body, html: str) -> Safe:
    """The "On this page" list: the page's h2 and h3 in document order; empty under two."""
    found = sorted(body.renderer.toc, key=lambda h: html.index(f'id="{h[1]}"'))
    if len(found) < 2:
        return Safe("")
    return toc_nav(ctx.templates, ctx.texts["on_this_page"], found)


def _search(ctx: Ctx) -> Safe:
    """The search box for the docs nav; without JS only its link to the docs index shows."""
    texts = ctx.texts["search"]
    return Safe(
        ctx.t(
            "search",
            INDEX=texts["index"],
            NONE=texts["none"],
            ONE=texts["one"],
            MANY=texts["many"],
            FAILED=texts["failed"],
            DOCS_HREF=_page_href(ctx, "overview"),
            FALLBACK=texts["fallback"],
            LABEL=texts["label"],
            PLACEHOLDER=texts["placeholder"],
            RESULTS=texts["results"],
        )
    )


def chock_quotes_digest(layers: list[dict[str, Any]]) -> str:
    """sha256 of every chock quote on the page, in order, so a changed quote is noticed."""
    rows = [
        q for layer in layers for q in layer["layer_quotes"] + layer["chock_quotes"]
    ]
    blob = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_landscape(data_dir: Path) -> dict[str, Any]:
    """data/landscape.yaml with its vendor quotes, refused on an unknown example or changed chock quote."""
    data = yaml.safe_load((data_dir / LANDSCAPE_YAML).read_text(encoding="utf-8"))
    digest = chock_quotes_digest(data["layers"])
    if digest != data["chock_quotes_sha256"]:
        raise PageError(
            f"{LANDSCAPE_YAML}: chock quotes changed (sha256 {digest}); "
            "check each against chock's docs, then update chock_quotes_sha256"
        )
    quotes = {q["id"]: q for q in vendorquotes.load(data_dir)}
    for layer in data["layers"]:
        unknown = sorted(set(layer["examples"]) - set(quotes))
        if unknown:
            raise PageError(
                f"{LANDSCAPE_YAML}: {layer['heading']!r} names unknown examples {unknown}"
            )
    data["quotes"] = quotes
    return data


def load_actions(data_dir: Path) -> dict[str, Any]:
    """data/page_actions.yaml, refused unless every open link is https with one prompt."""
    actions = yaml.safe_load((data_dir / ACTIONS_YAML).read_text(encoding="utf-8"))
    if actions["prompt"].count("__TWIN__") != 1:
        raise PageError(f"{ACTIONS_YAML}: prompt must name __TWIN__ once")
    for item in actions["open"]:
        href = item["href"]
        if not href.startswith("https://") or href.count("__PROMPT__") != 1:
            raise PageError(
                f"{ACTIONS_YAML}: {item['label']!r} needs https and one __PROMPT__"
            )
    return actions


def _page_actions(ctx: Ctx, path: str) -> Safe:
    """Copy page and its menu; the open links ask an assistant to read this page's twin."""
    twin = f"{path}index.md"
    labels = ctx.actions["labels"]
    prompt = data_fill(
        ctx.actions["prompt"], {"__TWIN__": ctx.site.data["site_url"] + twin}
    )
    items = "".join(
        ctx.t(
            "page-action-open",
            HREF=data_fill(item["href"], {"__PROMPT__": quote(prompt, safe="")}),
            LABEL=item["label"],
        )
        for item in ctx.actions["open"]
    )
    return Safe(
        ctx.t(
            "page-actions",
            MD_HREF=twin,
            VIEW=labels["view"],
            COPIED=labels["copied"],
            FAILED=labels["failed"],
            COPY=labels["copy"],
            MENU=labels["menu"],
            COPY_MARKDOWN=labels["copy_markdown"],
            OPEN=Safe(items),
        )
    )


def _excerpt(ctx: Ctx, summary: str) -> str:
    """A page's summary as one line of plain text, cut at a word boundary."""
    text = " ".join(summary.replace("`", "").split())
    limit = ctx.texts["search"]["excerpt_chars"]
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"


def _search_entry(
    ctx: Ctx, body: Body, html: str, path: str, title: str, summary: str
) -> dict[str, Any]:
    """One page's row in the search index: title, URL, excerpt and its h2/h3 headings."""
    found = sorted(body.renderer.toc, key=lambda h: html.index(f'id="{h[1]}"'))
    return {
        "title": title,
        "url": path,
        "excerpt": _excerpt(ctx, summary),
        "headings": [
            {"id": id_, "text": text.replace("`", "")} for _, id_, text in found
        ],
    }


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
    summary: str,
    code_title: bool = False,
) -> tuple[str, str, dict[str, Any]]:
    """One docs page and its Markdown twin; returns the path, the twin and its search row.

    A `code_title` (a command name) is set as code in the h1 and the twin's heading.
    """
    built_html, built_md = _built(ctx)
    html = "".join(body.html)
    content = ctx.t(
        "layout",
        SEARCH=_search(ctx),
        NAV=_nav(ctx, key),
        TOC=_toc(ctx, body, html),
        COPY=ctx.texts["copy"],
        CRUMB=crumb,
        TITLE=Safe(ctx.t("cli-code", TEXT=title)) if code_title else title,
        SUB=Prose(description),
        ACTIONS=_page_actions(ctx, path),
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
        scripts=("common.js", "docs.js", "search.js"),
    )
    twin = render_text_file(
        ctx.templates / MD / DOCS / "page.md",
        TITLE=md_code(title) if code_title else md_escape(title),
        SUB=md_escape(description),
        INTRO=md_escape(intro),
        ASK=ctx.texts["ask_first"],
        BODY="".join(body.md),
        BUILT=built_md,
    )
    write_md(out_dir, path, twin)
    return path, twin, _search_entry(ctx, body, html, path, title, summary)


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
        actions=load_actions(data_dir),
        landscape=load_landscape(data_dir),
        data_dir=data_dir,
        cli_tree=engine.cli_tree(),
        cli_examples=cliexamples.load(data_dir),
    )
    written: list[tuple[str, str, str, str]] = []
    rows: list[dict[str, Any]] = []

    def emit(
        key: str,
        path: str,
        title: str,
        description: str,
        intro: str,
        crumb: str,
        body: Body,
        summary: str = "",
        code_title: bool = False,
    ) -> None:
        page_path, twin, row = _write(
            ctx,
            out_dir,
            key=key,
            path=path,
            title=title,
            description=description,
            intro=intro,
            crumb=crumb,
            body=body,
            summary=summary or intro,
            code_title=code_title,
        )
        written.append((page_path, title, description, twin))
        rows.append(row)

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
            policy.description,
        )

    cli_page = docs["pages"]["cli"]
    for node in ctx.cli_tree:
        body = _new_body(ctx)
        _cli_body(ctx, body, node)
        name = _cli_name(node)
        emit(
            "cli",
            _cli_href(ctx, node),
            name,
            data_fill(ctx.texts["cli"]["description"], {"__NAME__": name}),
            sentence_start(node["summary"]),
            cli_page["title"],
            body,
            code_title=True,
        )

    arch_page = docs["pages"]["architecture"]
    arch_texts = architecture.load_texts(data_dir)
    diagrams = architecture.load(data_dir, arch_texts)
    for diagram in diagrams:
        body = _new_body(ctx)
        architecture.page(ctx, body, _section, diagram, arch_texts)
        emit(
            "architecture",
            f"{arch_page['path']}{diagram.id}/",
            diagram.title,
            diagram.summary,
            diagram.intro,
            arch_page["title"],
            body,
        )
    architecture.write_data(out_dir, diagrams, arch_texts)

    _api(ctx, out_dir, written)
    _search_index(ctx, out_dir, rows)
    llms = "".join(
        f"- [Docs: {p['nav_label']}]({p['path']}index.md): {p['description']}\n"
        for p in docs["pages"].values()
    )
    llms += "".join(
        f"- [Docs: {md_escape(title)}]({path}index.md): {md_escape(description)}\n"
        for path, title, description, _ in written
        if path not in {p["path"] for p in docs["pages"].values()}
    )
    return SectionResult(
        pages=[p for p, _, _, _ in written],
        llms=llms,
        docs=[(f"{p}index.md", twin) for p, _, _, twin in written],
        data_lines=(
            "- [/api/docs/index.json](/api/docs/index.json): every docs page, "
            "and each agent's routes, grade and witness rows\n"
            "- [/api/docs/search.json](/api/docs/search.json): the docs search index: "
            "each page's title, URL, excerpt and headings\n"
        ),
    )


def _api(ctx: Ctx, out_dir: Path, written: list[tuple[str, str, str, str]]) -> None:
    """/api/docs/index.json: the docs pages and the per-agent facts they show."""
    api = out_dir / "api" / DOCS
    api.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "engine": ctx.site.framework_ref,
        "catalog": ctx.site.catalog_ref,
        "pages": [
            {"path": p, "md": f"{p}index.md", "title": t} for p, t, _, _ in written
        ],
        "agents": [{k: v for k, v in a.items() if k != "notes"} for a in ctx.agents],
    }
    (api / "index.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _search_index(ctx: Ctx, out_dir: Path, rows: list[dict[str, Any]]) -> None:
    """/api/docs/search.json for the docs search box; the build fails past its byte budget."""
    texts = ctx.texts["search"]
    doc = {"schema_version": 1, "pages": rows}
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"
    data = text.encode("utf-8")
    if len(data) > texts["budget_bytes"]:
        msg = (
            f"{texts['index']} is {len(data)} bytes, over its budget of "
            f"{texts['budget_bytes']} (data/docs.yaml texts.search.budget_bytes)"
        )
        raise PageError(msg)
    target = out_dir / texts["index"].lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


# --- DOCS-2: How Chock works ------------------------------------------------------


def _how_steps(ctx: Ctx, body: Body) -> None:
    """The lifecycle diagram's main path as a list: each step's box, its card and the file it cites."""
    how = ctx.texts["how"]
    texts = architecture.load_texts(ctx.data_dir)
    diagram = next(
        (
            d
            for d in architecture.load(ctx.data_dir, texts)
            if d.id == how["steps_diagram"]
        ),
        None,
    )
    if diagram is None or not diagram.path:
        raise PageError(
            f"docs.yaml how.steps_diagram {how['steps_diagram']!r} has no main path"
        )
    nodes = {n["id"]: n for n in diagram.nodes}
    steps = [
        (nodes[i], architecture.source_url(texts, diagram, nodes[i]["source"]))
        for i in diagram.path
    ]
    items = "".join(
        render_file(
            ctx.templates / architecture.FOLDER / "index-item.html",
            HREF=url,
            TITLE=architecture.label_prose(node),
            SUMMARY=node["card"],
        )
        for node, url in steps
    )
    _section(
        ctx,
        body,
        how["steps_heading"],
        _para(ctx, how["steps_intro"]) + ctx.t("list", ITEMS=Safe(items)),
        f"{how['steps_intro']}\n\n"
        + "".join(
            f"- [{architecture.label_md(node)}]({url}): {md_escape(node['card'])}\n"
            for node, url in steps
        ),
    )


def _how_diagrams(ctx: Ctx, body: Body) -> None:
    """The diagrams that show how chock works, each linked to its page under Architecture."""
    how = ctx.texts["how"]
    diagrams = {d.id: d for d in architecture.load(ctx.data_dir)}
    if missing := [i for i in how["diagrams"] if i not in diagrams]:
        raise PageError(f"docs.yaml how.diagrams names no diagram {missing}")
    base = _page_href(ctx, "architecture")
    picked = [diagrams[i] for i in how["diagrams"]]
    items = "".join(
        render_file(
            ctx.templates / architecture.FOLDER / "index-item.html",
            HREF=f"{base}{d.id}/",
            TITLE=d.title,
            SUMMARY=d.summary,
        )
        for d in picked
    )
    _section(
        ctx,
        body,
        how["diagrams_heading"],
        _para(ctx, how["diagrams_intro"]) + ctx.t("list", ITEMS=Safe(items)),
        f"{how['diagrams_intro']}\n\n"
        + "".join(
            f"- [{md_escape(d.title)}]({ctx.site.data['site_url']}{base}{d.id}/index.md): "
            f"{md_escape(d.summary)}\n"
            for d in picked
        ),
    )


# A surface row in chock's table: its first cell is the surface name in backticks.
SURFACE_CELL_RE = re.compile(r"^\|\s*`([a-z-]+)`\s*\|")


def _doc_table(text: str) -> list[str]:
    """The lines of the first Markdown table in `text`."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("|")), None)
    if start is None:
        return []
    end = next(
        (i for i in range(start, len(lines)) if not lines[i].startswith("|")),
        len(lines),
    )
    return lines[start:end]


def _surfaces(ctx: Ctx, body: Body) -> None:
    """chock's own surface table, then each surface's emitter and agents as the engine's code has them."""
    how = ctx.texts["how"]
    source = how["surfaces_file"]
    table = _doc_table(sections(ctx.prose[source] or "", [how["surfaces_section"]]))
    documented = [
        m.group(1) for line in table[2:] if (m := SURFACE_CELL_RE.match(line))
    ]
    rows = engine.surface_rows()
    coded = [r["surface"] for r in rows]
    if sorted(documented) != sorted(coded):
        raise PageError(
            f"{source} at .framework-ref lists surfaces {sorted(documented)}, "
            f"the engine's code has {sorted(coded)}"
        )
    quoted = "\n".join(table) + "\n"
    resolve = _resolver(ctx, source)
    renderer = Renderer(ctx.templates, resolve, callouts=ctx.texts["callouts"])
    renderer.ids = body.renderer.ids
    renderer.toc = body.renderer.toc
    url = _engine_url(ctx, source)
    from_label = ctx.texts["prose_heading"] + ":"
    _section(
        ctx,
        body,
        how["surfaces_heading"],
        _para(ctx, how["surfaces_intro"])
        + ctx.t(
            "prose",
            FROM=from_label,
            URL=url,
            FILE=source,
            BODY=renderer.blocks(quoted),
        ),
        f"{how['surfaces_intro']}\n\n{from_label} [{source}]({url})\n\n"
        + rewrite_links(quoted, resolve),
    )
    html_rows: list[list[str | Safe]] = []
    md_rows: list[list[str]] = []
    for row in rows:
        # Agent ids are identifiers: each is set as code.
        agents: str | Safe = how["no_agents"]
        agents_md = how["no_agents"]
        if row["agents"]:
            agents = Safe(", ".join(ctx.t("cli-code", TEXT=a) for a in row["agents"]))
            agents_md = ", ".join(md_code(a) for a in row["agents"])
        held = how["held_out"] if not row["credited"] else how["counted"]
        if row["emitter"]:
            emitter_url = _engine_url(ctx, row["emitter"])
            emitter: str | Safe = Safe(
                ctx.t("link", HREF=emitter_url, TEXT=row["emitter"])
            )
            emitter_md = f"[{row['emitter']}]({emitter_url})"
        else:
            emitter = emitter_md = how["no_emitter"]
        html_rows.append(
            [Safe(ctx.t("code", TEXT=row["surface"])), emitter, agents, held]
        )
        md_rows.append([f"`{row['surface']}`", emitter_md, agents_md, held])
    _section(
        ctx,
        body,
        how["code_heading"],
        _para(ctx, how["code_intro"]) + _table(ctx, how["code_columns"], html_rows),
        f"{how['code_intro']}\n\n" + _md_table(how["code_columns"], md_rows),
    )


def _stop_help(ctx: Ctx, body: Body) -> None:
    """chock stop and chock resume, as the engine's parsers print them."""
    how = ctx.texts["how"]
    html, md = _help_blocks(ctx, body, how["help_commands"])
    _section(
        ctx,
        body,
        how["help_heading"],
        _para(ctx, how["help_intro"]) + html,
        f"{how['help_intro']}\n\n{md}",
    )


def _check_quotes(ctx: Ctx, sources: list[dict[str, str]]) -> None:
    """Each quote stands word for word in its file: the docs snapshot, or the installed engine's source."""
    for source in sources:
        if "quote" not in source:
            continue
        path = source["file"]
        text = (
            engine.engine_source(path)
            if path.startswith("src/")
            else ctx.prose.get(path)
        )
        if text is None or _flat(source["quote"]) not in _flat(text):
            raise PageError(
                f"docs.yaml how: {path} at .framework-ref does not say {source['quote']!r}"
            )


def _stop_facts(ctx: Ctx, body: Body) -> None:
    """What a stop does, where it is checked and its limits, each item with the chock files it quotes."""
    how = ctx.texts["how"]
    facts = engine.stop_facts()
    words = " ".join(line for item in how["facts"] for line in item["body"])
    for key in ("repo_file", "registry", "everywhere_file", "confirm_word"):
        if facts[key] not in words:
            raise PageError(
                f"docs.yaml how.facts never names the engine's {facts[key]!r}"
            )
    for item in how["facts"]:
        _check_quotes(ctx, item["sources"])
        html, md = "", ""
        if item.get("limits"):
            html += _para(ctx, how["limits_intro"]) + _code(ctx, facts["limits"])
            md += f"{how['limits_intro']}\n\n```text\n{facts['limits']}\n```\n\n"
        html += _list(ctx, item["body"])
        md += "".join(f"- {line}\n" for line in item["body"]) + "\n"
        h, m = _sources(ctx, [{"file": s["file"]} for s in item["sources"]])
        _section(ctx, body, item["heading"], html + h, md + m)
    url = _engine_url(ctx, how["stop_file"])
    body.html.append(
        ctx.t("line-link", LINE=how["stop_source"], URL=url, LINK=how["stop_file"])
    )
    body.md.append(f"{how['stop_source']} [{how['stop_file']}]({url})\n\n")


# --- DOCS-3: the agentseam pages, from the agentseam release chock pins ----------

# Imported here, not at the top, so this block stays append-only beside DOCS-2 and DOCS-4.
from . import agentseamdoc


def _agentseam_ref(ctx: Ctx) -> str:
    """The agentseam commit the pages document; refused unless it is installed and chock's pin."""
    pinned = agentseamdoc.pinned(ctx.data_dir)
    installed = engine.agentseam_commit()
    required = engine.agentseam_chock_pin()
    if not pinned == installed == required:
        raise PageError(
            f"agentseam: the snapshot pins {pinned}, the installed agentseam is "
            f"{installed or 'not from git'}, chock at .framework-ref requires "
            f"{required or 'no agentseam commit'}: install chock at .framework-ref and run "
            "python -m sitegen.agentseamdoc snapshot and run --record"
        )
    return pinned


def _agentseam_url(ctx: Ctx, path: str = "") -> str:
    """A link into agentseam at the pinned commit: the commit, or a file (with #L<line>) in it."""
    subs = {"__REPO__": ctx.docs["agentseam"]["repo"], "__REF__": _agentseam_ref(ctx)}
    if not path:
        return data_fill(COMMIT_URL, subs)
    return data_fill(BLOB_URL, subs | {"__PATH__": path})


def _agentseam_texts(ctx: Ctx) -> dict[str, Any]:
    return ctx.docs["agentseam"]["texts"]


def _agentseam_resolver(ctx: Ctx, source: str):
    """Resolve a link in an agentseam file: web links kept, repo paths sent to GitHub at the pin."""

    def resolve(href: str) -> str:
        parts = urlsplit(href)
        if parts.scheme in ("http", "https", "mailto"):
            return href
        frag = f"#{parts.fragment}" if parts.fragment else ""
        if not parts.path:
            return _agentseam_url(ctx, source) + frag
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), parts.path))
        if path.startswith(".."):
            return _agentseam_url(ctx)
        return _agentseam_url(ctx, path) + frag

    return resolve


def _agentseam_prose(ctx: Ctx, body: Body, file: str, text: str) -> None:
    """A quoted agentseam file section, from the snapshot, with links sent to GitHub."""
    texts = _agentseam_texts(ctx)
    resolve = _agentseam_resolver(ctx, file)
    renderer = Renderer(ctx.templates, resolve, callouts=ctx.texts["callouts"])
    renderer.ids = body.renderer.ids
    renderer.toc = body.renderer.toc
    url = _agentseam_url(ctx, file)
    body.html.append(
        ctx.t(
            "prose",
            FROM=texts["prose_heading"] + ":",
            URL=url,
            FILE=file,
            BODY=renderer.blocks(text),
        )
    )
    body.md.append(
        f"{texts['prose_heading']}: [{file}]({url})\n\n"
        + rewrite_links(text, resolve, ctx.texts["ask_code"])
        + "\n"
    )


def _agentseam_release(ctx: Ctx, body: Body) -> None:
    """The facts about the agentseam release the pages document."""
    texts = _agentseam_texts(ctx)
    labels = texts["release_rows"]
    meta = engine.agentseam_meta()
    ref = _agentseam_ref(ctx)
    commit_url = _agentseam_url(ctx)
    pyproject = _engine_url(ctx, "pyproject.toml")
    rows: list[tuple[str, str, str | Safe]] = [
        ("package", f"`agentseam {meta['version']}`", ""),
        ("commit", ref, Safe(ctx.t("link", HREF=commit_url, TEXT=ref))),
        ("python", meta["requires_python"], ""),
        ("license", meta["license"], ""),
        ("requires", meta["requires"] or texts["no_requires"], ""),
        ("script", engine.AGENTSEAM_PROG, ""),
        (
            "pinned",
            texts["pinned_by"],
            Safe(ctx.t("link", HREF=pyproject, TEXT=texts["pinned_by"])),
        ),
    ]
    _section(
        ctx,
        body,
        texts["release_heading"],
        _facts(ctx, [(labels[k], html or Prose(v)) for k, v, html in rows]),
        "".join(
            f"- {labels[k]}: "
            + (
                f"[{v}]({commit_url})"
                if k == "commit"
                else f"[{v}]({pyproject})"
                if k == "pinned"
                else v
            )
            + "\n"
            for k, v, _ in rows
        ),
    )


def _agentseam_about(ctx: Ctx, body: Body) -> None:
    """What agentseam is: the release, its own docs quoted, and the other agentseam pages."""
    import html

    _agentseam_release(ctx, body)
    texts = _agentseam_texts(ctx)
    site = ctx.site.data["site_url"]
    items: list[str | Safe] = []
    md = []
    for item in texts["pages_items"]:
        page = ctx.docs["pages"][item["page"]]
        tail = data_fill(texts["pages_line"], {"__TEXT__": item["text"]})
        link = ctx.t("link", HREF=page["path"], TEXT=page["title"])
        items.append(Safe(link + html.escape(tail, quote=True)))
        md.append(f"- [{page['title']}]({site}{page['path']}index.md){tail}\n")
    _section(ctx, body, texts["pages_heading"], _list(ctx, items), "".join(md))
    prose = agentseamdoc.load(ctx.data_dir)
    for entry in ctx.docs["agentseam"]["quotes"]:
        if entry.get("whole"):
            continue
        _agentseam_prose(ctx, body, entry["file"], prose[entry["file"]])


def _agentseam_direct(ctx: Ctx, body: Body) -> None:
    """Install, the files, and the recorded run of the README's handler."""
    texts = _agentseam_texts(ctx)
    cfg = ctx.docs["agentseam"]
    ref = _agentseam_ref(ctx)
    meta = engine.agentseam_meta()
    command = data_fill(
        texts["install_command"], {"__REPO__": cfg["repo"], "__REF__": ref}
    )
    python = data_fill(texts["install_python"], {"__PYTHON__": meta["requires_python"]})
    _section(
        ctx,
        body,
        texts["install_heading"],
        _para(ctx, texts["install_intro"])
        + _command(ctx, command)
        + _para(ctx, python),
        f"{texts['install_intro']}\n\n```bash\n{command}\n```\n\n{python}\n",
    )
    script = agentseamdoc.load_script(ctx.data_dir)
    if set(script["files"]) != set(texts["files"]):
        raise PageError(
            f"docs.yaml agentseam.texts.files names {sorted(texts['files'])}, "
            f"{cfg['run_script']} writes {sorted(script['files'])}"
        )
    example = cfg["texts"]["example_file"]
    example_url = _agentseam_url(ctx, example)
    intro = data_fill(texts["files_intro"], {"__EXAMPLE__": f"`{example}`"})
    html_parts = [ctx.t("line-link", LINE=Prose(intro), URL=example_url, LINK=example)]
    md = [f"{intro} [{example}]({example_url})\n\n"]
    for name, text in script["files"].items():
        lang = "python" if name.endswith(".py") else "json"
        html_parts += [
            _h3(ctx, body, name),
            _para(ctx, texts["files"][name]),
            _code(ctx, text.rstrip("\n"), lang),
        ]
        md.append(f"### {name}\n\n{texts['files'][name]}\n\n```{lang}\n{text}```\n\n")
    _section(ctx, body, texts["files_heading"], "".join(html_parts), "".join(md))
    recording = agentseamdoc.load_run(ctx.data_dir)
    if recording["agentseam"] != ref:
        raise PageError(
            f"data/{cfg['run_record']} was recorded at agentseam {recording['agentseam']}, "
            f"the pages document {ref}: run python -m sitegen.agentseamdoc run --record"
        )
    commands = [agentseamdoc.shown_command(step) for step in script["steps"]]
    if [e["command"] for e in recording["examples"]] != commands:
        raise PageError(
            f"data/{cfg['run_record']} differs from the steps of {cfg['run_script']}: "
            "run python -m sitegen.agentseamdoc run --record"
        )
    notes = texts["run_notes"]
    if sorted(notes) != list(range(1, len(commands) + 1)):
        raise PageError(
            f"docs.yaml agentseam.texts.run_notes needs one note per step, 1 to {len(commands)}"
        )
    run_intro = data_fill(
        texts["run_intro"], {"__SCRIPT__": f"data/{cfg['run_script']}"}
    )
    html_parts = [_para(ctx, run_intro)]
    md = [f"{run_intro}\n\n"]
    for example in recording["examples"]:
        step = data_fill(
            texts["run_step"],
            {
                "__STEP__": str(example["step"]),
                "__OF__": str(example["of"]),
                "__EXIT__": str(example["exit"]),
            },
        )
        note = notes[example["step"]]
        shown = f"$ {example['command']}"
        if example["output"]:
            shown += f"\n{example['output']}"
        html_parts += [_para(ctx, f"{step} {note}"), _code(ctx, shown)]
        md.append(f"{step} {note} {ctx.texts['ask_code']}\n\n```text\n{shown}\n```\n\n")
    _section(ctx, body, texts["run_heading"], "".join(html_parts), "".join(md))


def _api_groups(
    ctx: Ctx, api: list[dict[str, Any]]
) -> list[tuple[str, list[dict[str, Any]]]]:
    """The API entries in docs.yaml's groups; refused unless they cover `__all__` exactly once."""
    by_name = {entry["name"]: entry for entry in api}
    listed = [n for g in ctx.docs["agentseam"]["api_groups"] for n in g["names"]]
    missing = [n for n in by_name if n not in listed]
    extra = [n for n in listed if n not in by_name]
    twice = sorted({n for n in listed if listed.count(n) > 1})
    if missing or extra or twice:
        raise PageError(
            "docs.yaml agentseam.api_groups differs from agentseam.__all__: "
            f"not listed {missing}, not exported {extra}, listed twice {twice}"
        )
    return [
        (g["heading"], [by_name[n] for n in g["names"]])
        for g in ctx.docs["agentseam"]["api_groups"]
    ]


def _api_value(texts: dict[str, Any], entry: dict[str, Any]) -> str:
    if entry["size"] is not None:
        return sentence_start(
            data_fill(
                texts["api_size"],
                {"__KIND__": entry["kind"], "__COUNT__": str(entry["size"])},
            )
        )
    return entry["value"]


def _api_doc(texts: dict[str, Any], entry: dict[str, Any]) -> str:
    return entry["doc"] or texts["no_doc"]


def _api_values(ctx: Ctx, entries: list[dict[str, Any]]) -> tuple[str, str]:
    """Constants as one Name, Value table."""
    texts = _agentseam_texts(ctx)
    head = texts["api_value_head"]
    rows = [(e["name"], _api_value(texts, e), e["size"] is None) for e in entries]
    html_rows: list[list[str | Safe]] = [
        [
            Safe(ctx.t("cli-code", TEXT=name)),
            Safe(ctx.t("cli-code", TEXT=value)) if code else value,
        ]
        for name, value, code in rows
    ]
    md_rows = [[md_code(n), md_code(v) if code else v] for n, v, code in rows]
    return _table(ctx, head, html_rows), _md_table(head, md_rows)


def _api_members(ctx: Ctx, members: list[dict[str, Any]]) -> tuple[str, str]:
    """A class's or module's members as one table: name, kind, signature, summary."""
    texts = _agentseam_texts(ctx)
    head = texts["api_member_head"]
    html_rows: list[list[str | Safe]] = []
    md_rows = []
    for m in members:
        shown = (
            _api_value(texts, m) if m.get("value") or m.get("size") is not None else ""
        )
        signature = m["signature"] or shown
        doc = "" if shown else _api_doc(texts, m)
        html_rows.append(
            [
                Safe(ctx.t("cli-code", TEXT=m["name"])),
                m["kind"],
                Safe(ctx.t("cli-code", TEXT=signature)) if signature else "",
                Prose(doc),
            ]
        )
        md_rows.append(
            [
                md_code(m["name"]),
                m["kind"],
                md_code(signature) if signature else "",
                doc,
            ]
        )
    return _table(ctx, head, html_rows), _md_table(head, md_rows)


def _api_entry_html(ctx: Ctx, body: Body, entry: dict[str, Any]) -> tuple[str, str]:
    """One exported class, function or module: heading, signature, summary, source, members."""
    texts = _agentseam_texts(ctx)
    name = entry["name"]
    # An exported name is an identifier: its heading renders as code.
    html = [_h3(ctx, body, md_code(name))]
    md = [f"### {md_code(name)}\n\n"]
    if entry["signature"]:
        line = f"{name}{entry['signature']}"
        html.append(_code(ctx, line, "python"))
        md.append(f"```python\n{line}\n```\n\n")
    if entry["kind"] == "module":
        intro = data_fill(texts["api_module"], {"__MODULE__": entry["module"]})
        html += [_para(ctx, _api_doc(texts, entry)), _para(ctx, intro)]
        md.append(f"{_api_doc(texts, entry)}\n\n{intro}\n\n")
    else:
        html.append(_para(ctx, _api_doc(texts, entry)))
        md.append(f"{_api_doc(texts, entry)}\n\n")
    if entry["source"]:
        path = entry["source"]
        url = _agentseam_url(ctx, path)
        html.append(
            ctx.t(
                "line-link", LINE=texts["api_heading_source"] + ":", URL=url, LINK=path
            )
        )
        md.append(f"{texts['api_heading_source']}: [{path}]({url})\n\n")
    if entry["members"]:
        h, m = _api_members(ctx, entry["members"])
        html.append(h)
        md.append(f"{m}\n")
    return "".join(html), "".join(md)


def _agentseam_api(ctx: Ctx, body: Body) -> None:
    """Every name agentseam exports, grouped as docs.yaml says, read from the installed release."""
    texts = _agentseam_texts(ctx)
    _agentseam_ref(ctx)
    api = engine.agentseam_api()
    _section(
        ctx,
        body,
        texts["api_about_heading"],
        _para(ctx, texts["api_intro"]),
        f"{texts['api_intro']}\n",
    )
    for heading, entries in _api_groups(ctx, api):
        html, md = [], []
        values = [
            e for e in entries if e["kind"] not in ("class", "function", "module")
        ]
        for entry in entries:
            if entry in values:
                continue
            h, m = _api_entry_html(ctx, body, entry)
            html.append(h)
            md.append(m)
        if values:
            h, m = _api_values(ctx, values)
            html.append(h)
            md.append(m)
            if any(e["name"] == "MATRIX" for e in values):
                agents = ctx.docs["pages"]["agents"]
                html.append(
                    ctx.t(
                        "line-link",
                        LINE=texts["api_matrix"],
                        URL=agents["path"],
                        LINK=agents["title"],
                    )
                )
                md.append(
                    f"\n{texts['api_matrix']} "
                    f"[{agents['title']}]({ctx.site.data['site_url']}{agents['path']}index.md)\n"
                )
        _section(ctx, body, heading, "".join(html), "".join(md))


def _agentseam_cli_name(node: dict[str, Any]) -> str:
    return " ".join([engine.AGENTSEAM_PROG, *node["path"]])


def _agentseam_breakable(ctx: Ctx, text: str) -> str | Safe:
    """Help text with a line-break chance after each "/", so a long path wraps at phone width."""
    import html

    if "`" in text or "/" not in text:
        return Prose(text)
    parts = re.split(r"(?<=/)", text)
    return Safe(ctx.t("wbr").join(html.escape(part, quote=True) for part in parts))


def _agentseam_cli_arguments(ctx: Ctx, node: dict[str, Any]) -> tuple[str, str]:
    """A command's arguments as argparse prints them, each with its default, then its help.

    The default sits in the argument's cell, so the help column keeps the width a long
    word in agentseam's help needs at phone width.
    """
    import html

    texts = _agentseam_texts(ctx)
    if not node["arguments"]:
        return _para(ctx, texts["cli_no_arguments"]), f"{texts['cli_no_arguments']}\n\n"
    head = texts["cli_arguments_head"]
    html_rows: list[list[str | Safe]] = []
    md_rows = []
    for argument in node["arguments"]:
        code, tail = _cli_argument_cell(ctx, argument)
        default = argument["default"]
        cell = ctx.t("cli-argument", CODE=code, TAIL=tail)
        md_cell = md_code(code) + md_escape(tail)
        if default:
            label = html.escape(f" {texts['cli_default']} ", quote=True)
            cell += label + ctx.t("cli-code", TEXT=default)
            md_cell += f" {texts['cli_default']} {md_code(default)}"
        shown = sentence_start(argument["help"])
        html_rows.append([Safe(cell), _agentseam_breakable(ctx, shown)])
        md_rows.append([md_cell, md_escape(shown)])
    return _table(ctx, head, html_rows), _md_table(head, md_rows) + "\n"


def _agentseam_cli(ctx: Ctx, body: Body) -> None:
    """The agentseam command and each subcommand, from its parser, then exit codes and --help."""
    texts = _agentseam_texts(ctx)
    _agentseam_ref(ctx)
    nodes = engine.agentseam_cli()
    head = texts["cli_head"]
    rows = [(_agentseam_cli_name(n), sentence_start(n["summary"])) for n in nodes]
    _section(
        ctx,
        body,
        texts["cli_heading"],
        _para(ctx, texts["cli_intro"])
        + _table(
            ctx, head, [[Safe(ctx.t("cli-code", TEXT=c)), Prose(s)] for c, s in rows]
        ),
        f"{texts['cli_intro']}\n\n"
        + _md_table(head, [[md_code(c), s] for c, s in rows]),
    )
    for node in nodes:
        name = _agentseam_cli_name(node)
        summary = sentence_start(node["summary"])
        args_html, args_md = _agentseam_cli_arguments(ctx, node)
        html = [
            _para(ctx, summary) if summary else "",
            _para(ctx, texts["cli_usage"] + ":"),
            _code(ctx, node["usage"]),
            args_html,
        ]
        md = [
            f"{summary}\n\n" if summary else "",
            f"{texts['cli_usage']}:\n\n```text\n{node['usage']}\n```\n\n",
            args_md,
        ]
        if node["subcommands"]:
            subs = [" ".join([name, s["name"]]) for s in node["subcommands"]]
            html += [
                _para(ctx, texts["cli_subcommands"]),
                _list(ctx, [Safe(ctx.t("cli-code", TEXT=s)) for s in subs]),
            ]
            md.append(
                f"{texts['cli_subcommands']}\n\n"
                + "".join(f"- {md_code(s)}\n" for s in subs)
            )
        _section(ctx, body, md_code(name), "".join(html), "".join(md))
    lines = texts["exit_lines"]
    _section(
        ctx,
        body,
        texts["exit_heading"],
        _list(ctx, list(lines)),
        "".join(f"- {line}\n" for line in lines),
    )
    root = nodes[0]
    _section(
        ctx,
        body,
        texts["help_heading"],
        _para(ctx, texts["help_intro"]) + _code(ctx, root["help"]),
        f"{texts['help_intro']}\n\n```text\n{root['help']}\n```\n",
    )


BLOCKS.update(
    {
        "how_steps": _how_steps,
        "how_diagrams": _how_diagrams,
        "surfaces": _surfaces,
        "stop_help": _stop_help,
        "stop_facts": _stop_facts,
        "agentseam_about": _agentseam_about,
        "agentseam_direct": _agentseam_direct,
        "agentseam_api": _agentseam_api,
        "agentseam_cli": _agentseam_cli,
    }
)


# --- DOCS-4: the catalog pages, from data/catalog-source/ (sitegen/catalogdoc.py) ------


def _catalog_subs(ctx: Ctx) -> dict[str, str]:
    """__CATALOG__ and __ENGINE__: GitHub file links at the pinned catalog and engine commits."""
    return {
        "__CATALOG__": data_fill(
            BLOB_URL,
            {
                "__REPO__": ctx.texts["catalog"]["repo"],
                "__REF__": ctx.site.catalog_ref,
                "__PATH__": "",
            },
        ),
        "__ENGINE__": data_fill(
            BLOB_URL,
            {
                "__REPO__": ctx.docs["engine_repo"],
                "__REF__": ctx.site.framework_ref,
                "__PATH__": "",
            },
        ),
    }


def _catalog_resolver(ctx: Ctx, source: str):
    """Resolve a link in a catalog file: web links kept, repo paths sent to GitHub at the pinned commit."""
    base = _catalog_subs(ctx)["__CATALOG__"]

    def resolve(href: str) -> str:
        parts = urlsplit(href)
        if parts.scheme in ("http", "https", "mailto"):
            return href
        frag = f"#{parts.fragment}" if parts.fragment else ""
        path = posixpath.normpath(
            posixpath.join(posixpath.dirname(source), parts.path or source)
        )
        return base + quote(path) + frag

    return resolve


def _twin_href(ctx: Ctx, href: str) -> str:
    """A site link as the Markdown twins write it: the page's index.md on the site."""
    if href.startswith("/docs/"):
        return f"{ctx.site.data['site_url']}{href}index.md"
    return href


def _catalog_renderer(ctx: Ctx, body: Body, resolve) -> Renderer:
    renderer = Renderer(ctx.templates, resolve, callouts=ctx.texts["callouts"])
    renderer.ids = body.renderer.ids
    renderer.toc = body.renderer.toc
    return renderer


def _catalog_md(ctx: Ctx, body: Body, part: dict[str, Any]) -> tuple[str, str]:
    text = data_fill(part["md"], _catalog_subs(ctx))
    html = _catalog_renderer(ctx, body, lambda href: href).blocks(text)
    md = rewrite_links(text, lambda href: _twin_href(ctx, href), ctx.texts["ask_code"])
    return html, md


def _catalog_quote(
    ctx: Ctx, body: Body, part: dict[str, Any], source: dict[str, Any]
) -> tuple[str, str]:
    """Quoted sections of a catalog file, from the snapshot, with links sent to GitHub."""
    path = part["quote"]
    text = sections(source["quotes"][path], part["sections"], part.get("level", 2))
    resolve = _catalog_resolver(ctx, path)
    url = _catalog_subs(ctx)["__CATALOG__"] + path
    label = ctx.texts["catalog"]["quote_from"]
    html = ctx.t(
        "prose",
        FROM=label + ":",
        URL=url,
        FILE=path,
        BODY=_catalog_renderer(ctx, body, resolve).blocks(text),
    )
    md = f"{label}: [{path}]({url})\n\n" + rewrite_links(
        text, resolve, ctx.texts["ask_code"]
    )
    return html, md


def _catalog_run(ctx: Ctx, source: dict[str, Any]) -> tuple[str, str]:
    """The recorded adopt run: each step's note, command, output and exit code."""
    texts = ctx.texts["catalog"]
    examples = source["adopt"]["examples"]
    if len(texts["run_notes"]) != len(examples):
        raise PageError("docs.yaml texts.catalog.run_notes: one note per adopt step")
    setup = data_fill(texts["run_setup"], {"__SCRIPT__": texts["run_script"]})
    html, md = [_para(ctx, setup)], [f"{setup}\n\n"]
    for note, example in zip(texts["run_notes"], examples, strict=True):
        step = data_fill(
            texts["run_step"],
            {"__STEP__": str(example["step"]), "__EXIT__": str(example["exit"])},
        )
        shown = f"$ {example['command']}"
        if example["output"]:
            shown += f"\n{example['output']}"
        html += [_para(ctx, f"{step} {note}"), _code(ctx, shown)]
        md.append(f"{step} {note} {ctx.texts['ask_code']}\n\n```text\n{shown}\n```\n\n")
    return "".join(html), "".join(md)


def _catalog_trees(ctx: Ctx, source: dict[str, Any]) -> tuple[str, str]:
    texts = ctx.texts["catalog"]
    rows = [[t["tree"], str(t["policies"])] for t in source["trees"]]
    return (
        _para(ctx, texts["trees_intro"]) + _table(ctx, texts["trees_head"], rows),
        f"{texts['trees_intro']}\n\n" + _md_table(texts["trees_head"], rows),
    )


def _catalog_gates(ctx: Ctx, source: dict[str, Any]) -> tuple[str, str]:
    texts = ctx.texts["catalog"]
    rows = [
        [g["job"], g["if"] or texts["gates_always"], "; ".join(g["steps"])]
        for g in source["gates"]
    ]
    return (
        _para(ctx, texts["gates_intro"]) + _table(ctx, texts["gates_head"], rows),
        f"{texts['gates_intro']}\n\n" + _md_table(texts["gates_head"], rows),
    )


def _catalog_regen(ctx: Ctx, source: dict[str, Any]) -> tuple[str, str]:
    texts = ctx.texts["catalog"]
    regen = source["regen"]
    items = [f"`{script}`" for script in regen["scripts"]]
    return (
        _para(ctx, texts["regen_intro"])
        + _code(ctx, regen["doc"])
        + _para(ctx, texts["regen_scripts"])
        + _list(ctx, items),
        f"{texts['regen_intro']} {ctx.texts['ask_code']}\n\n```text\n{regen['doc']}\n```\n\n"
        f"{texts['regen_scripts']}\n\n" + "".join(f"- {item}\n" for item in items),
    )


def _catalog(ctx: Ctx, body: Body) -> None:
    """A catalog page: its `catalog` parts in order (data/docs.yaml, DOCS-4)."""
    from . import catalogdoc  # imported here so this block stays in one place

    source = catalogdoc.load(ctx.data_dir, ctx.site.catalog_ref)
    for part in ctx.page["catalog"]:
        if "quote" in part:
            html, md = _catalog_quote(ctx, body, part, source)
            if "heading" not in part:
                body.html.append(html)
                body.md.append(md + "\n")
                continue
        elif "md" in part:
            html, md = _catalog_md(ctx, body, part)
        elif part.get("run"):
            html, md = _catalog_run(ctx, source)
        elif part.get("trees"):
            html, md = _catalog_trees(ctx, source)
        elif part.get("gates"):
            html, md = _catalog_gates(ctx, source)
        elif part.get("regen"):
            html, md = _catalog_regen(ctx, source)
        else:
            raise PageError(f"docs.yaml: unknown catalog part {sorted(part)}")
        _section(ctx, body, part["heading"], html, md)


BLOCKS["catalog"] = _catalog


# --- DOCS-5: the Write policies pages, from data/write-source/ (sitegen/writedoc.py) ---


def _writing_run(ctx: Ctx, name: str, runs: dict[str, Any]) -> tuple[str, str]:
    """One recorded run: each step's note, command, output and exit code."""
    texts = ctx.texts["write"]
    if name not in runs:
        raise PageError(f"docs.yaml write run {name!r} has no recording")
    examples = runs[name]["examples"]
    notes = texts["run_notes"][name]
    if len(notes) != len(examples):
        raise PageError(f"docs.yaml texts.write.run_notes.{name}: one note per step")
    setup = data_fill(texts["run_setup"], {"__SCRIPT__": texts["run_script"]})
    html, md = [_para(ctx, setup)], [f"{setup}\n\n"]
    for note, example in zip(notes, examples, strict=True):
        step = data_fill(
            texts["run_step"],
            {"__STEP__": str(example["step"]), "__EXIT__": str(example["exit"])},
        )
        shown = f"$ {example['command']}"
        if example["output"]:
            shown += f"\n{example['output']}"
        html += [_para(ctx, f"{step} {note}"), _code(ctx, shown)]
        md.append(f"{step} {note} {ctx.texts['ask_code']}\n\n```text\n{shown}\n```\n\n")
    return "".join(html), "".join(md)


def _writing_rows(ctx: Ctx, rows: list[dict[str, Any]]) -> tuple[str, str]:
    """Schema rows as one table: field, type, required, allowed values, the schema's description."""
    texts = ctx.texts["write"]
    head = texts["schema_head"]
    yes, no = texts["schema_required"]
    html_rows: list[list[str | Safe]] = []
    md_rows = []
    for row in rows:
        required = yes if row["required"] else no
        allowed = row["allowed"]
        # A JSON type name stays as the schema spells it; a phrase ("array of string") is prose.
        kind = sentence_start(row["type"]) if " " in row["type"] else row["type"]
        description = sentence_start(row["description"])
        if row["pattern"]:
            # The dist check reads a backslash between name characters as a Windows path.
            shown = (
                texts["schema_pattern_file"]
                if "\\" in row["pattern"]
                else data_fill(texts["schema_pattern"], {"__PATTERN__": row["pattern"]})
            )
            allowed = "; ".join(p for p in (allowed, shown) if p)
        allowed = sentence_start(allowed)
        html_rows.append(
            [
                Safe(ctx.t("cli-code", TEXT=row["field"])),
                kind,
                required,
                Prose(allowed),
                _agentseam_breakable(ctx, description),
            ]
        )
        md_rows.append(
            [
                md_code(row["field"]),
                md_escape(kind),
                required,
                md_escape(allowed),
                md_escape(description),
            ]
        )
    return _table(ctx, head, html_rows), _md_table(head, md_rows)


def _writing_schema(ctx: Ctx, body: Body, part: dict[str, Any]) -> None:
    """A schema reference: its top-level fields, then one h3 per object field with every field under it."""
    from . import writedoc  # imported here so this block stays in one place

    texts = ctx.texts["write"]
    name = part["schema"]
    schema, store = engine.engine_schemas(name)
    rows = writedoc.schema_rows(schema, store)
    path = texts["schema_dir"] + name
    url = _engine_url(ctx, path)
    intro = data_fill(texts["schema_intro"], {"__FILE__": name})
    source = ctx.t("line-link", LINE=texts["schema_source"], URL=url, LINK=path)
    top = [r for r in rows if "." not in r["field"] and "[" not in r["field"]]
    h, m = _writing_rows(ctx, top)
    html = [_para(ctx, intro), source, h]
    md = [f"{intro}\n\n{texts['schema_source']} [{path}]({url})\n\n{m}\n"]
    for parent in top:
        under = [
            r
            for r in rows
            if r["field"].startswith(parent["field"] + ".")
            or r["field"].startswith(parent["field"] + "[]")
        ]
        if not under:
            continue
        h, m = _writing_rows(ctx, under)
        # A schema field is an identifier: its heading renders as code.
        heading = md_code(parent["field"])
        html += [_h3(ctx, body, heading), h]
        md.append(f"### {heading}\n\n{m}\n")
    _section(ctx, body, part["heading"], "".join(html), "".join(md))


def _writing(ctx: Ctx, body: Body) -> None:
    """A Write policies page: its `write` parts in order (data/docs.yaml, DOCS-5)."""
    from . import writedoc

    runs = writedoc.load(ctx.data_dir, ctx.site.framework_ref)
    for part in ctx.page["write"]:
        if "quote" in part:
            _prose(ctx, body, {"file": part["quote"], "sections": part["sections"]})
            continue
        if "schema" in part:
            _writing_schema(ctx, body, part)
            continue
        if "md" in part:
            html, md = _catalog_md(ctx, body, part)
        elif "run" in part:
            html, md = _writing_run(ctx, part["run"], runs)
        else:
            raise PageError(f"docs.yaml: unknown write part {sorted(part)}")
        _section(ctx, body, part["heading"], html, md)


BLOCKS["write"] = _writing


# --- DOCS-6: a page's video, rendered by VHS from videos/<name>.tape (sitegen/videos.py) ---


def _video(ctx: Ctx, body: Body) -> None:
    """The page's video, then what it was recorded with and every command it shows, from its tape."""
    from . import videos  # imported here so this block stays in one place

    texts = ctx.texts["videos"]
    name = ctx.page["video"]
    words = texts["items"][name]
    record = videos.load(videos.ROOT, name)
    tape = (videos.ROOT / record["tape"]).read_text(encoding="utf-8")
    shown = "\n".join(videos.shown_commands(tape))
    src, poster = videos.site_path(record["mp4"]), videos.site_path(record["poster"])
    size = f"{record['mp4_bytes'] / 1_000_000:.1f} MB"
    download = data_fill(texts["download"], {"__SIZE__": size})
    figure = ctx.t(
        "video",
        TITLE=words["title"],
        SRC=src,
        POSTER=poster,
        WIDTH=str(record["width"]),
        HEIGHT=str(record["height"]),
        DOWNLOAD=download,
        DESCRIPTION=words["description"],
        DURATION=record["duration"],
    )
    engine = record["engine"]
    made = data_fill(
        texts["catalog_made" if record["catalog"] else "made"],
        {
            "__TAPE__": record["tape"],
            "__ENGINE__": engine[:12],
            "__CATALOG__": (record["catalog"] or "")[:12],
        },
    )
    made = f"{made} {words['setup']}"
    tape_url = data_fill(
        BLOB_URL,
        {"__REPO__": texts["repo"], "__REF__": "main", "__PATH__": record["tape"]},
    )
    html = [
        figure,
        _para(ctx, made),
        ctx.t("line-link", LINE=texts["tape_link"], URL=tape_url, LINK=record["tape"]),
        _code(ctx, shown, "bash"),
    ]
    site = ctx.site.data["site_url"]
    md = [
        (
            f"{words['title']}: {words['description']} ({record['duration']}) "
            f"[{download}]({site}{src})\n\n"
        ),
        f"{made}\n\n{texts['tape_link']} [{record['tape']}]({tape_url})\n\n",
        f"{ctx.texts['ask_code']}\n\n```bash\n{shown}\n```\n",
    ]
    _section(ctx, body, texts["heading"], "".join(html), "".join(md))


BLOCKS["video"] = _video
