"""Site review fixes (SR-1): agent named on grades, --apply per agent, plain wording."""

import html
import re

import yaml
from conftest import DATA

from sitegen.catalog import plain_change


def _text(path) -> str:
    return path.read_text(encoding="utf-8")


def _visible(page: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))


def test_policies_list_names_the_agent_behind_its_counts(built) -> None:
    note = "Labels and counts are the catalog's grades on Claude Code"
    assert note in _visible(_text(built.out / "coding/policies/index.html"))
    assert note in _text(built.out / "coding/policies/index.md")
    assert note in _visible(_text(built.out / "coding/index.html"))


def test_builder_names_the_agent_behind_its_static_labels(built) -> None:
    page = _text(built.out / "coding/builder/index.html")
    assert "Labels and counts are the catalog&#x27;s grades on Claude Code." in page


def test_home_command_has_no_apply_and_says_who_gets_it(built) -> None:
    page = _visible(_text(built.out / "index.html"))
    twin = _text(built.out / "index.md")
    for text in (page, twin):
        assert "--client <agent> --apply" not in text
        assert "--client <agent>" in text
        assert "For an agent marked tested, the command adds --apply" in text


def test_promotion_changelog_reads_in_plain_words(built) -> None:
    for path in (built.out / "coding/policies").glob("*/index.*"):
        text = _text(path)
        assert "promotion rule" not in text, path
        assert "BV-C3" not in text, path


def test_plain_change_leaves_other_entries_alone() -> None:
    rewrites = yaml.safe_load((DATA / "site.json").read_text(encoding="utf-8"))[
        "texts"
    ]["change_rewrites"]
    raw = (
        "Status draft -> production by the BV-C3 promotion rule, measured at "
        "catalog main 9e3e2fe: every eval case executed. Behaviour unchanged."
    )
    assert plain_change(raw, rewrites) == (
        "Promoted from draft to production: every test case ran and passed, "
        "and no bug report was open. Behaviour unchanged."
    )
    assert plain_change("Fix a false positive.", rewrites) == "Fix a false positive."


def test_repos_intro_does_not_single_out_one_agent() -> None:
    repos = _text(DATA / "repos.yaml")
    assert "inside Claude Code" not in repos
