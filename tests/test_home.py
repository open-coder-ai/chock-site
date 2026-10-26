"""R-2 checks: the home page's data builds, its claims are computed, nothing banned ships."""

import dataclasses
import html as htmllib
import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

from sitegen import homedata
from sitegen.pageparts import PageError, install_command
from sitegen.render import sentence_start

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("Free forever", "pip install chock", "limit-diff-size-rule", "[stars]")
TEXT_SUFFIXES = {".html", ".md", ".txt", ".json", ".xml", ".css", ".js"}
CAVEAT = (
    "Your agent still sends context to its own model provider. Chock does not send "
    "it anywhere else. Installing fetches the policies once."
)


def _home(built) -> str:
    return (built.out / "index.html").read_text(encoding="utf-8")


def _main_text(html: str) -> str:
    main = re.search(r"<main.*?</main>", html, re.DOTALL).group(0)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", main)))


def _copy_data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    return data


def _site_json(built) -> dict:
    return json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))


def test_demo_cases_come_from_blocking_eval_cases(built, catalog_path: Path) -> None:
    assert [c.policy for c in built.site.demo] == [
        "block-no-verify",
        "scan-secrets",
        "block-curl-pipe-sh",
        "block-destructive-commands",
        "protect-agent-config",
    ]
    by_id = {c.policy: c for c in built.site.demo}
    assert by_id["block-no-verify"].command == "git commit --no-verify -m wip"
    assert by_id["scan-secrets"].command is None
    assert ".env" in by_id["scan-secrets"].files
    html = _home(built)
    for case in built.site.demo:
        assert f'id="demo-{case.policy}"' in html
        assert f'href="/coding/policies/{case.policy}/"' in html


def test_demo_has_no_invented_dialogue(built) -> None:
    text = _main_text(_home(built))
    for case in built.site.demo:
        assert f"Refused by {case.policy}:" in text
    assert "BLOCKED" not in text


def test_demo_build_fails_on_a_missing_or_non_block_case(
    built, catalog_path: Path, tmp_path: Path
) -> None:
    data = _copy_data(tmp_path)
    cases = {
        "missing": {"policy": "block-no-verify", "case": "tc-999"},
        "allow": {"policy": "block-no-verify", "case": "tc-002"},
        "hidden": {"policy": "rtk-dangerous-actions-blocker", "case": "tc-001"},
    }
    for name, entry in cases.items():
        (data / "demo.yaml").write_text(yaml.safe_dump({"demo": [entry]}), "utf-8")
        with pytest.raises(PageError):
            homedata.load_demo(catalog_path, data, built.site.policies)
        assert name


def test_incident_rows_name_visible_policies(built) -> None:
    visible = {p.id for p in built.site.policies}
    rows = built.site.incidents
    assert len(rows) == 10
    for row in rows:
        assert row.policies, row.incident
        assert set(row.policies) <= visible, row.incident
    names = " ".join(row.incident for row in rows)
    for needle in ("Log4Shell", "Spring4Shell", "Text4Shell", "Struts", "SSRF"):
        assert needle in names
    for needle in ("tj-actions", "Codecov", "MCP", "Leaked keys", "Trojan Source"):
        assert needle in names


def test_incident_build_fails_on_an_unknown_policy(built, tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    doc = yaml.safe_load((data / "incidents.yaml").read_text(encoding="utf-8"))
    doc["rows"][0]["policies"] = ["not-a-policy"]
    (data / "incidents.yaml").write_text(yaml.safe_dump(doc), "utf-8")
    with pytest.raises(PageError):
        homedata.load_incidents(data, built.site.policies)


def test_incident_copy_never_claims_prevention(built) -> None:
    text = _main_text(_home(built))
    assert "The class of flaw behind real incidents" in text
    assert "aligns with MITRE ATT&CK Initial Access, OWASP ASI01–10" in text
    assert "OWASP ASI01–10 (every mapping partial)" in text
    assert "CISA Secure by Design and NIST SSDF" in text
    assert (
        "Chock doesn't stop every attack. It closes common, known entry points." in text
    )
    for phrase in ("would have prevented", "mapped to", "would have stopped"):
        assert phrase not in text


def test_calculator_arithmetic_and_example_text(built) -> None:
    hours, money, days = homedata.savings(20, 60, 45, 100, 3)
    assert (hours, money, days) == pytest.approx((9.0, 900.0, 1.8))
    assert homedata.fmt_hours(hours) == "9"
    assert homedata.fmt_hours(1234.56) == "1,234.6"
    assert homedata.fmt_money(money) == "900"
    assert homedata.fmt_money(1234567.5) == "1,234,568"
    html = _home(built)
    defaults = yaml.safe_load((ROOT / "data" / "home.yaml").read_text("utf-8"))
    values = {i["id"]: i["value"] for i in defaults["landing"]["calc_inputs"]}
    assert values == {
        "findings": 20,
        "share": 60,
        "minutes": 45,
        "rate": 100,
        "days": 3,
    }
    text = _main_text(html)
    assert "Hours saved = findings × share covered × minutes per late fix ÷ 60" in text
    assert "These are example values, and we did not measure them." in text
    assert (
        "the formula gives 9 hours, $900 and 1.8 days. That is arithmetic on "
        "the values above. It says nothing about your own team." in text
    )
    for name in values:
        assert f'name="{name}"' in html


def test_two_pipelines_are_real_html(built) -> None:
    html = _home(built)
    today = re.search(r"<h3>Today</h3>\s*<ol[^>]*>(.*?)</ol>", html, re.DOTALL)
    with_chock = re.search(
        r"<h3>With chock</h3>\s*<ol[^>]*>(.*?)</ol>", html, re.DOTALL
    )
    assert today.group(1).count("<li>") == 5
    assert with_chock.group(1).count("<li>") == 4
    assert "SAST in CI" in today.group(1)


def test_no_model_and_local_copy(built) -> None:
    text = _main_text(_home(built))
    assert (
        "No model decides whether your code is safe. Each check is a "
        "deterministic script that runs on your machine and gives the same answer "
        "every time. When a check passes, nothing is added to the agent's context. "
        "When it refuses, the agent gets one short reason." in text
    )
    assert (
        "Chock checks code on the laptop, in the dev container or inside the cloud "
        "agent's pod. Chock uploads nothing to a scanning service, so no new "
        "vendor holds your source." in text
    )
    assert CAVEAT in text
    # No timing is shown: none was measured in this PR.
    assert not re.search(r"\b\d+(\.\d+)?\s?(ms|seconds?)\b", text)


def test_counts_labels_and_stats_are_computed(built) -> None:
    data = _site_json(built)
    policies = data["policies"]
    html = _home(built)
    tested = sum(p["eval_executed"] for p in policies)
    assert f"{len(policies)} POLICIES · {tested:,} TESTS" in html
    kinds = {
        k: sum(1 for p in policies if p["keyword"] == k)
        for k in data["label_words"]["coding"]
    }
    for key, word in data["label_words"]["coding"].items():
        assert f'dist-{key}"><span class="dist-num">{kinds[key]}</span> {word}' in html
    cards = re.search(r'id="track-coding".*?</article>', html, re.DOTALL).group(0)
    assert f"<dd>{len(policies)}</dd>" in cards
    assert f"<dd>{len(data['presets'])}</dd>" in cards
    assert f"<dd>{len(data['builder_clients']['order'])}</dd>" in cards
    assert "AVAILABLE NOW" in cards


def test_sections_block_from_tracks_yaml(built) -> None:
    html = _home(built)
    coding = re.search(r'id="track-coding".*?</article>', html, re.DOTALL).group(0)
    general = re.search(r'id="track-general".*?</article>', html, re.DOTALL).group(0)
    tracks = {t["id"]: t for t in _site_json(built)["tracks"]}
    assert tracks["coding"]["summary"].split(":")[0] in coding
    assert "DESIGN IN PROGRESS" in general
    assert "Guardrails for agents that act for a person or a business." in general
    assert "Nothing to install yet." in general
    assert 'href="/general/"' in general
    assert "<dl" not in general


def test_one_policy_every_surface_uses_the_registry_label_block(
    built, catalog_path: Path
) -> None:
    registry = yaml.safe_load((catalog_path / "registry.yaml").read_text("utf-8"))
    row = next(p for p in registry["policies"] if p["id"] == "scan-secrets")
    words = _site_json(built)["label_words"]["coding"]
    text = _main_text(_home(built))
    for client in ("claude-code", "cursor", "codex", "copilot", "devin"):
        label = row["label"].get(client)
        if label is None:  # the pinned catalog does not grade this agent yet
            assert "not graded yet for Devin" in text
            continue
        assert words[label["keyword"]] in text
        # SITE-CAPS-3: the text after the badge starts its own sentence.
        assert sentence_start(label["says"]) in text
    assert "plugin repo" not in text
    assert f"{row['eval_executed']} of {row['eval_cases']} test cases pass" in text


def test_use_cases_are_coding_only_and_drawn_from_presets(built) -> None:
    land = yaml.safe_load((ROOT / "data" / "home.yaml").read_text("utf-8"))["landing"]
    presets = {p.id: p for p in built.site.presets}
    assert [c["tab"] for c in land["usecases"]] == [
        "Solo developer",
        "Engineering team",
        "Open-source maintainer",
        "Security and compliance",
    ]
    for case in land["usecases"]:
        assert len(case["policies"]) <= 4
        assert set(case["policies"]) <= set(presets[case["preset"]].members)
    html = _home(built)
    assert html.count('data-usecase="') == 4
    assert (
        "general agents"
        not in re.search(
            r'<section class="[^"]*" aria-labelledby="use-cases">.*?</section>',
            html,
            re.DOTALL,
        )
        .group(0)
        .lower()
    )


def test_works_with_lists_every_install_client(built) -> None:
    html = _home(built)
    block = re.search(r'<section class="works".*?</section>', html, re.DOTALL).group(0)
    clients = _site_json(built)["builder_clients"]
    assert block.count('class="works-item"') == len(clients["order"]) == 11
    for client in clients["order"]:
        assert clients["clients"][client]["name"] in block


def test_install_line_follows_released(built) -> None:
    html = _home(built)
    assert 'id="home-install"' in html
    assert built.site.framework_ref in html
    assert "pipx install chock" not in html  # `released` is false
    released = dataclasses.replace(
        built.site, data={**built.site.data, "released": True}
    )
    assert install_command(released) == "pipx install chock"


def test_faq_adds_general_agents_answer(built) -> None:
    html = _home(built)
    assert "What are general agents?" in html
    assert (
        "Agents that act for a person or a business. We are still designing their "
        "guardrails, so there is nothing to install yet." in _main_text(html)
    )
    faq = (built.out / "faq" / "index.html").read_text(encoding="utf-8")
    assert "What are general agents?" in faq


def test_no_page_embeds_a_video_or_links_the_video_folder(built) -> None:
    for path in built.out.rglob("*"):
        if path.is_file() and path.suffix in (".html", ".md", ".txt", ".xml", ".json"):
            text = path.read_text(encoding="utf-8")
            assert "<video" not in text and "/video/" not in text, path
    assert not (built.out / "video").exists()


def test_no_star_counts_and_no_third_party_on_home(built) -> None:
    html = _home(built)
    assert "★" not in html
    assert not re.search(r"\bstars?\b", _main_text(html), re.IGNORECASE)
    assert "Star on GitHub" not in html
    assert (
        'href="https://github.com/open-coder-ai/chock-catalog/blob/main/CONTRIBUTING.md"'
        in html
    )
    assert re.search(
        r'href="https://github.com/open-coder-ai/chock"[^>]*>View on GitHub', html
    )


def test_home_twin_states_facts_and_asks_first(built) -> None:
    twin = (built.out / "index.md").read_text(encoding="utf-8")
    assert "ask the user before running" in twin.lower()
    assert "Ask the user first" in twin
    assert "| Log4Shell (CVE-2021-44228) |" in twin
    assert CAVEAT in twin
    assert "git commit --no-verify -m wip" in twin
    assert "Free and open source" in twin


def test_banned_texts_never_reach_dist(built) -> None:
    hits = []
    for path in built.out.rglob("*"):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            hits += [f"{path.name}: {b}" for b in BANNED if b in text]
    assert not hits, hits


def test_home_sections_in_the_specified_order(built) -> None:
    html = _home(built)
    ids = [
        "guardrails",
        "sections",
        "how-it-works",
        "every-surface",
        "use-cases",
        "honest-by-design",
        "no-model-no-tokens",
        "code-stays-local",
        "shift-left",
        "real-incidents",
        "presets",
        "where-chock-fits",
        "why-trust-it",
        "open-source",
        "questions",
        "ready",
    ]
    positions = [html.index(f'id="{i}"') for i in ids]
    assert positions == sorted(positions)


def test_home_ids_are_unique(built) -> None:
    ids = re.findall(r'\sid="([^"]+)"', _home(built))
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})
