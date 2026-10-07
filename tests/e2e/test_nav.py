"""Header, section nav and footer links all resolve; section nav marks current."""

from conftest import assert_clean

PAGES_TO_SWEEP = [
    "/",
    "/coding/",
    "/general/",
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
        ("Agents", "/coding/clients/"),
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


def test_mobile_hides_only_the_top_nav(browser, site_url) -> None:
    """390px: section nav, breadcrumb and footer links stay visible."""
    context = browser.new_context(viewport={"width": 390, "height": 844})
    try:
        page = context.new_page()
        page.goto(site_url + "/coding/policies/block-no-verify/")
        for sel in (".section-nav", ".breadcrumb", ".footer-links"):
            loc = page.locator(sel)
            assert loc.count(), sel
            assert loc.first.is_visible(), sel
        nav = page.locator("#nav-links")
        toggle = page.locator(".nav-toggle")
        assert not nav.is_visible()
        assert toggle.is_visible()
        toggle.click()
        assert nav.is_visible()
        assert page.locator(".section-nav").first.is_visible()
        toggle.click()
        assert not nav.is_visible()
    finally:
        context.close()


def test_section_nav_band_aligns_with_header(browser, site_url) -> None:
    """1280px: the section-nav band is full width; its inner aligns with the header."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    try:
        page = context.new_page()
        page.goto(site_url + "/coding/policies/")
        band = page.locator(".section-nav").bounding_box()
        assert band["x"] == 0 and band["width"] == 1280
        inner_x = page.locator(".section-nav-inner").bounding_box()["x"]
        header_x = page.locator(".header-inner").bounding_box()["x"]
        assert inner_x == header_x
        label = page.locator(".section-nav-title")
        assert label.inner_text().lower() == "coding agents"
        assert (
            page.evaluate(
                "getComputedStyle(document.querySelector('.section-nav-title'))"
                ".textTransform"
            )
            == "uppercase"
        )
        assert page.locator(".section-nav a[aria-current='page']").count() == 1
    finally:
        context.close()


def test_section_nav_shows_all_links_at_390(browser, site_url) -> None:
    """390px: all six section-nav links are fully on screen and the nav does not scroll."""
    context = browser.new_context(viewport={"width": 390, "height": 844})
    try:
        page = context.new_page()
        page.goto(site_url + "/coding/policies/")
        links = page.locator(".section-nav a")
        assert links.count() == 6
        for label in (
            "Overview",
            "Policies",
            "Builder",
            "Author",
            "Install",
            "Agents",
        ):
            link = page.locator(".section-nav a", has_text=label)
            assert link.is_visible(), label
            box = link.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= 390, (label, box)
        inner = page.locator(".section-nav-inner").evaluate(
            "el => [el.scrollWidth, el.clientWidth]"
        )
        assert inner[0] <= inner[1], inner
    finally:
        context.close()
