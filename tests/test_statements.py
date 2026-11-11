"""LN-6: statements the site makes about itself agree with the build and with each other."""

import re
from pathlib import Path

import pytest
import yaml

from sitegen import docs as docs_module

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE_URL = "https://chock.sh"
BEACON = "static.cloudflareinsights.com/beacon"
NO_COUNT_CLAIMS = ("no page views", "nothing tracked", "nothing is tracked")
TIME_CLAIM = re.compile(r"\b(?:seconds?|minutes?|hours?)\b", re.IGNORECASE)
COUNTED_CLIENTS = re.compile(
    r"\b(?:\d+|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) client ids\b",
    re.IGNORECASE,
)
ONE_AGENTS = re.compile(r"(?<![\d,.])1 agents\b")


def _texts(out: Path) -> list[tuple[Path, str]]:
    """Every built page, twin and text file with its text."""
    return [
        (path, path.read_text(encoding="utf-8"))
        for suffix in ("*.html", "*.md", "*.txt")
        for path in sorted(out.rglob(suffix))
    ]


def _beacon_in_build(out: Path) -> bool:
    """Whether the build ships the page-view beacon loader."""
    return any(BEACON in p.read_text(encoding="utf-8") for p in out.rglob("*.js"))


def test_the_build_ships_the_page_view_beacon(built) -> None:
    assert _beacon_in_build(built.out)


def test_no_page_denies_page_views_while_the_beacon_is_in_the_build(built) -> None:
    if not _beacon_in_build(built.out):
        return
    for path, text in _texts(built.out):
        for claim in NO_COUNT_CLAIMS:
            assert claim not in text.lower(), f"{path}: {claim!r}"


@pytest.mark.parametrize(
    ("page", "start"),
    [
        ("index.md", "- Do you collect anything about me?"),
        ("faq/index.md", "### Do you collect anything about me?"),
        ("security/index.md", "## What the site does"),
        ("security/index.md", "## What this site counts"),
    ],
)
def test_every_tracking_statement_says_page_views_are_counted(
    built, page: str, start: str
) -> None:
    if not _beacon_in_build(built.out):
        return
    text = (built.out / page).read_text(encoding="utf-8")
    statement = text.split(start, 1)[1].split("\n#", 1)[0].split("\n- ", 1)[0]
    assert "counts page views" in statement, statement


def test_the_home_call_to_action_makes_no_time_claim(built) -> None:
    home = yaml.safe_load((DATA / "home.yaml").read_text(encoding="utf-8"))["landing"]
    for key in ("cta_heading", "cta_sub"):
        assert not TIME_CLAIM.search(home[key]), home[key]
    twin = (built.out / "index.md").read_text(encoding="utf-8")
    assert f"{home['cta_heading']} {home['cta_sub']}" in twin
    assert "in a minute" not in twin.lower()


def test_no_page_states_a_number_of_client_ids(built) -> None:
    for path, text in _texts(built.out):
        assert not COUNTED_CLIENTS.search(text), path


def test_no_page_says_one_agents(built) -> None:
    for path, text in _texts(built.out):
        assert not ONE_AGENTS.search(text), path


@pytest.mark.parametrize("key", ["grade_row", "basis_row"])
def test_count_rows_have_a_singular_wording(key: str) -> None:
    texts = yaml.safe_load((DATA / "docs.yaml").read_text(encoding="utf-8"))["texts"]

    class Ctx:
        """The one field `_row` reads."""

    ctx = Ctx()
    ctx.texts = texts
    assert docs_module._row(ctx, key, 1) == texts[key + "_one"]
    assert docs_module._row(ctx, key, 2) == texts[key]
    assert texts[key + "_one"].endswith("__COUNT__ agent")
    assert texts[key].endswith("__COUNT__ agents")


def test_llms_txt_links_are_absolute_and_llms_full_headings_are_paths(built) -> None:
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)]*)\)", llms)
    assert targets
    for target in targets:
        assert target.startswith(SITE_URL + "/"), target
    full = (built.out / "llms-full.txt").read_text(encoding="utf-8")
    assert re.search(r"^# /index\.md$", full, re.MULTILINE)


def test_security_page_sends_vulnerability_reports_to_the_report_page(built) -> None:
    report = yaml.safe_load((DATA / "report.yaml").read_text(encoding="utf-8"))
    anchor = f"/report/#{report['security']['id']}"
    repos = re.findall(
        r"open-coder-ai/([a-z-]+)/security/advisories/new",
        " ".join(link["url"] for link in report["security"]["links"]),
    )
    assert sorted(repos) == ["chock", "chock-catalog", "chock-site"]
    page = (built.out / "security" / "index.html").read_text(encoding="utf-8")
    twin = (built.out / "security" / "index.md").read_text(encoding="utf-8")
    assert f'href="{anchor}"' in page
    assert f"\n{SITE_URL}{anchor}\n" in twin
    section = twin.split("## How to report a problem", 1)[1].split("\n## ", 1)[0]
    for repo in repos:
        assert re.search(rf"\b{re.escape(repo)}\b(?!-)", section), repo
    assert "SECURITY.md" not in section
    target = (built.out / "report" / "index.html").read_text(encoding="utf-8")
    assert f'id="{report["security"]["id"]}"' in target
