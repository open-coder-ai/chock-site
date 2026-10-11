"""The builder's agent picker and per-client install panels, as HTML and Markdown (BV-S1)."""

from pathlib import Path
from typing import Any

from .pageparts import data_fill
from .render import Prose, Safe, render_file

STEP_KINDS = ("command", "note", "settings")


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
            STATE_WORD=texts[block["clients"][client]["witness"]],
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
        )
        for client in block["order"]
    )


def markdown(block: dict[str, Any]) -> str:
    """The agents section of the builder's Markdown twin: command form, state and steps per agent."""
    commands = block["commands"]
    lines = []
    for client in block["order"]:
        data = block["clients"][client]
        state = data["witness"]
        command = data_fill(
            commands[state], {"__CLIENT__": client, "__CODE__": "<code>"}
        )
        lines.append(f"### {data['name']} (`{client}`, {block['texts'][state]})\n\n")
        if not data["graded"]:
            lines.append(f"{data['ungraded_note']}\n\n")
        if state == "untested":
            lines.append(
                f"{data['untested_label']} {data['untested_line']} "
                f"[{block['texts']['report']}]({data['report']}).\n\n"
            )
        lines.append(
            f"{block['texts']['command_md']}\n\n    {command}\n\n{data['steps_heading']}\n\n"
        )
        number = 0
        for item in data["steps"]:
            (kind, text), *_ = item.items()
            if kind == "command":
                number += 1
                lines.append(f"{number}. (command)\n\n       {text}\n\n")
            elif kind == "note":
                lines.append(f"{text}\n\n")
            else:
                lines.extend(f"    {line}\n" for line in text.splitlines())
                lines.append("\n")
        lines.append(f"\n{block['texts']['remove_md']}\n\n")
        for step in data["remove"]:
            (kind, text), *_ = step.items()
            lines.append(f"- {text}\n" if kind == "note" else f"- `{text}`\n")
        lines.append(f"\n{block['texts']['repo_line']} {data['plugin_repo']}\n\n")
    return "".join(lines)
