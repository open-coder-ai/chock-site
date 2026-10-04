"""Smoke test: the home page loads cleanly on the local server."""

from conftest import assert_clean, screenshot


def test_home_page_loads(page, site_url, request) -> None:
    response = page.goto(site_url + "/")
    assert response.status == 200
    assert "chock.sh" in page.title()
    assert_clean(page)
    screenshot(page, request.node.name)
