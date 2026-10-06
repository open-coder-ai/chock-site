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
    note = (
        ""
        if block["graded"]
        else render_file(
            templates / "builder-grades-note.html", NOTE=texts["grades_pending"]
        )
    )
    return render_file(
        templates / "builder-clients.html",
        LEGEND=texts["legend"],
        OPTIONS=Safe(options),
        GRADES_NOTE=Safe(note),
    )


def untested_lines(block: dict[str, Any], templates: Path) -> str:
    """The "untested in <client>" line with the checklist link, one per untested client."""
    return "".join(
        render_file(
            templates / "builder-untested.html",
            ID=client,
            HIDDEN=_hidden(client, block["default"]),
            LABEL=data["untested_label"],
            LINE=Prose(data["untested_line"]),
            CHECKLIST=block["checklist"],
            CHECKLIST_TEXT=block["texts"]["checklist"],
        )
        for client in block["order"]
        if (data := block["clients"][client])["witness"] == "untested"
    )


def _step(templates: Path, step: dict[str, str]) -> str:
    """One apply step: a command to type, a note to read or settings to paste."""
    (kind, text), *_ = step.items()
    if kind not in STEP_KINDS:
        raise ValueError(f"unknown step kind {kind!r}")
    return render_file(templates / f"builder-step-{kind}.html", **{kind.upper(): text})


def steps(block: dict[str, Any], templates: Path) -> str:
    """Each client's apply steps after the command, shown for the picked client only."""
    return "".join(
        render_file(
            templates / "builder-steps.html",
            ID=client,
            HIDDEN=_hidden(client, block["default"]),
            HEADING=block["clients"][client]["steps_heading"],
            STEPS=Safe(
                "".join(_step(templates, s) for s in block["clients"][client]["steps"])
            ),
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
        if state == "untested":
            lines.append(
                f"{data['untested_label']} {data['untested_line']} "
                f"[{block['texts']['checklist']}]({block['checklist']})\n\n"
            )
        lines.append(
            f"{block['texts']['command_md']}\n\n    {command}\n\n{data['steps_heading']}\n\n"
        )
        for number, step in enumerate(data["steps"], start=1):
            (kind, text), *_ = step.items()
            if kind == "note":
                lines.append(f"{number}. {text}\n")
            else:
                body = "".join(f"       {line}\n" for line in text.splitlines())
                lines.append(f"{number}. ({kind})\n\n{body}\n")
        lines.append("\n")
    return "".join(lines)
