"""R-3: the builder's start-screen questions are data, checked against presets and labels."""

import json
from pathlib import Path

import pytest
import yaml

from sitegen import engine
from sitegen.pageparts import PageError
from sitegen.presets import load_presets
from sitegen.quiz import load_quiz

DATA = Path(__file__).resolve().parents[1] / "data"
LABELS = set(engine.label_words())


def _presets():
    return load_presets(DATA / "presets.yaml")


def _clients() -> dict:
    """The parts of the builder_clients block the quiz reads, from witness.yaml and the engine."""
    witness = yaml.safe_load((DATA / "witness.yaml").read_text(encoding="utf-8"))
    return {
        "default": witness["default"],
        "order": list(witness["clients"]),
        "clients": {
            client: {"name": engine.client_name(client), "witness": state}
            for client, state in witness["clients"].items()
        },
    }


def _data_copy(tmp_path: Path, edit) -> Path:
    """A copy of data/quiz.yaml, changed by `edit(quiz)`, in its own data dir."""
    quiz = yaml.safe_load((DATA / "quiz.yaml").read_text(encoding="utf-8"))
    edit(quiz)
    (tmp_path / "quiz.yaml").write_text(yaml.safe_dump(quiz), encoding="utf-8")
    return tmp_path


def test_real_quiz_validates() -> None:
    quiz = load_quiz(DATA, _presets(), LABELS, _clients())
    assert [q["id"] for q in quiz["questions"]] == ["agent", "worries", "strictness"]


def test_every_worry_preset_is_a_preset() -> None:
    preset_ids = {p.id for p in _presets()}
    worries = load_quiz(DATA, _presets(), LABELS, _clients())["questions"][1]["options"]
    assert len(worries) == 8
    for worry in worries:
        assert worry["presets"]
        assert set(worry["presets"]) <= preset_ids


def test_worries_map_to_the_planned_presets() -> None:
    worries = load_quiz(DATA, _presets(), LABELS, _clients())["questions"][1]["options"]
    mapping = {w["label"]: w["presets"] for w in worries}
    assert mapping == {
        "Leaked secrets": ["secrets"],
        "Skipped checks": ["git-hygiene", "test-integrity"],
        "Destructive or risky shell": ["shell-containment"],
        "The agent changing its rules": ["agent-config"],
        "Packages and CI": ["supply-chain", "ci-pipeline"],
        "Injected instructions": ["prompt-injection"],
        "Insecure code and cloud": ["code-hardening", "cloud-iac"],
        "Compliance": ["owasp-agentic-top10", "eu-ai-act"],
    }


def test_strictness_levels_nest() -> None:
    options = load_quiz(DATA, _presets(), LABELS, _clients())["questions"][2]["options"]
    allowed = [o["allow"] for o in options]
    assert allowed == [
        ["block", "ask"],
        ["block", "ask", "warn"],
        ["block", "ask", "warn", "advise"],
    ]


def test_every_agent_continues_and_matches_the_engine_clients() -> None:
    options = load_quiz(DATA, _presets(), LABELS, _clients())["questions"][0]["options"]
    assert not [o["id"] for o in options if o.get("other")]
    assert sorted(o["id"] for o in options) == sorted(engine.client_ids())


def test_agent_options_follow_witness_yaml() -> None:
    """Names come from the engine and the tested/untested line from witness.yaml, never quiz.yaml."""
    clients = _clients()
    question = load_quiz(DATA, _presets(), LABELS, clients)["questions"][0]
    assert [o["id"] for o in question["options"]] == clients["order"]
    for option in question["options"]:
        about = clients["clients"][option["id"]]
        assert option["label"] == about["name"]
        assert option["sub"] == question["subs"][about["witness"]]
        assert bool(option.get("default")) == (option["id"] == clients["default"])
    raw = (DATA / "quiz.yaml").read_text(encoding="utf-8")
    assert "Codex" not in raw and "claude-code" not in raw


def test_agent_options_in_quiz_yaml_fail(tmp_path: Path) -> None:
    def edit(quiz) -> None:
        quiz["questions"][0]["options"] = [
            {"id": "codex", "label": "Codex", "sub": "x"}
        ]

    with pytest.raises(PageError, match="witness.yaml"):
        load_quiz(_data_copy(tmp_path, edit), _presets(), LABELS, _clients())


def test_unknown_preset_id_fails(tmp_path: Path) -> None:
    def edit(quiz) -> None:
        quiz["questions"][1]["options"][0]["presets"] = ["no-such-preset"]

    with pytest.raises(PageError, match="no-such-preset"):
        load_quiz(_data_copy(tmp_path, edit), _presets(), LABELS, _clients())


def test_unknown_label_fails(tmp_path: Path) -> None:
    def edit(quiz) -> None:
        quiz["questions"][2]["options"][0]["allow"] = ["block", "deny"]

    with pytest.raises(PageError, match="deny"):
        load_quiz(_data_copy(tmp_path, edit), _presets(), LABELS, _clients())


def test_single_question_needs_one_default(tmp_path: Path) -> None:
    def edit(quiz) -> None:
        quiz["questions"][2]["options"][0]["default"] = True

    with pytest.raises(PageError, match="exactly one default"):
        load_quiz(_data_copy(tmp_path, edit), _presets(), LABELS, _clients())


def test_site_json_carries_the_quiz(built) -> None:
    data = json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))
    assert data["quiz"]["questions"][1]["options"][0]["presets"] == ["secrets"]


def test_builder_page_has_the_hidden_start_screen(built) -> None:
    html = (built.out / "coding" / "builder" / "index.html").read_text(encoding="utf-8")
    assert (
        '<section class="quiz" id="quiz" aria-labelledby="quiz-title" hidden>' in html
    )
    assert "Skip to the full builder" in html
    assert 'id="builder-full"' in html
    # The noscript text from before stands, and no inline script or style appears.
    assert "The builder needs JavaScript." in html
    assert "<script>" not in html and "style=" not in html


def test_twin_lists_the_questions(built) -> None:
    twin = (built.out / "coding" / "builder" / "index.md").read_text(encoding="utf-8")
    assert "Which agent do you use?" in twin
    assert "Leaked secrets" in twin and "presets: secrets" in twin


def test_quiz_yaml_is_the_only_copy_of_the_questions() -> None:
    js = (Path(__file__).resolve().parents[1] / "static" / "js" / "quiz.js").read_text(
        encoding="utf-8"
    )
    for text in ("Which agent do you use?", "Leaked secrets", "Only hard stops"):
        assert text not in js
