"""The only module that imports chock (and agentseam): hashes, labels, schema, warnings, routes."""

import base64
import importlib.resources
import json
import re
import shlex
from pathlib import Path
from typing import Any

import chock.evidence
import chock.hooks.sync_notes
import chock.install.package
import chock.install.place
import chock.install.resolve
import chock.install.selection
import chock.install.steps
import chock.lock
import chock.vendors
from agentseam import matrix as agentseam_matrix
from agentseam import tier_table as agentseam_tiers
from chock.validation.loading import load_schema

INSTALL_JSON = "data/install.json"
WARNINGS_JSON = "data/warnings.json"
SelectionError = chock.install.selection.SelectionError
SCHEMA2 = chock.install.selection.SCHEMA2
CATALOG_ENTRY = chock.install.selection.CATALOG
BUNDLE_NAME = chock.install.selection.DEFAULT_BUNDLE
# Why `chock sync` does not wire an agent, keyed as data/routes.yaml words it (S-ALL).
UNWIRED_HOOK_DIR = "hook_dir"
UNWIRED_HOME_CONFIG = "home_config"
UNWIRED_NO_HOOKS = "no_hooks"
UNWIRED_UNADAPTED = "unadapted"
# What agentseam prints where an agent has no hook surface at all.
NOT_APPLICABLE = agentseam_tiers.NOT_APPLICABLE
# An argument shown as is: shell-safe characters, with a leading ~ kept for the shell to expand.
PLAIN_ARG = re.compile(r"~?[\w@%+=:,./-]+")


def _resource(name: str) -> dict[str, Any]:
    return json.loads(
        importlib.resources.files("chock.install")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def pack_hash(pack_dir: Path) -> str:
    """The sha256 `chock add --verify-sha` and `chock install` check for one policy."""
    return chock.lock.compute_pack_hash(pack_dir)


def label_words() -> dict[str, str]:
    """The engine's label keywords mapped to their displayed words."""
    return _resource(INSTALL_JSON)["labels"]


def warning_rules() -> list[dict[str, Any]]:
    """The engine's warning rules for policy combinations."""
    return _resource(WARNINGS_JSON)["rules"]


def build_selection(
    picks: list[dict[str, str]],
    catalog_source: str,
    catalog_ref: str,
    release: str | None = None,
    preset: str | None = None,
) -> dict[str, Any]:
    """A schema-1 selection object in the engine's key order (plan 8.1)."""
    catalog: dict[str, Any] = {"source": catalog_source, "ref": catalog_ref}
    if release is not None:
        catalog["release"] = release
    selection: dict[str, Any] = {
        "schema": 1,
        "client": "claude-code",
        "catalog": catalog,
    }
    if preset is not None:
        selection["preset"] = preset
    selection["policies"] = sorted(picks, key=lambda p: p["id"])
    return selection


def build_selection_v2(
    picks: list[dict[str, str]],
    catalog_source: str,
    catalog_ref: str,
    client: str,
    bundle_version: str,
    release: str | None = None,
    preset: str | None = None,
) -> dict[str, Any]:
    """A schema-2 selection of catalog policies for one client, in the schema's key order."""
    catalog: dict[str, Any] = {"source": catalog_source, "ref": catalog_ref}
    if release is not None:
        catalog["release"] = release
    selection: dict[str, Any] = {
        "schema": SCHEMA2,
        "client": client,
        "bundle": {"version": bundle_version},
        "catalog": catalog,
    }
    if preset is not None:
        selection["preset"] = preset
    selection["policies"] = [
        {"from": CATALOG_ENTRY, **pick} for pick in sorted(picks, key=lambda p: p["id"])
    ]
    return selection


def encode_selection(selection: dict[str, Any]) -> str:
    """The share code: base64url of compact UTF-8 JSON, no padding (plan 8.2)."""
    raw = json.dumps(selection, separators=(",", ":"), ensure_ascii=False)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def policy_labels(catalog: Path, selection: dict[str, Any]) -> dict[str, Any]:
    """Each selected policy's Label (policy_id, keyword, says, description) on the selection's client."""
    members = chock.install.resolve.members(catalog, selection)
    return {
        label.policy_id: label
        for label in chock.install.package.labels(members, catalog, selection["client"])
    }


def client_ids() -> list[str]:
    """The ids of every client `chock install --client` accepts."""
    return list(chock.install.package.settings()["clients"])


def client_name(client: str) -> str:
    """The client's display name from the engine's install data."""
    return chock.install.package.client(client)["name"]


def _shell_line(argv: list[str]) -> str:
    """An argv as one line to type: unsafe arguments quoted, a leading ~ left unquoted."""
    return " ".join(
        arg if PLAIN_ARG.fullmatch(arg) else shlex.quote(arg) for arg in argv
    )


def client_tokens(client: str) -> dict[str, str]:
    """The tokens `chock install` fills in a client's steps, for the default folder and bundle."""
    dest = Path(chock.install.package.client(client)["dest"])
    folder = chock.install.place.plugin_dir(client, dest, BUNDLE_NAME)
    return {
        "__DEST__": dest.as_posix(),
        "__PLUGIN_DIR__": Path(folder).as_posix(),
        "__PLUGIN__": BUNDLE_NAME,
        "__MARKETPLACE__": chock.install.package.settings()["marketplace"],
    }


def client_steps(client: str) -> list[dict[str, str]]:
    """The client's apply steps as `chock install` prints them for the default folder and bundle.

    Each step is {"command": a line to type}, {"note": text to read} or {"settings": JSON to paste}.
    """
    raw = chock.install.package.client(client)["steps"]
    rendered = chock.install.steps.render(client, client_tokens(client))
    return [
        {"command": _shell_line(step.command)}
        if step.command
        else {("settings" if "settings" in source else "note"): step.text}
        for source, step in zip(raw, rendered, strict=True)
    ]


def check_selection(obj: dict[str, Any]) -> dict[str, Any]:
    """The selection if it matches the engine's schema, else SelectionError."""
    return chock.install.selection.check(obj)


def load_selection(arg: str) -> dict[str, Any]:
    """The checked selection named by a file path, a URL with #s=..., or a bare code, as schema 2."""
    return chock.install.selection.load(arg)


def selection_schema() -> dict[str, Any]:
    """The engine's selection schema, served at /api/selection.schema.json."""
    return load_schema(chock.install.selection.SCHEMA)


def stop_agents() -> tuple[str, ...]:
    """The agents whose end of turn `chock sync` also gates."""
    return chock.vendors.stop_vendors()


def _data(name: str) -> Any:
    return json.loads(
        importlib.resources.files("chock")
        .joinpath("data", name)
        .read_text(encoding="utf-8")
    )


def ask_claims() -> list[dict[str, Any]]:
    """The engine's tested claims about which agents honour an `ask` verdict."""
    return [row for row in _data("claims.json") if row["claim"] == "honours_ask"]


def hook_timeouts() -> dict[str, dict[str, Any]]:
    """The engine's recorded hook timeout per agent, with the vendor page it comes from."""
    return _data("hook_timeouts.json")


def witness_ledger() -> list[dict[str, Any]]:
    """The engine's witness ledger: one row per agent and surface a person saw fire."""
    return _data("witnesses.json")


def gate_logs() -> dict[str, list[str]]:
    """The decision log files the engine writes per route, current then rotated.

    Sync paths are relative to the repository; plugin paths sit under the user's home.
    """
    import chock.gatelog_read as log

    sync = f".chock/{log.LOG_DIR}"
    plugin = f"~/.chock/{log.LOG_DIR}/<agent>"
    return {
        "sync": [f"{sync}/{log.LOG_NAME}", f"{sync}/{log.ROTATED_NAME}"],
        "plugin": [
            f"{plugin}/{log.PLUGIN_LOG_NAME}",
            f"{plugin}/{log.PLUGIN_ROTATED_NAME}",
        ],
    }


def _help_text(name: str, args: list[str]) -> str:
    """What `chock <name> <args>` prints, at a fixed width of 100 columns."""
    import contextlib
    import io
    import os

    import chock.cli

    saved = os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = "100"
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.suppress(SystemExit):
            chock.cli.COMMANDS[name][0](args)
    finally:
        if saved is None:
            del os.environ["COLUMNS"]
        else:
            os.environ["COLUMNS"] = saved
    return buf.getvalue().rstrip()


def subcommand_help(name: str, sub: str) -> str:
    """The --help text of one subcommand, e.g. `chock witness export --help`."""
    return _help_text(name, [sub, "--help"])


def cli_commands() -> list[dict[str, str]]:
    """Every `chock` command in the engine's groups, with its one-line help and its --help text."""
    groups = json.loads(
        importlib.resources.files("chock")
        .joinpath("data", "commands.json")
        .read_text(encoding="utf-8")
    )
    return [
        {
            "group": group,
            "name": name,
            "summary": spec["help"],
            "help": _help_text(name, ["--help"]),
        }
        for group, commands in groups.items()
        for name, spec in commands.items()
    ]


def matrix_agents() -> dict[str, str]:
    """Every agent agentseam's matrix records, mapped to its display name, in the matrix's order."""
    return {
        agent: str(agentseam_matrix.MATRIX[agent]["display"])
        for agent in agentseam_matrix.agents()
    }


def matrix_row(agent: str) -> dict[str, Any]:
    """The agent's agentseam matrix row: display, tier, config, events and notes."""
    return agentseam_matrix.MATRIX[agent]


def matrix_text(agent: str) -> str:
    """The agent's whole matrix row as JSON text, for checks that cite it."""
    return json.dumps(agentseam_matrix.MATRIX[agent])


def tier_row(agent: str) -> dict[str, str]:
    """agentseam's pre-tool tier row for the agent: tier, grade, fail mode, basis, date."""
    return next(r for r in agentseam_tiers.rows() if r["agent"] == agent)


def sync_vendors() -> tuple[str, ...]:
    """The agents `chock sync --repo` wires a pre-tool hook for."""
    return chock.vendors.in_agent_vendors()


def sync_agent_name(vendor: str) -> str:
    """The first name `chock sync --agents` accepts for the vendor."""
    return next(k for k, v in chock.vendors.CHOCK_AGENT.items() if v == vendor)


def sync_witnessed(vendor: str) -> bool:
    """Whether chock's ledger holds a live run of its repo hooks in the vendor's client."""
    return chock.hooks.sync_notes.witnessed(vendor)


def sync_tier_line(vendor: str) -> str | None:
    """The agentseam row `chock sync` prints for the vendor, or None without one."""
    return chock.hooks.sync_notes.tier_line(vendor)


def unwired_reason(agent: str) -> str:
    """Why `chock sync` does not wire the agent: a hooks folder, a home config, no hooks, no adapter."""
    if agent in sync_vendors():
        raise ValueError(f"{agent} is wired by chock sync")
    try:
        config = chock.vendors.entry(agent)
    except KeyError:
        tier = tier_row(agent)["tier"]
        if tier == agentseam_matrix.TIER_NONE:
            return UNWIRED_NO_HOOKS
        if tier == agentseam_matrix.TIER_UNADAPTED:
            return UNWIRED_UNADAPTED
        raise ValueError(f"{agent}: no adapter, tier {tier!r}") from None
    if config["config_format"] not in chock.vendors.SYNC_FORMATS:
        return UNWIRED_HOOK_DIR
    if not chock.vendors.repo_wirable(agent):
        return UNWIRED_HOME_CONFIG
    raise ValueError(f"{agent}: adapter wirable but not wired")


def plugin_witnessed(agent: str) -> bool:
    """Whether chock's witness ledger holds a plugin-hook row for the agent."""
    return chock.evidence.witness(agent, chock.evidence.PLUGIN_HOOK) is not None


# DOCS-1: the argparse tree behind every `chock` command, for the per-command pages.
CLI_PROG = "chock"
CLI_COLUMNS = "100"


class _Captured(Exception):
    """Raised in place of parsing, carrying the parser a command built."""

    def __init__(self, parser: Any) -> None:
        super().__init__(parser.prog)
        self.parser = parser


def _capture_parser(name: str) -> tuple[Any, str]:
    """The argparse parser `chock <name>` builds, or None, and what `--help` printed if it has none.

    The handler runs with `--help` and sys.argv[0] set to `chock`, as the console script
    runs it; parsing is stopped before it starts, so the command does nothing.
    """
    import argparse
    import contextlib
    import io
    import os
    import sys
    from unittest import mock

    import chock.cli

    def capture(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise _Captured(self)

    saved_argv0, saved_columns = sys.argv[0], os.environ.get("COLUMNS")
    sys.argv[0], os.environ["COLUMNS"] = CLI_PROG, CLI_COLUMNS
    buf = io.StringIO()
    try:
        with (
            mock.patch.object(argparse.ArgumentParser, "parse_known_args", capture),
            mock.patch.object(argparse.ArgumentParser, "parse_args", capture),
            contextlib.redirect_stdout(buf),
            contextlib.suppress(SystemExit),
        ):
            chock.cli.COMMANDS[name][0](["--help"])
    except _Captured as got:
        return got.parser, ""
    finally:
        sys.argv[0] = saved_argv0
        if saved_columns is None:
            del os.environ["COLUMNS"]
        else:
            os.environ["COLUMNS"] = saved_columns
    return None, buf.getvalue().rstrip()


def _cli_argument(parser: Any, action: Any) -> dict[str, Any]:
    """One option or positional argument as argparse declares it."""
    import argparse

    formatter = parser._get_formatter()
    if action.option_strings:
        metavar = formatter._get_default_metavar_for_optional(action)
    else:
        metavar = formatter._get_default_metavar_for_positional(action)
    takes_value = action.nargs != 0
    default = action.default
    shown = takes_value and default is not None and default is not argparse.SUPPRESS
    return {
        "name": ", ".join(action.option_strings)
        or formatter._metavar_formatter(action, metavar)(1)[0],
        "positional": not action.option_strings,
        "value": formatter._format_args(action, metavar)
        if takes_value and action.option_strings
        else "",
        "choices": [str(c) for c in action.choices] if action.choices else [],
        "default": str(default) if shown else "",
        "required": bool(action.required),
        "help": formatter._expand_help(action) if action.help else "",
    }


def _unprefixed(usage: str) -> str:
    """argparse's usage text without "usage: ", its wrapped lines moved left to match."""
    prefix = "usage: "
    first, *rest = usage.removeprefix(prefix).split("\n")
    pad = " " * len(prefix)
    return "\n".join([first, *(line.removeprefix(pad) for line in rest)])


def _cli_node(
    parser: Any, path: list[str], group: str, summary: str
) -> list[dict[str, Any]]:
    """The node for one parser, then its subcommands' nodes, depth first."""
    import argparse
    import os

    saved_prog, saved_columns = parser.prog, os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = CLI_COLUMNS
    try:
        help_text = parser.format_help().rstrip()
        parser.prog = " ".join([CLI_PROG, *path])
        usage = _unprefixed(parser.format_usage().strip())
    finally:
        parser.prog = saved_prog
        if saved_columns is None:
            del os.environ["COLUMNS"]
        else:
            os.environ["COLUMNS"] = saved_columns
    subs: list[tuple[str, Any, str]] = []
    arguments = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            helps = {a.dest: a.help or "" for a in action._choices_actions}
            seen: set[int] = set()
            for sub, sub_parser in action.choices.items():
                if id(sub_parser) not in seen:
                    seen.add(id(sub_parser))
                    subs.append((sub, sub_parser, helps.get(sub, "")))
        elif not isinstance(action, argparse._HelpAction) and (
            action.help is not argparse.SUPPRESS
        ):
            arguments.append(_cli_argument(parser, action))
    node = {
        "path": path,
        "group": group,
        "summary": summary,
        "parser": True,
        "usage": usage,
        "arguments": arguments,
        "subcommands": [{"name": s, "summary": h} for s, _, h in subs],
        "help": help_text,
    }
    nodes = [node]
    for sub, sub_parser, sub_help in subs:
        nodes += _cli_node(sub_parser, [*path, sub], group, sub_help)
    return nodes


def cli_tree() -> list[dict[str, Any]]:
    """Every `chock` command and subcommand as its parser declares it, in commands.json order.

    A node is {path, group, summary, parser, usage, arguments, subcommands, help}. Commands
    that parse their own arguments have parser False and only the help text they print.
    """
    groups = _data("commands.json")
    nodes: list[dict[str, Any]] = []
    for group, commands in groups.items():
        for name, spec in commands.items():
            parser, printed = _capture_parser(name)
            if parser is None:
                nodes.append(
                    {
                        "path": [name],
                        "group": group,
                        "summary": spec["help"],
                        "parser": False,
                        "usage": "",
                        "arguments": [],
                        "subcommands": [],
                        "help": printed,
                    }
                )
            else:
                nodes += _cli_node(parser, [name], group, spec["help"])
    return nodes
