"""DOC-1: the docs nav reaches every topic, agent pages carry their routes, nothing overflows."""

import json

from conftest import assert_clean

MOBILE = {"width": 390, "height": 844}


def test_docs_nav_reaches_every_topic_and_marks_it(page, site_url) -> None:
    page.goto(site_url + "/docs/")
    hrefs = page.eval_on_selector_all(
        ".docs-nav a", "els => els.map(e => e.getAttribute('href'))"
    )
    assert hrefs[0] == "/docs/" and len(hrefs) == len(set(hrefs))
    for href in hrefs:
        page.goto(site_url + href)
        current = page.locator('.docs-nav a[aria-current="page"]')
        assert current.count() == 1 and current.get_attribute("href") == href
        assert page.locator("h1").count() == 1
    assert_clean(page)


def test_header_docs_link_opens_the_overview(page, site_url) -> None:
    page.goto(site_url + "/")
    page.click('#nav-links a[href="/docs/"]')
    page.wait_for_url(site_url + "/docs/")
    assert page.locator('#nav-links a[aria-current="page"]').inner_text() == "Docs"
    assert_clean(page)


def test_every_agent_page_shows_its_routes(page, site_url) -> None:
    api = json.loads(page.request.get(site_url + "/api/docs/index.json").text())
    for agent in api["agents"]:
        page.goto(site_url + f"/docs/agents/{agent['slug']}/")
        text = page.locator("main").inner_text()
        for client in agent["plugin_clients"]:
            assert f"--client {client}" in text, agent["id"]
        if agent["sync_name"]:
            assert f"--agents {agent['sync_name']}" in text, agent["id"]
        assert agent["grade"] in text, agent["id"]
    assert_clean(page)


def test_docs_pages_fit_a_phone(browser, site_url) -> None:
    context = browser.new_context(viewport=MOBILE)
    try:
        page = context.new_page()
        for path in (
            "/docs/",
            "/docs/quickstart/plugin/",
            "/docs/agents/cursor/",
            "/docs/cli/",
        ):
            page.goto(site_url + path)
            wide = page.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth"
            )
            assert wide <= 0, f"{path}: {wide}px wider than the viewport"
    finally:
        context.close()
