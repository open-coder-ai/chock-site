"""The builder's start-screen questions (data/quiz.yaml), checked against the catalog data."""

from pathlib import Path
from typing import Any

import yaml

from .model import Preset
from .pageparts import PageError

QUIZ_YAML = "quiz.yaml"
KINDS = ("single", "multi")


def _check_options(question: dict[str, Any]) -> list[dict[str, Any]]:
    """The question's options, each with an id and a label; ids are unique."""
    options = question.get("options") or []
    if not options:
        raise PageError(f"quiz.yaml: question {question.get('id')} has no options")
    seen: set[str] = set()
    for option in options:
        for key in ("id", "label", "sub"):
            if not option.get(key):
                raise PageError(f"quiz.yaml: {question['id']} option lacks {key}")
        if option["id"] in seen:
            raise PageError(f"quiz.yaml: {question['id']} repeats {option['id']}")
        seen.add(option["id"])
    return options


def load_quiz(
    data_dir: Path, presets: list[Preset], label_keywords: set[str]
) -> dict[str, Any]:
    """quiz.yaml; a worry naming an unknown preset or a strictness naming an unknown label fails."""
    quiz = yaml.safe_load((data_dir / QUIZ_YAML).read_text(encoding="utf-8"))
    preset_ids = {p.id for p in presets}
    questions = quiz.get("questions") or []
    if [q.get("id") for q in questions] != ["agent", "worries", "strictness"]:
        raise PageError("quiz.yaml: the questions must be agent, worries, strictness")
    for question in questions:
        if question.get("kind") not in KINDS:
            raise PageError(f"quiz.yaml: {question['id']} kind not in {KINDS}")
        options = _check_options(question)
        defaults = [o for o in options if o.get("default")]
        if question["kind"] == "single" and len(defaults) != 1:
            raise PageError(f"quiz.yaml: {question['id']} needs exactly one default")
        for option in options:
            unknown = [p for p in option.get("presets", []) if p not in preset_ids]
            if unknown:
                raise PageError(
                    f"quiz.yaml: {option['id']} names unknown presets {unknown}"
                )
            if question["id"] == "worries" and not option.get("presets"):
                raise PageError(f"quiz.yaml: worry {option['id']} adds no preset")
            bad = [k for k in option.get("allow", []) if k not in label_keywords]
            if bad:
                raise PageError(
                    f"quiz.yaml: {option['id']} allows unknown labels {bad}"
                )
            if question["id"] == "strictness" and not option.get("allow"):
                raise PageError(f"quiz.yaml: strictness {option['id']} allows nothing")
    return quiz
