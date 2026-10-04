"""Tests for presets.py: valid file, unknown member, hidden member, duplicates."""

from pathlib import Path

import pytest
import yaml

from sitegen.model import Preset
from sitegen.presets import PresetError, load_presets, validate_presets

DATA = Path(__file__).resolve().parents[1] / "data"


def test_real_presets_validate(built) -> None:
    presets = load_presets(DATA / "presets.yaml")
    validate_presets(
        presets, {p.id for p in built.site.policies}, {"rtk-dangerous-actions-blocker"}
    )
    assert len(presets) == 14


def test_unknown_member_fails() -> None:
    presets = [
        Preset(id="ok-preset", title="T", summary="S", members=["no-such-policy"])
    ]
    with pytest.raises(PresetError, match="no-such-policy"):
        validate_presets(presets, {"some-policy"}, set())


def test_hidden_member_fails() -> None:
    presets = [
        Preset(
            id="ok-preset",
            title="T",
            summary="S",
            members=["rtk-dangerous-actions-blocker"],
        )
    ]
    with pytest.raises(PresetError, match="hidden"):
        validate_presets(
            presets,
            {"rtk-dangerous-actions-blocker"},
            {"rtk-dangerous-actions-blocker"},
        )


def test_duplicate_member_fails() -> None:
    presets = [
        Preset(id="ok-preset", title="T", summary="S", members=["a-policy", "a-policy"])
    ]
    with pytest.raises(PresetError, match="duplicate member a-policy"):
        validate_presets(presets, {"a-policy"}, set())


def test_duplicate_preset_id_fails() -> None:
    presets = [
        Preset(id="same-id", title="T", summary="S", members=[]),
        Preset(id="same-id", title="T", summary="S", members=[]),
    ]
    with pytest.raises(PresetError, match="duplicate preset id"):
        validate_presets(presets, set(), set())


def test_bad_id_fails(tmp_path: Path) -> None:
    bad = tmp_path / "presets.yaml"
    bad.write_text(
        yaml.safe_dump(
            {"presets": [{"id": "Bad ID", "title": "T", "summary": "S", "members": []}]}
        )
    )
    presets = load_presets(bad)
    with pytest.raises(PresetError, match="Bad ID"):
        validate_presets(presets, set(), set())
