"""Smoke test: the home page loads, and every sitemap URL renders one h1."""

import re

from conftest import assert_clean, screenshot


def test_home_page_loads(page, site_url, request) -> None:
    response = page.goto(site_url + "/")
    assert response.status == 200
    assert "chock.sh" in page.title()
    assert_clean(page)
    screenshot(page, request.node.name)


def _sitemap_urls(page, site_url: str) -> list[str]:
    """Fetch sitemap.xml in the browser and return the local URL paths."""
    response = page.goto(site_url + "/sitemap.xml")
    assert response.status == 200
    xml = response.body().decode("utf-8")
    return [
        loc[len("https://chock.sh") :] for loc in re.findall(r"<loc>([^<]+)</loc>", xml)
    ]


def test_every_sitemap_url_loads(page, site_url) -> None:
    paths = _sitemap_urls(page, site_url)
    assert len(paths) >= 70, "sitemap is missing pages"
    for path in paths:
        response = page.goto(site_url + path)
        assert response.status == 200, path
        assert page.locator("h1").count() == 1, f"{path}: h1 count"
    assert_clean(page)
