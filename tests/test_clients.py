"""BV-S1: witness data, per-client labels and steps in site.json's builder_clients block."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from sitegen import clientdata, engine
from sitegen.model import Latest, Policy
from sitegen.pageparts import PageError

DATA = Path(__file__).resolve().parents[1] / "data"
WORDS = {"block": "blocks", "ask": "asks", "warn": "warns", "advise": "advisory"}


def _site(built) -> dict:
    return json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))


def _policy(client_labels: dict) -> Policy:
    return Policy(
        id="p-one",
        path="base/p-one",
        name="P one",
        version="0.0.1",
        description="",
        eval_cases=0,
        eval_executed=0,
        latest=Latest("0.0.1", "", ""),
        source_url="",
        keyword="ask",
        says="claude says",
        client_labels=client_labels,
    )


def _witness_copy(tmp_path: Path, edit) -> Path:
    shutil.copy(DATA / "witness.yaml", tmp_path / "witness.yaml")
    data = yaml.safe_load((tmp_path / "witness.yaml").read_text(encoding="utf-8"))
    edit(data)
    (tmp_path / "witness.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp_path


def test_only_claude_code_is_witnessed() -> None:
    data = clientdata.load_witness(DATA, engine.client_ids())
    assert data["default"] == "claude-code"
    assert {c for c, s in data["clients"].items() if s == "witnessed"} == {
        "claude-code"
    }


def test_witness_file_must_name_every_engine_client(tmp_path: Path) -> None:
    folder = _witness_copy(tmp_path, lambda d: d["clients"].pop("devin"))
    with pytest.raises(PageError, match="clients"):
        clientdata.load_witness(folder, engine.client_ids())


def test_witness_state_is_witnessed_or_untested(tmp_path: Path) -> None:
    folder = _witness_copy(tmp_path, lambda d: d["clients"].update(cursor="maybe"))
    with pytest.raises(PageError, match="maybe"):
        clientdata.load_witness(folder, engine.client_ids())


def test_per_client_grades_need_all_five_clients() -> None:
    clients = engine.client_ids()
    full = {c: {"keyword": "block", "says": f"{c} says"} for c in clients}
    assert clientdata.has_client_grades([_policy(full)], clients)
    partial = {c: v for c, v in full.items() if c != "devin"}
    assert not clientdata.has_client_grades([_policy(partial)], clients)


def test_labels_come_from_the_catalog_only_when_graded() -> None:
    full = {c: {"keyword": "block", "says": f"{c} says"} for c in engine.client_ids()}
    policy = _policy(full)
    graded = clientdata.client_labels([policy], "cursor", True, WORDS)
    assert graded["p-one"] == {"keyword": "block", "says": "cursor says"}
    fallback = clientdata.client_labels([policy], "cursor", False, WORDS)
    assert fallback["p-one"] == {"keyword": "ask", "says": "claude says"}
    claude = clientdata.client_labels([policy], "claude-code", True, WORDS)
    assert claude["p-one"] == {"keyword": "ask", "says": "claude says"}


def test_site_json_carries_each_client(built) -> None:
    block = _site(built)["builder_clients"]
    assert block["order"] == ["claude-code", "cursor", "codex", "copilot", "devin"]
    assert sorted(block["clients"]) == sorted(engine.client_ids())
    ids = {p["id"] for p in _site(built)["policies"]}
    for client, data in block["clients"].items():
        assert set(data["labels"]) == ids, client
        assert data["steps"], client
        assert data["witness"] in ("witnessed", "untested")
    assert "--apply" in block["commands"]["witnessed"]
    assert "--apply" not in block["commands"]["untested"]


def test_steps_match_the_engine(built) -> None:
    block = _site(built)["builder_clients"]
    for client in engine.client_ids():
        assert block["clients"][client]["steps"] == engine.client_steps(client)


def test_builder_page_has_the_picker_and_one_panel_per_client(built) -> None:
    html = (built.out / "coding" / "builder" / "index.html").read_text(encoding="utf-8")
    for client in engine.client_ids():
        assert f'id="client-{client}"' in html
        assert f'<div class="client-steps" data-client="{client}"' in html
    twin = (built.out / "coding" / "builder" / "index.md").read_text(encoding="utf-8")
    assert "## Agents" in twin
    assert "--client cursor\n" in twin
