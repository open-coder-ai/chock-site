"""Every agent agentseam records, with the plugin and repo-hooks routes chock offers it (S-ALL)."""

from pathlib import Path
from typing import Any

import yaml

from . import engine
from .pageparts import PageError, data_fill
from .render import Prose, Safe, render_file, sentence_start

ROUTES_YAML = "routes.yaml"
REASONS = (
    engine.UNWIRED_HOOK_DIR,
    engine.UNWIRED_HOME_CONFIG,
    engine.UNWIRED_NO_HOOKS,
    engine.UNWIRED_UNADAPTED,
)
WITNESSED = "witnessed"
UNTESTED = "untested"


def load_routes(data_dir: Path) -> dict[str, Any]:
    """data/routes.yaml, checked: every install client mapped once to a matrix agent, every reason worded."""
    data = yaml.safe_load((data_dir / ROUTES_YAML).read_text(encoding="utf-8"))
    agents = engine.matrix_agents()
    plugins = data["plugins"]
    if sorted(plugins) != sorted(engine.client_ids()):
        raise PageError(
            f"{ROUTES_YAML}: plugins {sorted(plugins)} != engine {sorted(engine.client_ids())}"
        )
    for client, agent in plugins.items():
        if agent not in agents:
            raise PageError(f"{ROUTES_YAML}: {client} maps to {agent!r}, not an agent")
    if len(set(plugins.values())) != len(plugins):
        raise PageError(f"{ROUTES_YAML}: two clients map to one agent")
    if sorted(data["reasons"]) != sorted(REASONS):
        raise PageError(
            f"{ROUTES_YAML}: reasons {sorted(data['reasons'])} != {REASONS}"
        )
    for agent in data["notes"] or {}:
        if agent not in agents:
            raise PageError(f"{ROUTES_YAML}: note for {agent!r}, not an agent")
    return data


def check_agent_issues(
    evidence: dict[str, Any], routes: dict[str, Any], sync_witnessed: set[str]
) -> None:
    """evidence.yaml's `agents` rows: an agent with no plugin, untested on repo hooks, a positive issue."""
    plugin_agents = set(routes["plugins"].values())
    agents = engine.matrix_agents()
    for agent, number in (evidence.get("agents") or {}).items():
        if agent not in agents:
            raise PageError(f"evidence.yaml: agents row {agent!r} is not an agent")
        if agent in plugin_agents:
            raise PageError(
                f"evidence.yaml: {agent} has a plugin; its row goes under issues"
            )
        if agent in sync_witnessed:
            raise PageError(f"evidence.yaml: {agent} is witnessed on repo hooks")
        if type(number) is not int or number < 1:
            raise PageError(f"evidence.yaml: {agent} issue {number!r} is not a number")


def _issue(evidence: dict[str, Any], number: int | None) -> dict[str, str] | None:
    """An evidence issue's link and words, or None."""
    if number is None:
        return None
    subs = {"__NUMBER__": str(number)}
    return {
        "number": number,
        "url": data_fill(evidence["issue_url"], subs),
        "link": data_fill(evidence["texts"]["link"], subs),
    }


def agent_routes(
    routes: dict[str, Any], evidence: dict[str, Any], clients: dict[str, Any]
) -> dict[str, Any]:
    """The site.json `agent_routes` block: every matrix agent's plugin, repo hooks, reason and record."""
    texts = routes["texts"]
    witness_words = clients["texts"]
    by_agent = {agent: client for client, agent in routes["plugins"].items()}
    wired = engine.sync_vendors()
    sync_witnessed = {a for a in wired if engine.sync_witnessed(a)}
    check_agent_issues(evidence, routes, sync_witnessed)
    rows = []
    for agent, name in engine.matrix_agents().items():
        client = by_agent.get(agent)
        plugin = None
        number = (evidence.get("agents") or {}).get(agent)
        if client is not None:
            state = clients["clients"][client]["witness"]
            plugin = {
                "client": client,
                "name": clients["clients"][client]["name"],
                "witness": state,
                "word": witness_words[state],
                "link": data_fill(texts["plugin_link"], {"__CLIENT__": client}),
            }
            number = (evidence["issues"] or {}).get(client)
        sync = None
        reason = None
        if agent in wired:
            state = WITNESSED if agent in sync_witnessed else UNTESTED
            sync = {
                "agents": engine.sync_agent_name(agent),
                "command": data_fill(
                    texts["sync_command"], {"__AGENT__": engine.sync_agent_name(agent)}
                ),
                "witness": state,
                "word": witness_words[state],
            }
        else:
            reason = routes["reasons"][engine.unwired_reason(agent)]
        row = engine.tier_row(agent)
        route = (
            ("both" if sync else "plugin") if plugin else ("sync" if sync else "none")
        )
        rows.append(
            {
                "agent": agent,
                "name": name,
                "route": route,
                "route_text": texts["routes"][route],
                "plugin": plugin,
                "sync": sync,
                "reason": reason,
                "record": data_fill(
                    texts["record"],
                    {
                        "__TIER__": row["tier"],
                        "__GRADE__": row["grade"],
                        "__FAIL__": row["fail_mode"],
                        "__BASIS__": row["basis"],
                        "__DATE__": row["recorded"],
                    },
                ),
                "evidence": _issue(evidence, number),
                "note": (routes["notes"] or {}).get(agent),
            }
        )
    return {"texts": texts, "agents": rows}


def _plugin_cell(templates: Path, row: dict[str, Any], texts: dict[str, str]) -> str:
    """The plugin cell: the client's install section and its witness state, or "no plugin"."""
    plugin = row["plugin"]
    if plugin is None:
        return render_file(templates / "route-none.html", TEXT=texts["no_plugin"])
    return render_file(
        templates / "route-plugin.html",
        CLIENT=plugin["client"],
        LINK=plugin["link"],
        STATE=plugin["witness"],
        WORD=sentence_start(plugin["word"]),
    )


def _sync_cell(templates: Path, row: dict[str, Any]) -> str:
    """The repo-hooks cell: the sync command and its witness state, or the reason it is not wired."""
    sync = row["sync"]
    if sync is None:
        return render_file(templates / "route-none.html", TEXT=row["reason"])
    return render_file(
        templates / "route-sync.html",
        COMMAND=sync["command"],
        STATE=sync["witness"],
        WORD=sentence_start(sync["word"]),
    )


def _record_cell(templates: Path, row: dict[str, Any]) -> str:
    """agentseam's pre-tool record, then the evidence link and the cited note when there are any."""
    extra = ""
    if row["evidence"]:
        extra += render_file(
            templates / "route-evidence.html",
            URL=row["evidence"]["url"],
            LINK=row["evidence"]["link"],
        )
    if row["note"]:
        extra += render_file(
            templates / "route-note.html",
            TEXT=row["note"]["text"],
            SOURCE=Prose(row["note"]["source"]),
        )
    return render_file(
        templates / "route-record.html",
        RECORD=sentence_start(row["record"]),
        EXTRA=Safe(extra),
    )


def section(block: dict[str, Any], templates: Path) -> str:
    """The install page's "Every agent" table."""
    texts = block["texts"]
    rows = "".join(
        render_file(
            templates / "route-row.html",
            AGENT=row["agent"],
            NAME=row["name"],
            ROUTE=row["route"],
            ROUTE_TEXT=row["route_text"],
            PLUGIN=Safe(_plugin_cell(templates, row, texts)),
            SYNC=Safe(_sync_cell(templates, row)),
            RECORD=Safe(_record_cell(templates, row)),
        )
        for row in block["agents"]
    )
    return render_file(
        templates / "install-routes.html",
        HEADING=texts["heading"],
        INTRO=Prose(texts["intro"]),
        COL_AGENT=texts["col_agent"],
        COL_PLUGIN=texts["col_plugin"],
        COL_SYNC=texts["col_sync"],
        COL_RECORD=texts["col_record"],
        ROWS=Safe(rows),
    )


def builder_line(block: dict[str, Any], templates: Path) -> str:
    """The builder's pointer to the install page's "Every agent" table."""
    texts = block["texts"]
    return render_file(
        templates / "builder-routes.html",
        LINE=texts["builder_line"],
        LINK=texts["builder_link"],
    )


def markdown(block: dict[str, Any]) -> str:
    """The "Every agent" section of the install page's Markdown twin."""
    texts = block["texts"]
    lines = [f"## {texts['heading']}\n\n{texts['intro']}\n\n"]
    for row in block["agents"]:
        lines.append(f"### {row['name']} (`{row['agent']}`)\n\n{row['route_text']}\n\n")
        plugin = row["plugin"]
        if plugin is None:
            lines.append(f"- {texts['md_plugin']} {texts['no_plugin']}\n")
        else:
            lines.append(
                f"- {texts['md_plugin']} `chock install --client {plugin['client']}`, "
                f"{plugin['word']}.\n"
            )
        sync = row["sync"]
        if sync is None:
            lines.append(f"- {texts['md_sync']} {row['reason']}\n")
        else:
            lines.append(f"- {texts['md_sync']} `{sync['command']}`, {sync['word']}.\n")
        lines.append(f"- {texts['md_record']} {sentence_start(row['record'])}\n")
        if row["evidence"]:
            link = sentence_start(row["evidence"]["link"])
            lines.append(f"- [{link}]({row['evidence']['url']})\n")
        if row["note"]:
            lines.append(
                f"- {row['note']['text']} ({texts['md_source']} {row['note']['source']})\n"
            )
        lines.append("\n")
    return "".join(lines)
