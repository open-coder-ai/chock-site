"""S-ALL: every agent agentseam records, its plugin and repo-hooks routes, reasons and evidence."""

import json
import re
from pathlib import Path

import pytest
import yaml

from sitegen import clientdata, engine, routes
from sitegen.catalog import lead_sentences
from sitegen.clientpage import agent_note
from sitegen.pageparts import PageError

DATA = Path(__file__).resolve().parents[1] / "data"
ISSUES = "https://github.com/open-coder-ai/agentseam/issues/"


def _site(built) -> dict:
    return json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))


def _rows(built) -> dict[str, dict]:
    return {row["agent"]: row for row in _site(built)["agent_routes"]["agents"]}


def _page(built, page: str, name: str = "index.html") -> str:
    return (built.out / "coding" / page / name).read_text(encoding="utf-8")


def test_every_matrix_agent_is_listed_once(built) -> None:
    agents = [row["agent"] for row in _site(built)["agent_routes"]["agents"]]
    assert agents == list(engine.matrix_agents())
    assert len(agents) == len(set(agents)) == 27


def test_routes_follow_the_engine(built) -> None:
    rows = _rows(built)
    plugins = {
        row["plugin"]["client"]: agent for agent, row in rows.items() if row["plugin"]
    }
    assert sorted(plugins) == sorted(engine.client_ids())
    wired = {agent for agent, row in rows.items() if row["sync"]}
    assert wired == set(engine.sync_vendors())
    for agent, row in rows.items():
        assert (row["reason"] is None) == (agent in wired), agent
        expected = (
            ("both" if row["sync"] else "plugin")
            if row["plugin"]
            else ("sync" if row["sync"] else "none")
        )
        assert row["route"] == expected, agent


def test_the_named_routes(built) -> None:
    rows = _rows(built)
    reasons = yaml.safe_load((DATA / "routes.yaml").read_text("utf-8"))["reasons"]
    assert rows["mistral_vibe"]["route"] == "sync"
    assert rows["mistral_vibe"]["sync"]["command"] == (
        "chock sync --repo . --agents mistral-vibe"
    )
    assert {a for a, r in rows.items() if r["route"] == "sync"} == {
        "mistral_vibe",
        "tabnine",
        "vscode_copilot",
        "windsurf",
    }
    assert rows["kimi_code"]["route"] == "plugin"
    assert rows["cline"]["reason"] == reasons["hook_dir"]
    assert rows["junie"]["reason"] == reasons["home_config"]
    assert rows["kimi_code"]["reason"] == reasons["home_config"]
    for agent in ("aider", "zed"):
        assert rows[agent]["reason"] == reasons["no_hooks"], agent
    for agent in ("replit", "roo_code", "amp", "kiro", "opencode", "kilo_code"):
        assert rows[agent]["reason"] == reasons["unadapted"], agent
    none = {a for a, r in rows.items() if r["route"] == "none"}
    assert {"cline", "junie", "replit", "zed", "aider", "roo_code"} <= none


def test_a_plugin_witness_never_clears_repo_hooks(built) -> None:
    rows = _rows(built)
    sync_witnessed = {
        a for a, r in rows.items() if r["sync"] and r["sync"]["witness"] == "witnessed"
    }
    assert sync_witnessed == {"vscode_copilot"}
    for agent in ("claude_code", "cursor", "codex_cli"):
        assert rows[agent]["plugin"]["witness"] == "witnessed", agent
        assert rows[agent]["sync"]["witness"] == "untested", agent


def test_plugin_witness_follows_witness_yaml_and_the_ledger(built) -> None:
    rows = _rows(built)
    witness = clientdata.load_witness(DATA, engine.client_ids())["clients"]
    for row in rows.values():
        if row["plugin"]:
            assert row["plugin"]["witness"] == witness[row["plugin"]["client"]]


def test_the_engine_untested_plugins_are_untested_here(built) -> None:
    """The engine install's Untested clients, plus witness.yaml claims the ledger does not back."""
    block = _site(built)["builder_clients"]
    prefix = block["engine_untested_prefix"]
    (rule,) = [r for r in engine.warning_rules() if r["says"].startswith(prefix)]
    untested = [
        c for c in block["order"] if block["clients"][c]["witness"] == "untested"
    ]
    unbacked = clientdata.load_witness(DATA, engine.client_ids())["unbacked"]
    assert sorted(untested) == sorted([*rule["clients"], *unbacked])


def test_records_come_from_agentseam(built) -> None:
    for agent, row in _rows(built).items():
        tier = engine.tier_row(agent)
        assert f"pre-tool: {tier['tier']}, {tier['grade']}," in row["record"], agent
        assert tier["basis"] in row["record"] and tier["recorded"] in row["record"]


def test_agent_issues_are_the_ones_agentseam_cites(built) -> None:
    evidence = yaml.safe_load((DATA / "evidence.yaml").read_text("utf-8"))
    assert evidence["agents"]
    for agent, number in evidence["agents"].items():
        assert f"{ISSUES}{number}" in engine.matrix_text(agent), agent
        assert _rows(built)[agent]["evidence"]["url"] == f"{ISSUES}{number}"
    rows = _rows(built)
    assert rows["mistral_vibe"]["evidence"]["number"] == 187
    assert rows["cline"]["evidence"]["number"] == 178
    assert rows["goose"]["evidence"]["number"] == 177
    assert rows["cursor"]["evidence"] is None


def test_cited_notes(built) -> None:
    rows = _rows(built)
    assert "Antigravity" in rows["gemini_cli"]["note"]["text"]
    assert "does not protect OpenHands" in rows["openhands"]["note"]["text"]
    for row in rows.values():
        if row["note"]:
            assert row["note"]["source"], row["agent"]


def test_kimi_code_never_says_asks(built) -> None:
    for policy in _site(built)["policies"]:
        assert policy["agent_labels"]["kimi-code"]["keyword"] != "ask", policy["id"]


def test_install_page_lists_every_agent(built) -> None:
    html = _page(built, "install")
    twin = _page(built, "install", "index.md")
    assert 'id="every-agent"' in html
    for row in _site(built)["agent_routes"]["agents"]:
        tr = re.search(
            rf'<tr id="route-{row["agent"]}".*?</tr>', html, re.DOTALL
        ).group(0)
        assert f'data-route="{row["route"]}"' in tr
        if row["plugin"]:
            client = row["plugin"]["client"]
            assert f'href="#agent-{client}"' in tr
            assert f'id="agent-{client}"' in html
        if row["sync"]:
            assert row["sync"]["command"] in tr
        else:
            assert row["reason"] in tr.replace("&#x27;", "'")
        if row["evidence"]:
            assert f'href="{row["evidence"]["url"]}"' in tr
        assert f"### {row['name']} (`{row['agent']}`)" in twin


def test_builder_points_to_every_agent(built) -> None:
    assert 'href="/coding/install/#every-agent"' in _page(built, "builder")
    assert "(/coding/install/#every-agent)" in _page(built, "builder", "index.md")


def test_engine_evidence_notes_are_said_once(built) -> None:
    site = _site(built)
    prefix = site["builder_clients"]["engine_evidence_prefix"]
    assert not [r for r in site["warning_rules"] if r["says"].startswith(prefix)]
    assert [r for r in engine.warning_rules() if r["says"].startswith(prefix)]


def test_an_engine_evidence_note_must_match_the_site_row() -> None:
    rule = {"kind": "client", "clients": ["goose"], "says": "Evidence wanted: at x/177"}
    block = {
        "engine_evidence_prefix": "Evidence wanted:",
        "clients": {"goose": {"evidence": {"url": "x/178"}}},
    }
    with pytest.raises(PageError, match="goose"):
        clientdata.drop_engine_evidence([rule], block)
    block["clients"]["goose"]["evidence"]["url"] = "x/177"
    assert clientdata.drop_engine_evidence([rule], block) == []


def _routes_copy(tmp_path: Path, edit) -> Path:
    data = yaml.safe_load((DATA / "routes.yaml").read_text("utf-8"))
    edit(data)
    (tmp_path / "routes.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("edit", "match"),
    (
        (lambda d: d["plugins"].pop("goose"), "plugins"),
        (lambda d: d["plugins"].update(goose="nobody"), "not an agent"),
        (lambda d: d["plugins"].update(goose="grok"), "two clients"),
        (lambda d: d["reasons"].pop("hook_dir"), "reasons"),
        (lambda d: d["notes"].update(nobody={"text": "t", "source": "s"}), "nobody"),
    ),
)
def test_routes_yaml_is_checked(tmp_path: Path, edit, match: str) -> None:
    with pytest.raises(PageError, match=match):
        routes.load_routes(_routes_copy(tmp_path, edit))


@pytest.mark.parametrize(
    ("agents", "match"),
    (
        ({"goose": 177}, "has a plugin"),
        ({"vscode_copilot": 5}, "witnessed on repo hooks"),
        ({"nobody": 5}, "not an agent"),
        ({"cline": 0}, "not a number"),
        ({"cline": "178"}, "not a number"),
    ),
)
def test_agent_issue_rows_are_checked(agents: dict, match: str) -> None:
    data = routes.load_routes(DATA)
    with pytest.raises(PageError, match=match):
        routes.check_agent_issues({"agents": agents}, data, {"vscode_copilot"})


def test_agent_note_asks_in_the_sentence_that_names_install() -> None:
    ask = " (ask the user before running it)"
    assert agent_note("Plain. Use `chock install --client x`. Next.", ask) == (
        "Plain. Use `chock install --client x` (ask the user before running it). Next."
    )
    assert agent_note("Edit settings.json; no install here.", ask) == (
        "Edit settings.json; no install here."
    )
    assert agent_note("Ask first: chock install.", ask) == "Ask first: chock install."


def test_lead_sentences_reach_the_length() -> None:
    text = "Short one. A second, longer sentence here. Third."
    assert lead_sentences(text, 5) == "Short one."
    assert lead_sentences(text, 20) == "Short one. A second, longer sentence here."
    assert lead_sentences("No stop", 50) == "No stop"
