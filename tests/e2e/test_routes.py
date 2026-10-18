"""S-ALL: the install page's "Every agent" table, and a real untested agent in the builder."""

import json

import pytest
from conftest import SCREENSHOTS, assert_clean

from sitegen.render import sentence_start

INSTALL = "/coding/install/"
ISSUES = "https://github.com/open-coder-ai/agentseam/issues/"


def _routes(page, site_url: str) -> list[dict]:
    site = json.loads(page.request.get(site_url + "/data/site.json").text())
    return site["agent_routes"]["agents"]


def test_every_agent_has_a_row_with_its_routes(page, site_url) -> None:
    rows = _routes(page, site_url)
    assert len(rows) == 27
    page.goto(site_url + INSTALL)
    table = page.locator("table.routes")
    assert table.locator("tbody tr").count() == len(rows)
    for row in rows:
        tr = table.locator(f"#route-{row['agent']}")
        assert tr.get_attribute("data-route") == row["route"]
        assert row["name"] in tr.locator("th").inner_text()
        assert row["route_text"] in tr.inner_text()
        cells = tr.locator("td")
        if row["plugin"]:
            link = cells.nth(0).locator("a")
            assert link.get_attribute("href") == f"#agent-{row['plugin']['client']}"
            assert row["plugin"]["word"] in cells.nth(0).inner_text()
        if row["sync"]:
            assert row["sync"]["command"] in cells.nth(1).inner_text()
            assert row["sync"]["word"] in cells.nth(1).inner_text()
        else:
            assert row["reason"] in cells.nth(1).inner_text()
        assert sentence_start(row["record"]) in cells.nth(2).inner_text()
        evidence = cells.nth(2).locator("a.route-evidence")
        if row["evidence"]:
            assert evidence.get_attribute("href") == row["evidence"]["url"]
            assert evidence.get_attribute("href").startswith(ISSUES)
        else:
            assert evidence.count() == 0
    assert_clean(page)


def test_a_plugin_link_opens_that_agents_section(page, site_url) -> None:
    page.goto(site_url + INSTALL)
    page.locator("#route-goose a[href='#agent-goose']").click()
    assert page.evaluate("location.hash") == "#agent-goose"
    section = page.locator("section[aria-labelledby='agent-goose']")
    assert section.is_visible()
    assert section.locator(".client-evidence a").get_attribute("href") == (
        f"{ISSUES}177"
    )
    removal = section.locator(".remove-unverified")
    assert "Removal steps not verified for goose yet." in removal.inner_text()
    assert removal.locator("a").get_attribute("href") == f"{ISSUES}177"
    assert_clean(page)


def test_the_builder_links_to_every_agent(page, site_url) -> None:
    page.goto(site_url + "/coding/builder/#preset=git-hygiene")
    page.locator("a[href='/coding/install/#every-agent']").click()
    page.wait_for_url("**/coding/install/#every-agent")
    assert page.locator("#every-agent").is_visible()
    assert_clean(page)


def test_a_real_untested_agent_gets_its_line_notice_and_no_apply(
    page, site_url
) -> None:
    page.goto(site_url + "/coding/builder/#preset=git-hygiene")
    page.wait_for_selector(".sel-item")
    assert page.locator("#client-mistral-vibe").count() == 0  # sync only, no plugin
    page.locator("#client-goose").check()
    command = page.locator("[data-selection-code]").inner_text()
    assert command.endswith(" --client goose")
    notice = page.locator(".client-evidence[data-client='goose']")
    assert notice.is_visible()
    assert notice.locator("a").get_attribute("href") == f"{ISSUES}177"
    assert page.locator(".client-untested[data-client='goose']").is_visible()
    assert_clean(page)


@pytest.mark.parametrize("width", (390, 1280))
def test_the_table_never_scrolls_the_page(browser, site_url, width) -> None:
    context = browser.new_context(viewport={"width": width, "height": 900})
    try:
        page = context.new_page()
        page.goto(site_url + INSTALL + "#every-agent")
        scroll, inner = page.evaluate(
            "[document.scrollingElement.scrollWidth, window.innerWidth]"
        )
        assert scroll <= inner, (width, scroll, inner)
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        page.locator("#every-agent").screenshot(
            path=str(SCREENSHOTS / f"every_agent_{width}.png")
        )
    finally:
        context.close()
