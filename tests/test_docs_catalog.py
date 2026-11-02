"""DOCS-4: the catalog pages, their snapshot of the pinned catalog, and the recorded adopt run."""

import html
import json
import re
import shlex
import shutil
from pathlib import Path

import pytest
import yaml
from chock.scaffold.new import KINDS

from sitegen import catalogdoc
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
SOURCE = DATA / catalogdoc.SOURCE_DIR
CATALOG_REF = (ROOT / ".catalog-ref").read_text(encoding="utf-8").strip()
ENGINE_REF = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
PAGES = ("catalog-adopt", "catalog-contribute")


def _page(built, key: str) -> tuple[str, str]:
    """A catalog page's HTML, unescaped, and its Markdown twin."""
    folder = built.out / DOCS["pages"][key]["path"].strip("/")
    return (
        html.unescape((folder / "index.html").read_text(encoding="utf-8")),
        (folder / "index.md").read_text(encoding="utf-8"),
    )


def test_catalog_pages_are_one_nav_group() -> None:
    group = next(g for g in DOCS["nav"] if g["group"] == "Catalog")
    assert tuple(group["pages"]) == PAGES


def test_snapshot_matches_the_pinned_catalog(catalog_path: Path) -> None:
    files = catalogdoc.snapshot(catalog_path, DOCS, CATALOG_REF)
    present = {p.name for p in SOURCE.iterdir()} - {catalogdoc.ADOPT_JSON}
    assert set(files) == present
    for name, text in files.items():
        assert (SOURCE / name).read_text(encoding="utf-8") == text, name


def test_snapshot_taken_at_another_catalog_commit_is_refused() -> None:
    with pytest.raises(PageError, match="catalog-ref"):
        catalogdoc.load(DATA, "0" * 40)


def test_quote_drops_html_comments() -> None:
    text = "## A\n\n<!-- gen:x -->25<!-- /gen --> of them.\n\n## B\n\nno\n"
    want = [{"sections": ["A"], "level": 2}]
    assert catalogdoc.quoted(text, want) == "## A\n\n25 of them.\n"


def test_trees_and_gates_are_read_from_the_checkout(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "trees.py").write_text('TREES = ("base", "extra")\n')
    for folder in ("base/one", "base/two", "extra/three", "base/notes"):
        (tmp_path / folder).mkdir(parents=True)
    for policy in ("base/one", "base/two", "extra/three"):
        (tmp_path / policy / "manifest.yaml").write_text("id: x\n")
    assert catalogdoc.trees(tmp_path) == [
        {"tree": "base", "policies": 2},
        {"tree": "extra", "policies": 1},
    ]
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "jobs:\n  a:\n    if: x\n    steps:\n      - name: S\n      - run: r\n"
        "  b:\n    steps: []\n"
    )
    assert catalogdoc.gates(tmp_path) == [
        {"job": "a", "if": "x", "steps": ["S"]},
        {"job": "b", "if": None, "steps": []},
    ]


def test_adopt_run_is_at_both_pins_and_refuses_the_commit_to_main() -> None:
    adopt = json.loads((SOURCE / catalogdoc.ADOPT_JSON).read_text(encoding="utf-8"))
    assert adopt["engine"] == ENGINE_REF
    assert adopt["catalog"] == CATALOG_REF
    script = catalogdoc.load_script(DATA, CATALOG_REF)
    assert [shlex.split(e["command"]) for e in adopt["examples"]] == [
        s["run"] for s in script["steps"]
    ]
    adds = [e for e in adopt["examples"] if e["command"].startswith("chock add")]
    assert adds and all(f"--ref {CATALOG_REF}" in e["command"] for e in adds)
    refused = next(e for e in adopt["examples"] if "--allow-empty" in e["command"])
    assert refused["exit"] == 1
    assert "protected branch" in refused["output"]
    assert adopt["examples"][-1]["exit"] == 0


def test_adopt_page_shows_every_step_with_its_exit_code(built) -> None:
    page, twin = _page(built, "catalog-adopt")
    adopt = json.loads((SOURCE / catalogdoc.ADOPT_JSON).read_text(encoding="utf-8"))
    for example in adopt["examples"]:
        step = f"Step {example['step']}, exit code {example['exit']}."
        for text in (page, twin):
            assert f"$ {example['command']}" in text
            assert step in text


def test_contribute_page_names_every_kind_the_engine_has(built) -> None:
    page, twin = _page(built, "catalog-contribute")
    named = re.search(r"one kind: (.+?)\.", twin).group(1)
    assert set(re.findall(r"`(\w+)`", named)) == set(KINDS)
    assert "chock new policy <id> --kind content_regex --repo ." in page


def test_contribute_page_lists_every_ci_job_and_tree(built) -> None:
    page, twin = _page(built, "catalog-contribute")
    for gate in json.loads((SOURCE / catalogdoc.GATES_JSON).read_text("utf-8")):
        assert f"| {gate['job']} |" in twin
        assert gate["job"] in page
    for tree in json.loads((SOURCE / catalogdoc.TREES_JSON).read_text("utf-8")):
        assert f"| {tree['tree']} | {tree['policies']} |" in twin


def test_no_ci_job_runs_the_adoption_transcripts(catalog_path: Path) -> None:
    # texts.catalog.gates_intro says so; a catalog pin that adds it must reword the page.
    ci = (catalog_path / catalogdoc.CI_FILE).read_text(encoding="utf-8")
    assert "gen_adoption_transcript" not in ci
    assert (
        "No job runs `tools/gen_adoption_transcript.py`"
        in (DOCS["texts"]["catalog"]["gates_intro"])
    )


def test_regen_lists_the_generators_regen_all_runs(catalog_path: Path) -> None:
    regen = catalogdoc.regen(catalog_path)
    assert regen["doc"].startswith("Regenerate every derived file")
    assert regen["scripts"][0] == "tools/gen_lib_copies.py"
    assert "tools/gen_registry.py" in regen["scripts"]
    assert all((catalog_path / s).is_file() for s in regen["scripts"])


# --- SITE-1: snapshot names, quoted paths and setup steps are checked -------------------


def test_a_snapshot_name_that_leaves_the_folder_is_refused(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    source = data / catalogdoc.SOURCE_DIR / catalogdoc.SOURCE_JSON
    record = json.loads(source.read_text(encoding="utf-8"))
    (tmp_path / "escaped").write_text("outside", encoding="utf-8")
    first = next(iter(record["files"]))
    record["files"][first] = "../../../escaped"
    source.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(PageError, match="'../../../escaped'"):
        catalogdoc.load(data, CATALOG_REF)


def test_a_quoted_path_that_leaves_the_catalog_is_refused(catalog_path: Path) -> None:
    docs = json.loads(json.dumps(DOCS))
    quote = next(
        part
        for page in docs["pages"].values()
        for part in page.get("catalog", [])
        if "quote" in part
    )
    quote["quote"] = "../../etc/hostname"
    with pytest.raises(PageError, match="'../../etc/hostname'"):
        catalogdoc.snapshot(catalog_path, docs, CATALOG_REF)


def _adopt_with_setup(tmp_path: Path, setup: object) -> Path:
    script = yaml.safe_load((DATA / catalogdoc.ADOPT_YAML).read_text(encoding="utf-8"))
    script["setup"] = setup
    (tmp_path / catalogdoc.ADOPT_YAML).write_text(yaml.safe_dump(script), "utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "setup",
    [
        [["touch", "pwned"]],
        [["sh", "-c", "touch pwned"]],
        [{"sh": "touch pwned"}],
        ["git init"],
        [[]],
        "git init",
    ],
)
def test_a_setup_step_outside_the_allowlist_is_refused(
    tmp_path: Path, setup: object
) -> None:
    with pytest.raises(PageError, match="setup"):
        catalogdoc.load_script(_adopt_with_setup(tmp_path, setup), CATALOG_REF)


def test_the_committed_setup_is_allowlisted() -> None:
    script = catalogdoc.load_script(DATA, CATALOG_REF)
    assert all(argv[0] in catalogdoc.PROGRAMS for argv in script["setup"])


def _git_script(steps: list[dict]) -> dict:
    """A git-only adopt script, so the run needs no network and no catalog."""
    return {
        "repo": "/work/demo",
        "home": "/home/demo",
        "setup": [["git", "init", "-q", "-b", "main", "."]],
        "steps": steps,
    }


def test_a_step_whose_exit_is_not_the_expected_one_fails_the_run() -> None:
    script = _git_script([{"run": ["git", "rev-parse", "HEAD"]}])
    with pytest.raises(PageError, match=r"adopt step 1.*exit 128.*expected 0"):
        catalogdoc.run_adopt(script, ENGINE_REF, CATALOG_REF)


def test_a_declared_exit_is_the_expected_one() -> None:
    script = _git_script([{"run": ["git", "rev-parse", "HEAD"], "exit": 128}])
    adopt = catalogdoc.run_adopt(script, ENGINE_REF, CATALOG_REF)
    assert [e["exit"] for e in adopt["examples"]] == [128]


def test_a_declared_exit_the_step_does_not_give_fails_the_run() -> None:
    script = _git_script([{"run": ["git", "status", "-s"], "exit": 1}])
    with pytest.raises(PageError, match=r"adopt step 1.*exit 0.*expected 1"):
        catalogdoc.run_adopt(script, ENGINE_REF, CATALOG_REF)


@pytest.mark.parametrize("declared", ["1", True, -1, 1.5, None, [1]])
def test_a_step_exit_that_is_not_a_small_integer_is_refused(
    tmp_path: Path, declared: object
) -> None:
    script = yaml.safe_load((DATA / catalogdoc.ADOPT_YAML).read_text(encoding="utf-8"))
    script["steps"][0]["exit"] = declared
    (tmp_path / catalogdoc.ADOPT_YAML).write_text(yaml.safe_dump(script), "utf-8")
    with pytest.raises(PageError, match="exit"):
        catalogdoc.load_script(tmp_path, CATALOG_REF)


def test_the_committed_script_declares_the_refused_commit_and_nothing_else() -> None:
    script = catalogdoc.load_script(DATA, CATALOG_REF)
    declared = {s["run"][2]: s["exit"] for s in script["steps"] if "exit" in s}
    assert declared == {"--allow-empty": 1}
    adopt = json.loads((SOURCE / catalogdoc.ADOPT_JSON).read_text(encoding="utf-8"))
    for step, example in zip(script["steps"], adopt["examples"], strict=True):
        assert example["exit"] == step.get("exit", 0)
