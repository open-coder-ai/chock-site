"""Header, section nav and footer links all resolve; section nav marks current."""

from conftest import assert_clean

PAGES_TO_SWEEP = [
    "/",
    "/coding/",
    "/coding/policies/",
    "/coding/policies/block-no-verify/",
    "/coding/builder/",
    "/coding/install/",
    "/coding/clients/",
    "/faq/",
    "/security/",
    "/for-agents/",
]


def _local_links(page, site_url: str) -> list[str]:
    """Header, section-nav and footer links, as root-relative paths."""
    return page.evaluate(
        """() => {
            const links = new Set();
            for (const sel of ["#nav-links a", ".section-nav a", ".footer-links a"]) {
                for (const a of document.querySelectorAll(sel)) {
                    const href = a.getAttribute("href");
                    if (href && href.startsWith("/")) links.add(href.split("#")[0]);
                }
            }
            return [...links];
        }"""
    )


def test_nav_and_footer_links_resolve(page, site_url) -> None:
    found = set()
    for path in PAGES_TO_SWEEP:
        page.goto(site_url + path)
        found.update(_local_links(page, site_url))
    for href in sorted(found):
        response = page.goto(site_url + href)
        assert response.status == 200, href
        if "text/html" in response.headers.get("content-type", ""):
            h1 = page.locator("h1").first
            assert h1.inner_text() != "Page not found", href
    assert_clean(page)


def test_section_nav_marks_current(page, site_url) -> None:
    page.goto(site_url + "/coding/policies/")
    nav = page.locator('nav[aria-label="Coding agents"]')
    assert nav.count() == 1
    current = nav.locator('[aria-current="page"]')
    assert current.inner_text() == "Policies"
    assert current.get_attribute("href") == "/coding/policies/"
    for label, href in (
        ("Overview", "/coding/"),
        ("Builder", "/coding/builder/"),
        ("Install", "/coding/install/"),
        ("Other clients", "/coding/clients/"),
    ):
        link = nav.locator("a", has_text=label)
        assert link.get_attribute("href") == href


def test_header_cta_goes_to_builder(page, site_url) -> None:
    page.goto(site_url + "/")
    cta = page.locator('header a.button[href="/coding/builder/"]')
    assert cta.count() == 1
    response = page.goto(site_url + "/coding/builder/")
    assert response.status == 200
    assert "Build your plugin" in page.locator("h1").inner_text()
