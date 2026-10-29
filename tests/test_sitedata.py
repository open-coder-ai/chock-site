"""Tests for the generated dist/data/site.json."""

import json
import re
from pathlib import Path

import chock.lock
import yaml

from sitegen import engine
from sitegen.__main__ import build

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
KEYWORDS = {"block", "ask", "warn", "advise"}
HIDDEN_ID = "rtk-dangerous-actions-blocker"


def _site_json(built) -> dict:
    return json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))


def test_every_policy_has_hash_and_keyword(built) -> None:
    data = _site_json(built)
    assert data["policies"], "site.json has no policies"
    for policy in data["policies"]:
        assert SHA256_RE.match(policy["sha256"]), policy["id"]
        assert policy["keyword"] in KEYWORDS, policy["id"]
        assert policy["word"] == data["label_words"][policy["track"]][policy["keyword"]]


def test_no_hidden_id_anywhere(built) -> None:
    # Plan 5.3: the hidden policy is shown nowhere. A byte grep cannot pass:
    # block-destructive-commands' description mentions the id in prose, so this
    # checks structural absence instead (flagged under Questions in PR 1).
    data = _site_json(built)
    assert HIDDEN_ID not in {p["id"] for p in data["policies"]}
    assert all(HIDDEN_ID not in p["members"] for p in data["presets"])
    assert all(
        HIDDEN_ID not in rule.get("policies", []) for rule in data["warning_rules"]
    )
    paths = [str(p.relative_to(built.out)) for p in built.out.rglob("*")]
    assert all(HIDDEN_ID not in path for path in paths)


def test_counts_match_registry_minus_hidden(built, catalog_path: Path) -> None:
    data = _site_json(built)
    registry = yaml.safe_load(
        (catalog_path / "registry.yaml").read_text(encoding="utf-8")
    )
    registry_ids = {row["id"] for row in registry["policies"]}
    assert len(data["policies"]) == len(registry_ids) - 1
    assert {p["id"] for p in data["policies"]} == registry_ids - {HIDDEN_ID}


def _text_key(rule: dict) -> str:
    if rule["kind"] == "grade":
        return f"grade:{rule['grade']}"
    return rule["kind"]


def test_warning_texts_cover_engine_rules(built) -> None:
    data = _site_json(built)
    expected = {_text_key(rule) for rule in engine.warning_rules()}
    assert expected <= set(data["warning_texts"]), (
        f"missing texts for {expected - set(data['warning_texts'])}"
    )


def test_block_test_skips_latest_matches_manifest_version(
    built, catalog_path: Path
) -> None:
    data = _site_json(built)
    policy = next(p for p in data["policies"] if p["id"] == "block-test-skips")
    manifest = yaml.safe_load(
        (catalog_path / "base" / "block-test-skips" / "manifest.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["changelog"][0]["version"] != manifest["version"], (
        "test needs a changelog that is not ordered newest-first"
    )
    entry = next(
        e for e in manifest["changelog"] if e["version"] == manifest["version"]
    )
    assert policy["latest"]["version"] == manifest["version"]
    assert policy["latest"]["date"] == str(entry["date"])
    assert policy["latest"]["change"] == " ".join(str(entry["changes"][0]).split())


def test_block_no_verify_misses(built) -> None:
    data = _site_json(built)
    policy = next(p for p in data["policies"] if p["id"] == "block-no-verify")
    assert policy["misses"] == "older aliases, scripts, $VARs."


def test_build_is_byte_identical_and_lf_only(
    built, catalog_path: Path, tmp_path: Path
) -> None:
    out2 = tmp_path / "dist2"
    build(catalog_path, out2, str(catalog_path.resolve()), None)
    files1 = sorted(
        p.relative_to(built.out) for p in built.out.rglob("*") if p.is_file()
    )
    files2 = sorted(p.relative_to(out2) for p in out2.rglob("*") if p.is_file())
    assert files1 == files2
    for rel in files1:
        content = (built.out / rel).read_bytes()
        assert content == (out2 / rel).read_bytes(), rel
        # Binary assets (og-card.png, fonts) legally contain 0x0d; the LF rule is
        # for text files, which Path.write_text(newline="\n") governs.
        if rel.suffix not in (".png", ".woff2", ".jpg"):
            assert b"\r" not in content, rel


def test_every_policy_has_a_v1_hash_the_engine_accepts(built, catalog_path) -> None:
    paths = {
        p["id"]: p["path"]
        for p in yaml.safe_load((catalog_path / "registry.yaml").read_text("utf-8"))[
            "policies"
        ]
    }
    for policy in _site_json(built)["policies"]:
        v1 = policy["sha256_v1"]
        assert v1 is None or SHA256_RE.match(v1), policy["id"]
        pack = catalog_path / paths[policy["id"]]
        has_nul = any(b"\0" in f.read_bytes() for f in pack.rglob("*") if f.is_file())
        assert (v1 is None) == has_nul, policy["id"]
        if v1 is not None:
            assert chock.lock.pack_hash_matches(pack, v1), policy["id"]
        assert chock.lock.pack_hash_matches(pack, policy["sha256"]), policy["id"]
