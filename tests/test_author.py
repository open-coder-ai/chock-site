"""Tests for the author page's data, generated files and wiring (BV-S2)."""

import json
import re
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path, PurePosixPath

import pytest
import yaml

from sitegen import authordata
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
KINDS = {"content_regex", "guard", "rule", "script", "skill"}
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' "
    "data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
    "base-uri 'none'; form-action 'none'"
)
TOKENS = ("__ID__", "__NAME__", "__DATE__")

TEXT_KEYS = {
    "noscript",
    "kind_legend",
    "name_label",
    "name_hint",
    "name_example",
    "interview_hint",
    "catalog_heading",
    "catalog_hint",
    "advanced_heading",
    "advanced_hint",
    "advanced_reset",
    "selection_heading",
    "selection_hint",
    "script_heading",
    "script_hint",
    "sha_label",
    "download_label",
    "copy_label",
    "share_label",
    "share_hint",
    "clear_label",
    "clear_done",
    "saved_note",
    "errors_title",
    "required",
    "id_invalid",
    "control_chars",
    "refuse_match",
    "pass_match",
    "refuse_pattern",
    "pass_pattern",
    "refuse_name",
    "pass_name",
    "rule_too_long",
    "not_ready",
    "unknown_catalog",
    "untested_note",
    "file_edited",
    "link_unreadable",
}
SCRIPT_KEYS = {
    "file_name",
    "default_agent",
    "default_folder",
    "default_mode",
    "agent_prompt",
    "folder_prompt",
    "mode_prompt",
    "bundle_name",
}


def _author(built) -> dict:
    """The emitted dist/data/author.json."""
    return json.loads((built.out / "data" / "author.json").read_text(encoding="utf-8"))


def _author_html(built) -> str:
    return (built.out / "coding" / "author" / "index.html").read_text(encoding="utf-8")


def test_kind_templates_match_the_engine_byte_for_byte() -> None:
    engine_kinds = files("chock.scaffold.data") / "kinds"
    for kind_dir in sorted((DATA / "kinds").iterdir()):
        if not kind_dir.is_dir():
            continue
        copied = {
            p.relative_to(kind_dir).as_posix(): p.read_bytes()
            for p in kind_dir.rglob("*.tmpl")
        }
        engine_files = {
            p.relative_to(engine_kinds / kind_dir.name).as_posix(): p.read_bytes()
            for p in (engine_kinds / kind_dir.name).rglob("*.tmpl")
        }
        assert copied == engine_files, (
            f"{kind_dir.name} templates drifted from the engine"
        )


def test_engine_commit_matches_framework_ref() -> None:
    commit = (DATA / "kinds" / "engine-commit.txt").read_text(encoding="utf-8").strip()
    assert commit == (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()


def test_installed_engine_is_the_pinned_commit() -> None:
    commit = (DATA / "kinds" / "engine-commit.txt").read_text(encoding="utf-8").strip()
    direct_url = json.loads(distribution("chock").read_text("direct_url.json") or "{}")
    assert direct_url.get("vcs_info", {}).get("commit_id") == commit, (
        "install chock from git at data/kinds/engine-commit.txt"
    )


@pytest.mark.parametrize("policy_id", ["my-a", "my-a-b", "my-0"])
def test_js_path_order_matches_the_engine(policy_id: str) -> None:
    # author.js sorts paths as strings; compute_pack_hash sorts Path objects by part.
    author = authordata.load_author(DATA)
    for kind, spec in author["kinds"].items():
        paths = [path.replace("__ID__", policy_id) for path in spec["files"]]
        assert all(path.isascii() for path in paths), kind
        assert sorted(paths) == [
            p.as_posix() for p in sorted(map(PurePosixPath, paths))
        ], kind


def test_author_yaml_covers_the_five_kinds() -> None:
    author = authordata.load_author(DATA)
    assert set(author["kinds"]) == KINDS
    assert TEXT_KEYS <= set(author["texts"])
    assert SCRIPT_KEYS <= set(author["script"])
    for kind, spec in author["kinds"].items():
        assert spec["fields"] and spec["edits"] and spec["evals"]
        assert spec["files"], kind
        assert all(not path.endswith(".tmpl") for path in spec["files"])


def test_only_known_tokens_left_in_templates() -> None:
    author = authordata.load_author(DATA)
    for kind, spec in author["kinds"].items():
        for path, text in spec["files"].items():
            found = set(re.findall(r"__[A-Z_]+__", text))
            assert found <= set(TOKENS), (
                f"{kind}/{path}: unknown tokens {found - set(TOKENS)}"
            )


def test_a_stale_anchor_fails_the_build() -> None:
    config = yaml.safe_load((DATA / "author.yaml").read_text(encoding="utf-8"))
    spec = config["kinds"]["guard"]
    files = authordata._kind_files(DATA / "kinds" / "guard")
    edit = next(e for e in spec["edits"] if e.get("find"))
    edit["find"] = "this anchor does not exist in the template"
    with pytest.raises(PageError, match="anchor occurs 0 times"):
        authordata._check_kind("guard", spec, files)


def test_author_json_emitted(built) -> None:
    author = _author(built)
    assert author["schema_version"] == 1
    assert set(author["kinds"]) == KINDS
    pin = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
    assert author["engine_commit"] == pin
    guard_files = author["kinds"]["guard"]["files"]
    assert "implementations/__ID__.py" in guard_files


def test_author_page_structure(built) -> None:
    html = _author_html(built)
    assert html.count("<h1") == 1
    assert f'content="{CSP}"' in html
    assert 'lang="en"' in html
    for kind in KINDS:
        assert f'value="{kind}"' in html
    assert "localStorage draft" in html
    assert "<noscript>" in html
    assert 'src="/js/common.js"' in html
    assert 'src="/js/author.js"' in html


def test_author_page_in_nav_and_llms(built) -> None:
    html = _author_html(built)
    assert 'href="/coding/author/"' in html
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    assert "/coding/author/index.md" in llms
    builder = (built.out / "coding" / "builder" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'href="/coding/author/"' in builder


def test_author_markdown_twin(built) -> None:
    twin = (built.out / "coding" / "author" / "index.md").read_text(encoding="utf-8")
    pin = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
    assert pin[:12] in twin
    for spec in authordata.load_author(DATA)["kinds"].values():
        assert spec["title"] in twin


def test_author_js_uses_no_forbidden_apis() -> None:
    src = (ROOT / "static" / "js" / "author.js").read_text(encoding="utf-8")
    for banned in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "eval(",
        "new Function",
    ):
        assert banned not in src, banned
    assert not re.search(r"setTimeout\s*\(\s*['\"`]", src)


def test_every_kind_builds_files_the_engine_would_validate(built) -> None:
    # The engine needs a manifest plus an eval suite per kind; guard and script
    # also ship an implementation file.
    author = _author(built)
    for spec in author["kinds"].values():
        assert "manifest.yaml" in spec["files"]
        assert "evals/suite.yaml" in spec["files"]
    assert "implementations/__ID__.py" in author["kinds"]["guard"]["files"]
    assert "implementations/check.py" in author["kinds"]["script"]["files"]
    assert "skill/body.md" in author["kinds"]["skill"]["files"]
