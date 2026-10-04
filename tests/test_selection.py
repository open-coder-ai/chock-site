"""Tests for the selection object the builder produces (plan 8.1)."""

import pytest

from sitegen import engine
from sitegen.engine import SelectionError


def _picks(policies, ids):
    by_id = {p.id: p for p in policies}
    return [
        {"id": pid, "version": by_id[pid].version, "sha256": by_id[pid].sha256}
        for pid in ids
    ]


def test_every_preset_builds_a_valid_selection(built) -> None:
    site = built.site
    for preset in site.presets:
        picks = _picks(site.policies, preset.members)
        selection = engine.build_selection(
            picks, site.catalog_source, site.catalog_ref, preset=preset.id
        )
        assert engine.check_selection(selection)


def test_extra_key_fails(built) -> None:
    site = built.site
    picks = _picks(site.policies, [site.policies[0].id])
    selection = engine.build_selection(picks, site.catalog_source, site.catalog_ref)
    selection["bogus"] = True
    with pytest.raises(SelectionError):
        engine.check_selection(selection)


def test_bad_ref_fails(built) -> None:
    site = built.site
    picks = _picks(site.policies, [site.policies[0].id])
    selection = engine.build_selection(picks, site.catalog_source, "not-a-hex-ref")
    with pytest.raises(SelectionError):
        engine.check_selection(selection)
