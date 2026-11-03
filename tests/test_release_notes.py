"""P-6c: the release-notes page lists the newest versions and links their entries, without embedding them."""

import re
from pathlib import Path

import yaml

from sitegen.docsmd import first_titles, github_anchor

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))
ENTRY = DOCS["pages"]["release-notes"]["prose"][0]
CHANGELOG = (DATA / "docs-source" / "CHANGELOG.md").read_text(encoding="utf-8")


def _page(built, name: str) -> str:
    path = built.out / "docs" / "release-notes" / name
    return path.read_text(encoding="utf-8")


def test_github_anchor_matches_what_github_makes_of_a_heading() -> None:
    assert github_anchor("1.0.0 - 2026-11-02") == "100---2026-11-02"
    assert github_anchor("0.15.2 — Script hashes skip Python bytecode") == (
        "0152--script-hashes-skip-python-bytecode"
    )
    assert github_anchor("It's `code`, Ünï") == "its-code-ünï"


def test_first_titles_takes_the_newest_level_two_headings_outside_fences() -> None:
    text = "# T\n\n## A\n\n```\n## not\n```\n\n## B\n\n### sub\n\n## C\n"
    assert first_titles(text, 2) == ["A", "B"]
    assert first_titles(text, 9) == ["A", "B", "C"]


def test_page_links_each_of_the_newest_versions_at_the_pinned_commit(built) -> None:
    titles = first_titles(CHANGELOG, ENTRY["first"])
    assert len(titles) == ENTRY["first"] and ENTRY["headings"] is True
    page, twin = _page(built, "index.html"), _page(built, "index.md")
    base = f"/blob/{built.site.framework_ref}/CHANGELOG.md#"
    for title in titles:
        assert (base + github_anchor(title)) in page
        assert (base + github_anchor(title)) in twin
    assert len(re.findall(r"CHANGELOG\.md#", page)) == len(titles)


def test_page_does_not_embed_the_entries(built) -> None:
    page = _page(built, "index.html")
    body = CHANGELOG.split("\n", 1)[1]
    assert len(page.encode()) < 20_000
    assert body.strip().splitlines()[2] not in page
