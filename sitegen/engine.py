"""The only module that imports chock: hashes, labels, selection schema and warnings."""

import importlib.resources
import json
from pathlib import Path
from typing import Any

import chock.install.package
import chock.install.resolve
import chock.install.selection
import chock.lock

INSTALL_JSON = "data/install.json"
WARNINGS_JSON = "data/warnings.json"
SelectionError = chock.install.selection.SelectionError


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
    """A selection object in the engine's key order (plan 8.1)."""
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


def policy_labels(catalog: Path, selection: dict[str, Any]) -> dict[str, Any]:
    """Each selected policy's Label (policy_id, keyword, says, description), keyed by id."""
    members = chock.install.resolve.members(catalog, selection)
    return {
        label.policy_id: label
        for label in chock.install.package.labels(members, catalog)
    }


def check_selection(obj: dict[str, Any]) -> dict[str, Any]:
    """The selection if it matches the engine's schema, else SelectionError."""
    return chock.install.selection.check(obj)
