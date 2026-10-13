"""The only module that imports chock: hashes, labels, selection schema and warnings."""

import base64
import importlib.resources
import json
import re
import shlex
from pathlib import Path
from typing import Any

import chock.install.package
import chock.install.place
import chock.install.resolve
import chock.install.selection
import chock.install.steps
import chock.lock
from chock.validation.loading import load_schema

INSTALL_JSON = "data/install.json"
WARNINGS_JSON = "data/warnings.json"
SelectionError = chock.install.selection.SelectionError
SCHEMA2 = chock.install.selection.SCHEMA2
CATALOG_ENTRY = chock.install.selection.CATALOG
BUNDLE_NAME = chock.install.selection.DEFAULT_BUNDLE
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


def sync_agents() -> tuple[str, ...]:
    """The agents `chock sync` wires a repo's own hooks for (the in-agent surface)."""
    import chock.vendors

    return chock.vendors.in_agent_vendors()


def stop_agents() -> tuple[str, ...]:
    """The agents whose end of turn `chock sync` also gates."""
    import chock.vendors

    return chock.vendors.stop_vendors()


def sync_names() -> dict[str, str]:
    """Each agent's first `chock sync --agents` name, keyed by agentseam agent."""
    import chock.vendors

    names: dict[str, str] = {}
    for name, agent in chock.vendors.CHOCK_AGENT.items():
        names.setdefault(agent, name)
    return names


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


def gate_logs() -> list[str]:
    """The repo-relative paths of the gate log the engine writes, current then rotated."""
    import chock.gatelog

    folder = f".chock/{chock.gatelog.LOG_DIR}"
    return [
        f"{folder}/{chock.gatelog.LOG_NAME}",
        f"{folder}/{chock.gatelog.ROTATED_NAME}",
    ]


def cli_commands() -> list[dict[str, str]]:
    """Every `chock` command in the engine's groups, with its one-line help and its --help text."""
    import contextlib
    import io
    import os

    import chock.cli

    groups = json.loads(
        importlib.resources.files("chock")
        .joinpath("data", "commands.json")
        .read_text(encoding="utf-8")
    )
    saved = os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = "100"
    rows = []
    try:
        for group, commands in groups.items():
            for name, spec in commands.items():
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.suppress(SystemExit):
                    chock.cli.COMMANDS[name][0](["--help"])
                rows.append(
                    {
                        "group": group,
                        "name": name,
                        "summary": spec["help"],
                        "help": buf.getvalue().rstrip(),
                    }
                )
    finally:
        if saved is None:
            del os.environ["COLUMNS"]
        else:
            os.environ["COLUMNS"] = saved
    return rows
