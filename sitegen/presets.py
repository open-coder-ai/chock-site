"""Load and validate data/presets.yaml."""

import re
from pathlib import Path

import yaml

from .model import Preset

ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")


class PresetError(ValueError):
    """A preset file that fails validation; the message names the preset and member."""


def load_presets(path: Path) -> list[Preset]:
    """The presets, in file order."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [
        Preset(
            id=str(row["id"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            members=[str(m) for m in row["members"]],
        )
        for row in data.get("presets", [])
    ]


def validate_presets(
    presets: list[Preset], visible_ids: set[str], hidden_ids: set[str]
) -> None:
    """Unique, well-formed ids; every member a visible, non-hidden policy exactly once."""
    seen: set[str] = set()
    for preset in presets:
        if not ID_RE.match(preset.id):
            msg = f"preset {preset.id}: id does not match {ID_RE.pattern}"
            raise PresetError(msg)
        if preset.id in seen:
            msg = f"preset {preset.id}: duplicate preset id"
            raise PresetError(msg)
        seen.add(preset.id)
        members_seen: set[str] = set()
        for member in preset.members:
            if member in members_seen:
                msg = f"preset {preset.id}: duplicate member {member}"
                raise PresetError(msg)
            members_seen.add(member)
            if member in hidden_ids:
                msg = f"preset {preset.id}: member {member} is hidden"
                raise PresetError(msg)
            if member not in visible_ids:
                msg = f"preset {preset.id}: unknown member {member}"
                raise PresetError(msg)
