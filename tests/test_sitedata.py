"""Tests for the generated dist/data/site.json."""

import json
import re
from pathlib import Path

import yaml

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
        assert policy["word"] == data["label_words"][policy["keyword"]]


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


def test_warning_texts_cover_engine_kinds(built) -> None:
    data = _site_json(built)
    kinds = {rule["kind"] for rule in data["warning_rules"]}
    assert kinds <= set(data["warning_texts"]), (
        f"missing texts for {kinds - set(data['warning_texts'])}"
    )
