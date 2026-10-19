"""The General agents section: the fixed 'design in progress' page."""

import re

from conftest import assert_clean

BANNED = ("deny", "step_up", "modify", "profile", "approval", "specification")


def test_general_page_is_the_fixed_copy(page, site_url, request) -> None:
    response = page.goto(site_url + "/general/")
    assert response.status == 200
    main = page.locator("main")
    text = main.inner_text()
    for line in (
        "General agents",
        "DESIGN IN PROGRESS",
        (
            "Guardrails for agents that act for a person or a business. "
            "We are still designing them."
        ),
        "There is nothing to install yet.",
        "Follow open-coder-ai on GitHub",
    ):
        assert line in text, line
    for word in BANNED:
        assert not re.search(rf"\b{word}\b", text.lower()), word
    assert page.locator("h1").inner_text() == "General agents"
    link = page.locator('main a[href="https://github.com/open-coder-ai"]')
    assert link.count() == 1
    assert_clean(page)


def test_general_badges_and_section_nav(page, site_url) -> None:
    page.goto(site_url + "/general/")
    badge = page.locator('#nav-links a[href="/general/"] .badge')
    assert badge.inner_text() == "DESIGN IN PROGRESS"
    # The badge lives in the header; footer links stay plain text.
    assert page.locator('.footer-links a[href="/general/"]').count() == 1
    assert page.locator('.footer-links a[href="/general/"] .badge').count() == 0
    nav = page.locator('nav[aria-label="General agents"]')
    assert nav.count() == 1
    links = nav.locator("a")
    assert links.count() == 1
    assert links.first.inner_text() == "Overview"
    assert links.first.get_attribute("aria-current") == "page"
    assert_clean(page)


def test_general_has_no_api_dir(site_url) -> None:
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(site_url + "/api/general/")
        raise AssertionError("/api/general/ should not exist")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404


def test_general_page_has_no_external_requests(browser, site_url) -> None:
    """The page and every asset it loads come from the site itself."""
    requests = []
    context = browser.new_context()
    try:
        page = context.new_page()
        page.on("request", lambda req: requests.append(req.url))
        page.goto(site_url + "/general/")
        page.wait_for_load_state("networkidle")
        for url in requests:
            assert url.startswith(site_url), url
    finally:
        context.close()
