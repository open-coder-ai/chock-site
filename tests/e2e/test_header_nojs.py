"""Header at 390px: no horizontal scroll with JavaScript on or off."""

import pytest

MOBILE = {"width": 390, "height": 844}
PATHS = ("/", "/docs/", "/faq/", "/coding/")


@pytest.mark.parametrize("javascript", [True, False], ids=["js-on", "js-off"])
def test_no_horizontal_scroll_at_390(browser, site_url, javascript: bool) -> None:
    """Home, docs, FAQ and coding pages fit 390px whether or not scripts run."""
    context = browser.new_context(viewport=MOBILE, java_script_enabled=javascript)
    try:
        page = context.new_page()
        for path in PATHS:
            page.goto(site_url + path)
            widths = page.evaluate(
                "[document.scrollingElement.scrollWidth, window.innerWidth]"
            )
            assert widths[0] <= widths[1], f"{path}: scrollWidth, innerWidth = {widths}"
    finally:
        context.close()


def test_nav_links_visible_without_javascript(browser, site_url) -> None:
    """Scripts off at 390px: all site links show, no menu button, header not sticky."""
    context = browser.new_context(viewport=MOBILE, java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(site_url + "/")
        assert not page.locator(".nav-toggle").is_visible()
        position = page.evaluate(
            "getComputedStyle(document.querySelector('body > header')).position"
        )
        assert position == "static"
        links = page.locator("#nav-links a")
        assert links.count()
        for i in range(links.count()):
            assert links.nth(i).is_visible(), links.nth(i).inner_text()
    finally:
        context.close()
