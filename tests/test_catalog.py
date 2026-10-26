"""Tests for catalog.py: misses extraction, where tags, and the registry id and path checks."""

from pathlib import Path

import chock.policy_id
import pytest
import yaml

from sitegen.catalog import (
    POLICY_ID_RE,
    CatalogError,
    extract_misses,
    load_policies,
    policy_dir,
    registry_ids,
    where_tags,
)
from sitegen.pageparts import PageError


def test_misses_marker_present() -> None:
    desc = "Blocks bad git flags. Misses: older aliases, scripts, $VARs. More detail follows."
    assert extract_misses(desc) == "older aliases, scripts, $VARs."


def test_misses_not_caught_here_marker() -> None:
    desc = "Scans writes. Not caught here: symlinks. Further text."
    assert extract_misses(desc) == "symlinks."


def test_misses_absent() -> None:
    assert extract_misses("Does a thing. No marker anywhere.") is None


def test_misses_marker_at_end() -> None:
    assert extract_misses("Does a thing. Misses:") == ""


def test_misses_first_marker_by_position() -> None:
    desc = "Not caught here: the gap. Misses: another gap."
    assert extract_misses(desc) == "the gap."


def test_where_command_only() -> None:
    says = "refuses a matched shell command before it runs"
    assert where_tags(says) == ["command"]


def test_where_write_and_turn_end() -> None:
    says = "warns on an agent's file writes and at turn end"
    assert where_tags(says) == ["write", "turn-end"]


def test_where_advisory() -> None:
    says = "advisory only: skill text, nothing stops a violation"
    assert where_tags(says) == ["text"]


def test_where_command_write_turn_end() -> None:
    says = (
        "refuses a matched shell command before it runs; "
        "blocks on an agent's file writes and at turn end"
    )
    assert where_tags(says) == ["command", "write", "turn-end"]


# --- SITE-1: no registry value reaches a shell line or a path unchecked -------------------


def _scratch_catalog(tmp_path: Path, rows: list[dict]) -> Path:
    """A catalog folder holding registry.yaml with `rows`, and one real-looking policy."""
    catalog = tmp_path / "catalog"
    folder = catalog / "base" / "block-marker"
    folder.mkdir(parents=True)
    (folder / "manifest.yaml").write_text(
        "id: block-marker\nname: Block marker\nversion: 1.0.0\ndescription: Refuses a marker.\n",
        encoding="utf-8",
    )
    (catalog / "registry.yaml").write_text(
        yaml.safe_dump({"policies": rows}, sort_keys=False), encoding="utf-8"
    )
    return catalog


GOOD_ROW = {"id": "block-marker", "path": "base/block-marker", "version": "1.0.0"}


def test_a_well_formed_registry_row_loads(tmp_path: Path) -> None:
    catalog = _scratch_catalog(tmp_path, [GOOD_ROW])
    assert registry_ids(catalog) == ["block-marker"]
    [policy] = load_policies(catalog, set(), "r")
    assert (policy.id, policy.path) == ("block-marker", "base/block-marker")


@pytest.mark.parametrize(
    "bad_id",
    [
        "safe;echo PWNED > pwned",
        "../../../escaped",
        "block marker",
        "Block-Marker",
        "ab",
        "-leading-dash",
        "a" * 65,
        "block$(id)",
        "",
    ],
)
def test_an_id_outside_the_engine_grammar_fails_the_build_naming_it(
    tmp_path: Path, bad_id: str
) -> None:
    catalog = _scratch_catalog(tmp_path, [GOOD_ROW | {"id": bad_id}])
    for reader in (registry_ids, lambda c: load_policies(c, set(), "r")):
        with pytest.raises(CatalogError) as found:
            reader(catalog)
        assert repr(bad_id) in str(found.value)
        assert POLICY_ID_RE.pattern in str(found.value)


def test_a_hidden_id_is_still_checked(tmp_path: Path) -> None:
    catalog = _scratch_catalog(tmp_path, [GOOD_ROW | {"id": "a;b"}])
    with pytest.raises(CatalogError, match="'a;b'"):
        load_policies(catalog, {"a;b"}, "r")


def test_the_grammar_is_the_engines_own() -> None:
    assert POLICY_ID_RE is chock.policy_id.POLICY_ID_RE


@pytest.mark.parametrize(
    "bad_path",
    ["../../../escaped", "/etc", "base/../../escaped", "", None],
)
def test_a_path_that_leaves_the_catalog_fails_the_build(
    tmp_path: Path, bad_path: object
) -> None:
    catalog = _scratch_catalog(tmp_path, [GOOD_ROW | {"path": bad_path}])
    with pytest.raises(PageError) as found:
        load_policies(catalog, set(), "r")
    assert repr(bad_path) in str(found.value)
    assert "path of 'block-marker'" in str(found.value)


def test_every_pinned_registry_row_passes_both_checks(catalog_path: Path) -> None:
    ids = registry_ids(catalog_path)
    assert ids and all(POLICY_ID_RE.fullmatch(pid) for pid in ids)
    rows = yaml.safe_load((catalog_path / "registry.yaml").read_text("utf-8"))
    for row in rows["policies"]:
        assert policy_dir(catalog_path, row).is_dir(), row["id"]
