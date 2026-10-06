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


@pytest.mark.parametrize("client", engine.client_ids())
def test_every_preset_builds_a_valid_schema_2_selection_per_client(
    built, client
) -> None:
    site = built.site
    version = site.data["builder_clients"]["bundle_version"]
    for preset in site.presets:
        picks = _picks(site.policies, preset.members)
        selection = engine.build_selection_v2(
            picks,
            site.catalog_source,
            site.catalog_ref,
            client,
            version,
            None,
            preset.id,
        )
        assert engine.check_selection(selection)["client"] == client
        code = engine.encode_selection(selection)
        loaded = engine.load_selection(code)
        assert [p["id"] for p in loaded["policies"]] == sorted(preset.members)


def test_schema_2_rejects_an_unknown_client(built) -> None:
    site = built.site
    picks = _picks(site.policies, [site.policies[0].id])
    selection = engine.build_selection_v2(
        picks, site.catalog_source, site.catalog_ref, "vim", "1.0.0"
    )
    with pytest.raises(SelectionError):
        engine.check_selection(selection)
