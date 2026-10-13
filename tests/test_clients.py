"""BV-S1: witness data, per-client labels and steps in site.json's builder_clients block."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from sitegen import catalog, clientdata, clientpage, engine
from sitegen.model import Latest, Policy
from sitegen.pageparts import PageError
from tests.fixtures.untested import CLIENT, ISSUE, untested_data

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


def test_witnessed_needs_a_plugin_hook_row_in_chocks_ledger() -> None:
    """S-ALL: witness.yaml's "witnessed" shows only where chock's ledger has a plugin-hook row."""
    assert clientdata.ledger_clients(DATA) == {"claude-code", "cursor", "codex"}
    data = clientdata.load_witness(DATA, engine.client_ids())
    assert data["default"] == "claude-code"
    shown = {c for c, s in data["clients"].items() if s == "witnessed"}
    assert shown == {"claude-code", "cursor", "codex"}
    assert data["unbacked"] == ["copilot", "devin"]
    backed = clientdata.load_witness(
        DATA,
        engine.client_ids(),
        {"claude-code", "cursor", "codex", "copilot", "devin"},
    )
    assert backed["unbacked"] == []
    assert backed["clients"]["devin"] == "witnessed"


def test_a_client_without_a_row_is_untested(tmp_path: Path) -> None:
    """The 7 P-ALL clients have no witness.yaml row; they show untested, after the rows."""
    data = clientdata.load_witness(DATA, engine.client_ids())
    rows = yaml.safe_load((DATA / "witness.yaml").read_text(encoding="utf-8"))[
        "clients"
    ]
    missing = [c for c in engine.client_ids() if c not in rows]
    assert len(missing) == 7
    assert list(data["clients"]) == [*rows, *missing]
    assert all(data["clients"][c] == "untested" for c in missing)
    folder = _witness_copy(tmp_path, lambda d: d["clients"].pop("devin"))
    every = set(engine.client_ids())
    assert clientdata.load_witness(folder, engine.client_ids(), every)["clients"][
        "devin"
    ] == ("untested")


def test_witness_file_names_engine_clients_only(tmp_path: Path) -> None:
    folder = _witness_copy(tmp_path, lambda d: d["clients"].update(vim="untested"))
    with pytest.raises(PageError, match="vim"):
        clientdata.load_witness(folder, engine.client_ids(), set())


def test_witness_state_is_witnessed_or_untested(tmp_path: Path) -> None:
    folder = _witness_copy(tmp_path, lambda d: d["clients"].update(cursor="maybe"))
    with pytest.raises(PageError, match="maybe"):
        clientdata.load_witness(folder, engine.client_ids())


def test_graded_clients_are_those_the_catalog_grades_on_every_policy() -> None:
    clients = engine.client_ids()
    full = {c: {"keyword": "block", "says": f"{c} says"} for c in clients}
    partial = {c: v for c, v in full.items() if c != "devin"}
    graded = clientdata.graded_clients([_policy(full), _policy(partial)], clients)
    assert graded == [c for c in clients if c != "devin"]
    # The engine grades claude-code itself, so it counts with no catalog block at all.
    assert clientdata.graded_clients([_policy({})], clients) == ["claude-code"]


def test_labels_are_each_agents_own_grade_or_not_graded() -> None:
    partial = {
        c: {"keyword": "block", "says": f"{c} says"}
        for c in engine.client_ids()
        if c != "devin"
    }
    policy = _policy(partial)
    graded = clientdata.client_labels([policy], "cursor", WORDS, "not graded yet")
    assert graded["p-one"] == {"keyword": "block", "says": "cursor says"}
    # No grade for devin: "not graded", never Claude's label in its place.
    devin = clientdata.client_labels([policy], "devin", WORDS, "not graded yet")
    assert devin["p-one"] == {"keyword": clientdata.UNGRADED, "says": "not graded yet"}
    claude = clientdata.client_labels([policy], "claude-code", WORDS, "x")
    assert claude["p-one"] == {"keyword": "ask", "says": "claude says"}


def test_label_status_and_extras_are_not_agents() -> None:
    row = {
        "label": {
            "cursor": {"keyword": "block", "says": "s"},
            "status": {"keyword": "deprecated", "says": "lifecycle status: deprecated"},
            "misses": None,
        }
    }
    assert set(catalog._client_labels(row)) == {"cursor"}
    assert catalog._label_status(row) == "deprecated"
    # A missing status key means no status, never an error (BV-C3).
    assert catalog._label_status({"label": {"cursor": row["label"]["cursor"]}}) is None
    assert catalog._label_status({}) is None


def test_engine_untested_note_is_dropped_once(built) -> None:
    """witness.yaml says which agents are untested; the engine's own note would say it twice."""
    site = _site(built)
    prefix = site["builder_clients"]["engine_untested_prefix"]
    assert not [
        r for r in site["warning_rules"] if r.get("says", "").startswith(prefix)
    ]
    assert [r for r in engine.warning_rules() if r.get("says", "").startswith(prefix)]


def test_remove_steps_and_repos_name_every_agent(built) -> None:
    block = _site(built)["builder_clients"]
    for client, data in block["clients"].items():
        assert bool(data["remove"]) != bool(data["remove_unverified"]), client
        if data["remove_unverified"]:
            assert data["remove_unverified"]["url"] == data["evidence"]["url"], client
            assert data["remove_unverified"]["text"].startswith(
                f"Removal steps not verified for {data['name']} yet."
            )
        repo = data["plugin_repo"]
        assert repo is None or repo.startswith("https://github.com/open-coder-ai/")
        assert "__" not in json.dumps(data["remove"]), client
    with_repo = {c for c, d in block["clients"].items() if d["plugin_repo"]}
    assert with_repo == {"claude-code", "cursor", "codex", "copilot", "devin"}


def test_site_json_carries_each_client(built) -> None:
    block = _site(built)["builder_clients"]
    assert block["order"][:5] == ["claude-code", "cursor", "codex", "copilot", "devin"]
    assert sorted(block["order"]) == sorted(engine.client_ids())
    assert sorted(block["clients"]) == sorted(engine.client_ids())
    policies = _site(built)["policies"]
    for client, data in block["clients"].items():
        # Each label lives once, in policies[].agent_labels (the site.json budget).
        assert "labels" not in data, client
        for policy in policies:
            assert policy["agent_labels"][client]["keyword"], (client, policy["id"])
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
    assert "--client cursor --apply\n" in twin


# ----- S-EV: the "evidence wanted" notice for untested agents -----
# Every real agent is witnessed, so these use the test-only fixture data
# (tests/fixtures/untested-agent.yaml): CLIENT untested with an ISSUE row.

TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "coding"
URL = f"https://github.com/open-coder-ai/agentseam/issues/{ISSUE}"
LINK = f"agentseam issue #{ISSUE}"
NAME = engine.client_name(CLIENT)


def _evidence_copy(tmp_path: Path, edit) -> dict:
    folder = untested_data(tmp_path / "data")
    data = yaml.safe_load((folder / "evidence.yaml").read_text(encoding="utf-8"))
    edit(data)
    (folder / "evidence.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return clientdata.load_evidence(
        folder, clientdata.load_witness(folder, engine.client_ids())
    )


def _install_section(html: str, client: str) -> str:
    start = html.index(f'aria-labelledby="agent-{client}"')
    return html[start : html.index("</section>", start)]


def test_site_evidence_rows_are_the_untested_agents(tmp_path: Path) -> None:
    """Each untested agent has a row, matching the engine's own evidence note; a witnessed one fails."""
    witness = clientdata.load_witness(DATA, engine.client_ids())
    issues = clientdata.load_evidence(DATA, witness)["issues"]
    untested = {c for c, s in witness["clients"].items() if s == "untested"}
    # copilot and devin: witness.yaml says witnessed, chock's ledger has no row; no issue.
    assert set(issues) == untested - set(witness["unbacked"])
    assert issues == {
        "antigravity": 129,
        "gemini-cli": 132,
        "goose": 177,
        "grok": 188,
        "kimi-code": 135,
        "factory-droid": 184,
        "openhands": 181,
    }
    for client, number in issues.items():
        url = f"https://github.com/open-coder-ai/agentseam/issues/{number}"
        assert any(
            r["kind"] == "client" and client in r["clients"] and r["says"].endswith(url)
            for r in engine.warning_rules()
        ), client
    rows = yaml.safe_load((DATA / "evidence.yaml").read_text(encoding="utf-8"))
    rows["issues"] = {"cursor": 141}
    (tmp_path / "evidence.yaml").write_text(yaml.safe_dump(rows), encoding="utf-8")
    with pytest.raises(PageError, match="cursor is witnessed"):
        clientdata.load_evidence(tmp_path, witness)


def test_evidence_rows_name_untested_agents_only(tmp_path: Path) -> None:
    for client in ("claude-code", "nobody"):
        with pytest.raises(PageError, match=client):
            _evidence_copy(
                tmp_path / client, lambda d, c=client: d["issues"].update({c: 7})
            )


@pytest.mark.parametrize("number", ("141", 0, -3, None, True))
def test_evidence_issue_is_a_positive_number(tmp_path: Path, number) -> None:
    with pytest.raises(PageError, match=CLIENT):
        _evidence_copy(tmp_path, lambda d: d["issues"].update({CLIENT: number}))


def test_evidence_links_only_to_agentseam_issues(tmp_path: Path) -> None:
    with pytest.raises(PageError, match="issue_url"):
        _evidence_copy(
            tmp_path, lambda d: d.update(issue_url="https://example.com/__NUMBER__")
        )


def test_notice_shown_for_an_untested_agent(built_untested) -> None:
    built = built_untested
    notice = _site(built)["builder_clients"]["clients"][CLIENT]["evidence"]
    assert notice["url"] == URL
    assert notice["link"] == LINK
    assert f"chock has not seen {NAME} run the plugin yet" in notice["line"]
    assert "The command still builds the plugin" in notice["line"]
    builder = (built.out / "coding" / "builder" / "index.html").read_text(
        encoding="utf-8"
    )
    assert f'<p class="client-evidence" data-client="{CLIENT}" hidden>' in builder
    assert f'<a href="{URL}">{LINK}</a>' in builder
    install = (built.out / "coding" / "install" / "index.html").read_text(
        encoding="utf-8"
    )
    section = _install_section(install, CLIENT)
    assert f'<p class="client-evidence" data-client="{CLIENT}">' in section
    assert f'href="{URL}"' in section
    for page in ("builder", "install"):
        twin = (built.out / "coding" / page / "index.md").read_text(encoding="utf-8")
        assert f"[{LINK}]({URL})." in twin, page


@pytest.mark.parametrize("which", ("site", "fixture"))
def test_no_notice_for_a_witnessed_agent(request, which) -> None:
    built = request.getfixturevalue("built" if which == "site" else "built_untested")
    block = _site(built)["builder_clients"]
    witnessed = [c for c, d in block["clients"].items() if d["witness"] == "witnessed"]
    assert "claude-code" in witnessed
    builder = (built.out / "coding" / "builder" / "index.html").read_text(
        encoding="utf-8"
    )
    install = (built.out / "coding" / "install" / "index.html").read_text(
        encoding="utf-8"
    )
    for client in witnessed:
        assert block["clients"][client]["evidence"] is None, client
        assert f'class="client-evidence" data-client="{client}"' not in builder
        assert "client-evidence" not in _install_section(install, client), client
    notices = len([c for c, d in block["clients"].items() if d["evidence"]])
    assert notices >= 7
    assert builder.count('class="client-evidence"') == notices
    assert install.count('class="client-evidence"') == notices


def test_cursor_shows_no_evidence_or_untested_notice(built) -> None:
    """W-CUR: Cursor is witnessed, so the site says nothing about it being untested."""
    about = _site(built)["builder_clients"]["clients"]["cursor"]
    assert about["witness"] == "witnessed"
    assert about["evidence"] is None
    evidence_label = "Evidence wanted for Cursor."
    for page in ("builder", "install"):
        for name in ("index.html", "index.md"):
            text = (built.out / "coding" / page / name).read_text(encoding="utf-8")
            assert 'class="client-evidence" data-client="cursor"' not in text
            assert 'class="client-untested" data-client="cursor"' not in text
            assert about["untested_label"] not in text, (page, name)
            assert evidence_label not in text, (page, name)
    install = (built.out / "coding" / "install" / "index.html").read_text("utf-8")
    assert "agentseam issue #" not in _install_section(install, "cursor")


def test_the_notice_follows_the_data_row(tmp_path: Path) -> None:
    """Adding a row adds the notice; deleting it (agent witnessed, issue closed) removes it."""

    def block(evidence: dict) -> dict:
        notice = clientdata.evidence_notice(evidence, CLIENT, NAME)
        return {
            "default": "claude-code",
            "order": [CLIENT],
            "clients": {CLIENT: {"evidence": notice}},
        }

    kept = _evidence_copy(tmp_path / "kept", lambda d: None)
    html = clientpage.evidence_lines(block(kept), TEMPLATES)
    assert f'<a href="{URL}">' in html
    dropped = _evidence_copy(tmp_path / "dropped", lambda d: d["issues"].pop(CLIENT))
    assert clientdata.evidence_notice(dropped, CLIENT, NAME) is None
    assert clientpage.evidence_lines(block(dropped), TEMPLATES) == ""
