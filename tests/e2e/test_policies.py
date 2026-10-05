"""The policies list: row count, label chips, search, and the no-JS fallback."""

import json
import urllib.request

from conftest import screenshot

VISIBLE = ".row[data-policy-id]:not(.hidden)"


def _catalog_count(site_url: str) -> int:
    with urllib.request.urlopen(site_url + "/api/coding/catalog.json") as r:
        return len(json.load(r)["policies"])


def test_row_count_matches_catalog(page, site_url) -> None:
    page.goto(site_url + "/coding/policies/")
    total = _catalog_count(site_url)
    assert page.locator(".row[data-policy-id]").count() == total
    screenshot(page, "policies-desktop")


def test_label_chip_filters(page, site_url) -> None:
    page.goto(site_url + "/coding/policies/")
    page.locator('.chip[data-facet="label"][data-value="block"]').click()
    visible = page.locator(VISIBLE)
    assert visible.count() > 0
    for i in range(visible.count()):
        assert visible.nth(i).get_attribute("data-label") == "block"
    assert "Showing" in page.locator("#policies-status").inner_text()


def test_search_finds_block_no_verify(page, site_url) -> None:
    page.goto(site_url + "/coding/policies/")
    # Descriptions arrive via fetch('/data/site.json') on first input; wait for it.
    with page.expect_response("**/data/site.json"):
        page.locator("#policy-search").fill("no-verify")
    page.wait_for_timeout(150)  # let the post-fetch apply() run
    ids = page.evaluate(
        "[...document.querySelectorAll('.row[data-policy-id]:not(.hidden)')]"
        ".map(r => r.dataset.policyId)"
    )
    assert "block-no-verify" in ids


def test_rows_render_without_javascript(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(site_url + "/coding/policies/")
        assert page.locator(".row[data-policy-id]").count() == _catalog_count(site_url)
        assert page.locator(".row.hidden").count() == 0
    finally:
        context.close()
