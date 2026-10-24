"""The builder's agent picker and per-client install panels, as HTML and Markdown (BV-S1)."""

import re
from pathlib import Path
from typing import Any

from . import engine
from .pageparts import data_fill
from .render import Prose, Safe, render_file, sentence_start

STEP_KINDS = ("command", "note", "settings")
# A sentence and its closing punctuation, for the agent-facing ask in Markdown notes.
SENTENCE_RE = re.compile(r".+?(?:[.!?]+(?=\s|$)|$)", re.DOTALL)
INSTALL_WORDS = "chock install"


def agent_note(text: str, ask: str) -> str:
    """An engine note for agents: each sentence naming `chock install` gets the site's ask before its stop."""

    def _ask(match: re.Match) -> str:
        sentence = match.group(0)
        if INSTALL_WORDS not in sentence or "ask" in sentence.lower():
            return sentence
        body = sentence.rstrip(".!?")
        return f"{body}{ask}{sentence[len(body) :]}"

    return SENTENCE_RE.sub(_ask, text)


def _hidden(client: str, shown: str) -> Safe:
    """The `hidden` attribute for every client but the one shown before builder.js runs."""
    return Safe("" if client == shown else " hidden")


def picker(block: dict[str, Any], templates: Path) -> str:
    """The radio group that picks the agent, with each one's witness state."""
    texts = block["texts"]
    options = "".join(
        render_file(
            templates / "builder-client.html",
            ID=client,
            CHECKED=Safe(" checked" if client == block["default"] else ""),
            NAME=block["clients"][client]["name"],
            STATE=block["clients"][client]["witness"],
            STATE_WORD=sentence_start(texts[block["clients"][client]["witness"]]),
        )
        for client in block["order"]
    )
    note = "".join(
        render_file(
            templates / "builder-grades-note.html",
            ID=client,
            HIDDEN=_hidden(client, block["default"]),
            NOTE=data["ungraded_note"],
        )
        for client in block["order"]
        if not (data := block["clients"][client])["graded"]
    )
    return render_file(
        templates / "builder-clients.html",
        LEGEND=texts["legend"],
        OPTIONS=Safe(options),
        GRADES_NOTE=Safe(note),
    )


def untested_lines(block: dict[str, Any], templates: Path) -> str:
    """The "untested in <client>" line with the report link, one per untested client."""
    return "".join(
        render_file(
            templates / "builder-untested.html",
            ID=client,
            HIDDEN=_hidden(client, block["default"]),
            LABEL=data["untested_label"],
            LINE=Prose(data["untested_line"]),
            REPORT=data["report"],
            REPORT_TEXT=block["texts"]["report"],
        )
        for client in block["order"]
        if (data := block["clients"][client])["witness"] == "untested"
    )


def evidence_line(
    block: dict[str, Any], templates: Path, client: str, hidden: str = ""
) -> str:
    """The "evidence wanted" notice for one client, or "" without an evidence row (S-EV)."""
    notice = block["clients"][client]["evidence"]
    if notice is None:
        return ""
    return render_file(
        templates / "builder-evidence.html",
        ID=client,
        HIDDEN=Safe(hidden),
        LABEL=notice["label"],
        LINE=Prose(notice["line"]),
        URL=notice["url"],
        LINK=notice["link"],
    )


def evidence_lines(block: dict[str, Any], templates: Path) -> str:
    """The builder's evidence notices, one per client with an evidence row, shown when picked."""
    return "".join(
        evidence_line(block, templates, client, _hidden(client, block["default"]))
        for client in block["order"]
    )


def step(templates: Path, step: dict[str, str]) -> str:
    """One apply step: a command to type, a note to read or settings to paste."""
    (kind, text), *_ = step.items()
    if kind not in STEP_KINDS:
        raise ValueError(f"unknown step kind {kind!r}")
    value = Prose(text) if kind == "note" else text
    return render_file(templates / f"builder-step-{kind}.html", **{kind.upper(): value})


def step_blocks(templates: Path, steps: list[dict[str, str]]) -> str:
    """Steps in engine order: runs of commands as numbered lists, notes and settings unnumbered."""
    blocks: list[str] = []
    run: list[str] = []
    number = 1
    for item in steps:
        (kind, _), *_ = item.items()
        html = step(templates, item)
        if kind == "command":
            run.append(html)
            continue
        if run:
            blocks.append(_step_list(templates, number, run))
            number += len(run)
            run = []
        blocks.append(html)
    if run:
        blocks.append(_step_list(templates, number, run))
    return "".join(blocks)


def _step_list(templates: Path, start: int, items: list[str]) -> str:
    """A numbered list of command steps, counting on from `start`."""
    return render_file(
        templates / "builder-step-list.html",
        START=str(start),
        ITEMS=Safe("".join(items)),
    )


def steps(block: dict[str, Any], templates: Path) -> str:
    """Each client's apply steps after the command, shown for the picked client only."""
    return "".join(
        render_file(
            templates / "builder-steps.html",
            ID=client,
            HIDDEN=_hidden(client, block["default"]),
            HEADING=block["clients"][client]["steps_heading"],
            STEPS=Safe(step_blocks(templates, block["clients"][client]["steps"])),
            CLAUDE_PLUGIN=Safe(claude_plugin(block, templates, client)),
        )
        for client in block["order"]
    )


def claude_plugin(block: dict[str, Any], templates: Path, client: str) -> str:
    """chock's Claude Code plugin option for one agent: its routes, steps and warnings, or why not."""
    offer = block["clients"][client]["claude_plugin"]
    if offer is None:
        return ""
    if "not_offered" in offer:
        return render_file(
            templates / "claude-plugin-none.html",
            NOT_OFFERED=Prose(offer["not_offered"]),
        )
    texts = block["texts"]
    routes = "".join(
        render_file(
            templates / "claude-plugin-route.html",
            WHERE=route["where"],
            LABEL=route["label"],
            LEAD=Safe(
                step_blocks(templates, [{"note": route["prefer_native"]}])
                if route["prefer_native"]
                else ""
            ),
            BUILD=Safe(
                _build_line(templates, route["build"], texts["code_placeholder"])
            ),
            STEPS=Safe(step_blocks(templates, route["steps"])),
        )
        for route in offer["routes"]
    )
    warnings = "".join(
        render_file(
            templates / "claude-plugin-warning.html",
            LABEL=texts["claude_plugin_warning"],
            WARNING=Prose(warning),
        )
        for warning in offer["warnings"]
    )
    return render_file(
        templates / "claude-plugin.html",
        HEADING=texts["claude_plugin_heading"],
        INTRO=Prose(offer["heading"]),
        ROUTES=Safe(routes),
        WARNINGS=Safe(warnings),
    )


def _build_line(templates: Path, build: str, placeholder: str) -> str:
    """chock's build line with a slot builder.js fills with the selection code; elsewhere the placeholder."""
    parts = build.split(engine.SELECTION_TOKEN)
    if len(parts) != 2:
        raise ValueError(f"build line needs one {engine.SELECTION_TOKEN}: {build!r}")
    before, after = parts
    return render_file(
        templates / "claude-plugin-build.html",
        BEFORE=before,
        CODE=placeholder,
        AFTER=after,
    )


def claude_route_steps(route: dict[str, Any], code: str) -> list[dict[str, str]]:
    """A route's notes and steps in chock's order: the native-plugin advice, the build line, the steps."""
    lead = [route["prefer_native"]] if route["prefer_native"] else []
    build = data_fill(route["build"], {engine.SELECTION_TOKEN: code})
    return [{"note": text} for text in [*lead, build]] + route["steps"]


def code_hint(block: dict[str, Any]) -> str:
    """The line under a command form that says what replaces the selection code placeholder."""
    texts = block["texts"]
    return data_fill(texts["code_hint"], {"__CODE__": texts["code_placeholder"]})


def markdown(block: dict[str, Any]) -> str:
    """The agents section of the builder's Markdown twin: command form, state and steps per agent."""
    commands = block["commands"]
    lines = []
    for client in block["order"]:
        data = block["clients"][client]
        state = data["witness"]
        command = data_fill(
            commands[state],
            {"__CLIENT__": client, "__CODE__": block["texts"]["code_placeholder"]},
        )
        lines.append(f"### {data['name']} (`{client}`, {block['texts'][state]})\n\n")
        if not data["graded"]:
            lines.append(f"{data['ungraded_note']}\n\n")
        if state == "untested":
            lines.append(
                f"{data['untested_label']} {data['untested_line']} "
                f"[{block['texts']['report']}]({data['report']}).\n\n"
            )
        if notice := data["evidence"]:
            lines.append(
                f"{notice['label']} {notice['line']} "
                f"[{notice['link']}]({notice['url']}).\n\n"
            )
        lines.append(
            f"{block['texts']['command_md']}\n\n    {command}\n\n"
            f"{code_hint(block)} [{block['texts']['code_hint_link']}]"
            f"(/coding/builder/#client={client}).\n\n{data['steps_heading']}\n\n"
        )
        lines.append(md_steps(data["steps"], block["texts"]["ask_inline"]))
        lines.append(f"\n{block['texts']['remove_md']}\n\n")
        for step in data["remove"]:
            (kind, text), *_ = step.items()
            lines.append(f"- {text}\n" if kind == "note" else f"- `{text}`\n")
        if unverified := data["remove_unverified"]:
            lines.append(
                f"- {unverified['text']} [{unverified['link']}]({unverified['url']}).\n"
            )
        if data["plugin_repo"]:
            lines.append(
                f"\n{block['texts']['repo_line']} {data['plugin_repo']}\n\n"
                f"{block['texts']['repo_note']}\n"
            )
        lines.append(_md_claude_plugin(block, data["claude_plugin"]))
        lines.append("\n")
    return "".join(lines)


def md_steps(steps: list[dict[str, str]], ask: str) -> str:
    """Steps for the Markdown twin: numbered commands, notes with the ask, settings indented."""
    lines = []
    number = 0
    for item in steps:
        (kind, text), *_ = item.items()
        if kind == "command":
            number += 1
            lines.append(f"{number}. (command)\n\n   ```sh\n   {text}\n   ```\n\n")
        elif kind == "note":
            lines.append(f"{agent_note(text, ask)}\n\n")
        else:
            lines.extend(f"    {line}\n" for line in text.splitlines())
            lines.append("\n")
    return "".join(lines)


def _md_claude_plugin(block: dict[str, Any], offer: dict[str, Any] | None) -> str:
    """The Claude Code plugin option in the Markdown twin, or chock's reason it offers none."""
    if offer is None:
        return ""
    if "not_offered" in offer:
        return f"\n{offer['not_offered']}\n"
    texts = block["texts"]
    lines = [f"\n#### {texts['claude_plugin_heading']}\n\n{offer['heading']}\n\n"]
    for route in offer["routes"]:
        lines.append(f"{route['where']}: {route['label']}\n\n")
        lines.append(
            md_steps(
                claude_route_steps(route, f"`{texts['code_placeholder']}`"),
                texts["ask_inline"],
            )
        )
    lines.extend(
        f"{texts['claude_plugin_warning']} {warning}\n\n"
        for warning in offer["warnings"]
    )
    return "".join(lines)
