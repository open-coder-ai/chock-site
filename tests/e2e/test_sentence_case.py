"""SITE-CAPS: text the browser renders (builder cart, chips, warnings) starts sentences uppercase."""

import json
from pathlib import Path

import pytest
import yaml
from conftest import assert_clean, collect

from tests.sentence_case import html_blocks, lowercase_starts

ROOT = Path(__file__).resolve().parents[2]
RULES = yaml.safe_load(
    (ROOT / "data" / "sentence-case.yaml").read_text(encoding="utf-8")
)
# Policies across labels (blocks, asks, warns, advisory) so every chip and warning shows.
PICKS = "block-no-verify,scan-secrets-entropy,limit-diff-size,agent-discipline,protect-main-branch"
UPSTREAM = [start for row in RULES["upstream"] for start in row["starts"]]


def _lowercase(page, site_url: str) -> list[str]:
    """Lowercase sentence starts in the rendered DOM, less the listed upstream text."""
    site = json.loads(page.request.get(site_url + "/data/site.json").text())
    names = frozenset(RULES["names"]) | {p["id"] for p in site["policies"]}
    found = [s for b in html_blocks(page.content()) for s in lowercase_starts(b, names)]
    return [s for s in found if not any(s.startswith(u) for u in UPSTREAM)]


@pytest.mark.parametrize("client", ["claude-code", "goose"])
def test_builder_text_starts_uppercase(page, site_url, client) -> None:
    """The builder with picks, tested and untested agent: cart rows, chips, warnings, command."""
    collect(page, site_url)
    page.goto(f"{site_url}/coding/builder/#client={client}&p={PICKS}")
    page.wait_for_selector("#builder-status:not(:empty)", state="attached")
    page.wait_for_selector("[data-selection-code]", state="attached")
    assert page.locator(".sel-count").inner_text() == "5 policies"
    assert _lowercase(page, site_url) == []
    assert_clean(page)


@pytest.mark.parametrize(
    "path", ["/", "/coding/policies/", "/coding/policies/scan-secrets/", "/report/"]
)
def test_rendered_pages_start_uppercase(page, site_url, path) -> None:
    """Pages whose chips and lists the scripts fill in, read after the scripts run."""
    collect(page, site_url)
    page.goto(site_url + path)
    page.wait_for_load_state("networkidle")
    assert _lowercase(page, site_url) == []
    assert_clean(page)
