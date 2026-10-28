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
import chock.install.claude_plugin
import chock.install.package
import chock.install.place
import chock.install.resolve
import chock.install.selection
import chock.install.steps
import chock.lock
import chock.policy_id
import chock.vendors
from agentseam import matrix as agentseam_matrix
from agentseam import tier_table as agentseam_tiers
from chock.validation.loading import load_schema

from .paths import safe_join

INSTALL_JSON = "data/install.json"
WARNINGS_JSON = "data/warnings.json"
SelectionError = chock.install.selection.SelectionError
SCHEMA2 = chock.install.selection.SCHEMA2
CATALOG_ENTRY = chock.install.selection.CATALOG
BUNDLE_NAME = chock.install.selection.DEFAULT_BUNDLE
# The selection argument in the Claude Code build line, which the site fills per page.
SELECTION_TOKEN = "__CODE__"
# Why `chock sync` does not wire an agent, keyed as data/routes.yaml words it (S-ALL).
UNWIRED_HOOK_DIR = "hook_dir"
UNWIRED_HOME_CONFIG = "home_config"
UNWIRED_NO_HOOKS = "no_hooks"
UNWIRED_UNADAPTED = "unadapted"
# What agentseam prints where an agent has no hook surface at all.
NOT_APPLICABLE = agentseam_tiers.NOT_APPLICABLE
# The engine's one rule for a policy id, which it enforces before an id becomes a path or a command token.
POLICY_ID_RE = chock.policy_id.POLICY_ID_RE
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
    return _site_steps(raw, chock.install.steps.render(client, client_tokens(client)))


def client_remove(client: str) -> list[dict[str, str]]:
    """The client's removal steps as `chock install` prints them; empty when the engine has none."""
    raw = chock.install.package.client(client).get("remove", [])
    rendered = chock.install.steps.render_remove(client, client_tokens(client))
    return _site_steps(raw, rendered)


def _site_steps(
    raw: list[dict[str, Any]], rendered: list[chock.install.steps.Step]
) -> list[dict[str, str]]:
    """Rendered engine steps as the site's {"command"|"note"|"settings": text} records."""
    return [
        {"command": _shell_line(step.command)}
        if step.command
        else {("settings" if "settings" in source else "note"): step.text}
        for source, step in zip(raw, rendered, strict=True)
    ]


def claude_plugin_tokens() -> dict[str, str]:
    """The tokens `chock install` fills in the Claude Code build's steps for another agent."""
    build = chock.install.claude_plugin.settings()["build_client"]
    dest = Path(chock.install.package.client(build)["dest"])
    tokens = chock.install.claude_plugin.tokens(dest, BUNDLE_NAME, SELECTION_TOKEN)
    return tokens | {
        "__DEST__": dest.as_posix(),
        "__PLUGIN_DIR__": Path(tokens["__PLUGIN_DIR__"]).as_posix(),
    }


def claude_plugin_offer(client: str) -> dict[str, Any] | None:
    """What `chock install --client <client>` adds about the Claude Code build, or None.

    An offer is {"heading", "routes", "warnings"}: each route has chock's `where`, `label`,
    optional `prefer_native`, the `build` line and its steps. Where chock offers none but says
    why, it is {"not_offered": text}.
    """
    plugin = chock.install.claude_plugin
    data = plugin.settings()
    if client == data["build_client"]:
        return None
    entry = data["clients"].get(client, {})
    offered = plugin.routes(client, data)
    if not offered:
        return {"not_offered": entry["not_offered"]} if "not_offered" in entry else None
    tokens = claude_plugin_tokens()
    render = chock.install.steps.render_steps
    return {
        "heading": data["heading"],
        "routes": [
            {
                "where": route["where"],
                "label": route["label"],
                "prefer_native": route.get("prefer_native"),
                "build": render(
                    [{"note": data["build"]}], tokens | {"__WHERE__": route["where"]}
                )[0].text,
                "steps": _site_steps(route["steps"], render(route["steps"], tokens)),
            }
            for route in offered
        ],
        "warnings": list(data["warnings"]),
    }


def claude_plugin_clients() -> list[str]:
    """The install clients chock offers the Claude Code build to, in chock's data order."""
    plugin = chock.install.claude_plugin
    return [client for client in plugin.settings()["clients"] if plugin.routes(client)]


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


# --- DOCS-2: How Chock works -----------------------------------------------------


def _emitter_path(emitter: Any) -> str:
    """The file a compiler emitter's `emit` is defined in, as a path in the chock repository."""
    import inspect

    return "src/" + inspect.getmodule(emitter.emit).__name__.replace(".", "/") + ".py"


def surface_rows() -> list[dict[str, Any]]:
    """Each enforcement surface in the engine's order: its emitter file, its agents, and whether it earns coverage."""
    from chock.compile.compiler import EMITTERS
    from chock.compile.surfaces import SURFACE_AGENTS, UNCREDITED_SURFACES, Surface

    return [
        {
            "surface": surface.value,
            "emitter": _emitter_path(EMITTERS[surface])
            if surface in EMITTERS
            else None,
            "agents": sorted(a for a, has in SURFACE_AGENTS.items() if surface in has),
            "credited": surface not in UNCREDITED_SURFACES,
        }
        for surface in Surface
    ]


def engine_source(path: str) -> str:
    """The text of one engine file, `src/chock/...`, as installed from .framework-ref."""
    prefix = "src/chock/"
    if not path.startswith(prefix):
        raise ValueError(f"{path!r} is not a file under {prefix}")
    package = Path(chock.__file__).resolve().parent
    return safe_join(package, path.removeprefix(prefix), "engine file").read_text(
        encoding="utf-8"
    )


def stop_facts() -> dict[str, str]:
    """What `chock stop` prints about its limits, the files a stop lives in, and the word that lifts --everywhere."""
    from chock.gate.runner.halt import (
        HALT_EVERYWHERE_NAME,
        HALT_PARTS,
        HALT_REGISTRY_PARTS,
    )
    from chock.stop_common import LIMITS
    from chock.stop_everywhere import CONFIRM_WORD

    registry = "~/" + "/".join(HALT_REGISTRY_PARTS)
    return {
        "limits": LIMITS,
        "repo_file": "/".join(HALT_PARTS),
        "registry": registry + "/",
        "everywhere_file": f"{registry}/{HALT_EVERYWHERE_NAME}",
        "confirm_word": CONFIRM_WORD,
    }


def check_names() -> tuple[str, ...]:
    """The checks `chock check` runs, in its order."""
    from chock.lifecycle import CHECKS

    return CHECKS


# DOCS-3: agentseam's public API and CLI, read from the release chock installs.
AGENTSEAM_PROG = "agentseam"
AGENTSEAM_SRC = "src/agentseam"


def agentseam_commit() -> str:
    """The agentseam commit pip installed from git, or "" if it was not installed that way."""
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        raw = distribution(AGENTSEAM_PROG).read_text("direct_url.json") or "{}"
    except PackageNotFoundError:
        return ""
    return json.loads(raw).get("vcs_info", {}).get("commit_id", "")


def agentseam_meta() -> dict[str, str]:
    """The installed agentseam's version, Python requirement and licence, from its metadata."""
    from importlib.metadata import distribution

    meta = distribution(AGENTSEAM_PROG).metadata
    return {
        "version": meta["Version"],
        "requires_python": meta["Requires-Python"] or "",
        "license": meta["License-Expression"] or meta["License"] or "",
        # Requirements behind an extra (`pytest; extra == "dev"`) are not installed by default.
        "requires": ", ".join(
            r for r in meta.get_all("Requires-Dist") or [] if "extra ==" not in r
        ),
    }


def _doc(obj: Any) -> str:
    """An object's own docstring, first paragraph only, as one line; "" when it has none."""
    import inspect

    own = obj.__doc__ if isinstance(obj.__doc__, str) else None
    if not own:
        return ""
    first = inspect.cleandoc(own).split("\n\n", 1)[0]
    return " ".join(first.split())


def _signature(obj: Any) -> str:
    import inspect

    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return ""


def _source(obj: Any) -> str:
    """Where obj is defined, as `src/agentseam/<file>#L<line>`, or "" if inspect cannot say."""
    import inspect

    import agentseam

    try:
        path = Path(inspect.getsourcefile(obj) or "")
        line = inspect.getsourcelines(obj)[1]
    except (OSError, TypeError):
        return ""
    root = Path(agentseam.__file__).parent
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return ""
    return f"{AGENTSEAM_SRC}/{rel}#L{line}"


def _value(value: Any) -> tuple[str, int | None]:
    """A plain value as code (sets sorted), or for a mapping only its size."""
    if isinstance(value, dict):
        return "", len(value)
    if isinstance(value, (set, frozenset)):
        value = tuple(sorted(value))
    if isinstance(value, (tuple, list)) and not all(
        isinstance(v, (str, int, float, bool)) for v in value
    ):
        return "", len(value)
    return repr(value), None


def _api_entry(name: str, obj: Any) -> dict[str, Any]:
    """One public name: its kind, signature, docstring summary, source and members."""
    import inspect
    import types

    entry: dict[str, Any] = {
        "name": name,
        "kind": "",
        "signature": "",
        "doc": "",
        "value": "",
        "size": None,
        "source": "",
        "members": [],
    }
    if isinstance(obj, types.ModuleType):
        public = getattr(obj, "__all__", None)
        if public is None:
            public = [
                k
                for k, v in vars(obj).items()
                if not k.startswith("_")
                and (inspect.isfunction(v) or inspect.isclass(v))
                and v.__module__ == obj.__name__
            ]
        entry |= {"kind": "module", "doc": _doc(obj)}
        entry["members"] = [_api_entry(k, getattr(obj, k)) for k in public]
        entry["module"] = obj.__name__
        return entry
    if inspect.isclass(obj):
        members = []
        for key, raw in vars(obj).items():
            if key.startswith("_"):
                continue
            if isinstance(raw, (classmethod, staticmethod, property)) or (
                inspect.isfunction(raw)
            ):
                member = getattr(obj, key)
                members.append(
                    {
                        "name": key,
                        "kind": type(raw).__name__,
                        "signature": ""
                        if isinstance(raw, property)
                        else _signature(member),
                        "doc": _doc(raw.fget if isinstance(raw, property) else member),
                    }
                )
        entry |= {
            "kind": "class",
            "signature": _signature(obj),
            "doc": _doc(obj),
            "source": _source(obj),
            "members": members,
        }
        return entry
    if callable(obj):
        entry |= {
            "kind": "function",
            "signature": _signature(obj),
            "doc": _doc(obj),
            "source": _source(obj),
        }
        return entry
    value, size = _value(obj)
    entry |= {"kind": type(obj).__name__, "value": value, "size": size}
    return entry


def agentseam_api() -> list[dict[str, Any]]:
    """Every name in agentseam's `__all__`, in that order, as `_api_entry` reads it."""
    import agentseam

    return [_api_entry(name, getattr(agentseam, name)) for name in agentseam.__all__]


def _agentseam_parser() -> Any:
    """The argparse parser `agentseam` builds; parsing is stopped before it starts."""
    import argparse
    import contextlib
    import io
    from unittest import mock

    import agentseam.cli

    def capture(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise _Captured(self)

    try:
        with (
            mock.patch.object(argparse.ArgumentParser, "parse_known_args", capture),
            mock.patch.object(argparse.ArgumentParser, "parse_args", capture),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            agentseam.cli.main([])
    except _Captured as got:
        return got.parser
    raise RuntimeError("agentseam.cli.main built no parser")


def _agentseam_node(parser: Any, path: list[str], summary: str) -> list[dict[str, Any]]:
    """One agentseam parser as a node like cli_tree's, then its subcommands, depth first."""
    import argparse
    import os

    saved_prog, saved_columns = parser.prog, os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = CLI_COLUMNS
    try:
        parser.prog = " ".join([AGENTSEAM_PROG, *path])
        usage = _unprefixed(parser.format_usage().strip())
        help_text = parser.format_help().rstrip()
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
            for sub, sub_parser in action.choices.items():
                subs.append((sub, sub_parser, helps.get(sub, "")))
        elif not isinstance(action, argparse._HelpAction) and (
            action.help is not argparse.SUPPRESS
        ):
            arguments.append(_cli_argument(parser, action))
    nodes = [
        {
            "path": path,
            "summary": summary,
            "usage": usage,
            "arguments": arguments,
            "subcommands": [{"name": s, "summary": h} for s, _, h in subs],
            "help": help_text,
        }
    ]
    for sub, sub_parser, sub_help in subs:
        nodes += _agentseam_node(sub_parser, [*path, sub], sub_help)
    return nodes


def agentseam_cli() -> list[dict[str, Any]]:
    """The `agentseam` command and every subcommand, as its argparse parser declares them."""
    parser = _agentseam_parser()
    return _agentseam_node(parser, [], parser.description or "")


def agentseam_exit(argv: list[str]) -> int:
    """The exit code `agentseam <argv>` returns, run in this process with output discarded."""
    import contextlib
    import io

    import agentseam.cli

    try:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return int(agentseam.cli.main(argv) or 0)
    except SystemExit as stop:
        return int(stop.code or 0)


def agentseam_chock_pin() -> str:
    """The agentseam commit the installed chock requires (`agentseam @ git+…@<commit>`), or ""."""
    from importlib.metadata import distribution

    for req in distribution("chock").requires or []:
        name, _, url = req.partition("@")
        if name.strip() == AGENTSEAM_PROG and "@" in url:
            return url.rsplit("@", 1)[1].split(";", 1)[0].strip()
    return ""


# --- DOCS-5: the schemas the Write policies reference pages tabulate -------------------


def engine_schemas(name: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """One of the engine's validation schemas, and every schema file it can $ref, by $id."""
    from chock.validation.loading import SCHEMA_STORE

    return load_schema(name), dict(SCHEMA_STORE)
