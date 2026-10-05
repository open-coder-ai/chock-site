"""Mobile: at 390x844 nothing in the sitemap scrolls horizontally."""

import re

from conftest import screenshot

MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 800}


def _paths(page, site_url: str) -> list[str]:
    response = page.goto(site_url + "/sitemap.xml")
    xml = response.body().decode("utf-8")
    return [
        loc[len("https://chock.sh") :] for loc in re.findall(r"<loc>([^<]+)</loc>", xml)
    ]


def _wide_elements(page) -> list[str]:
    return page.evaluate(
        """() => {
            const w = window.innerWidth;
            const out = [];
            document.querySelectorAll('body *').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.right > w + 0.5 || r.left < -0.5) {
                    const cls = (el.className && el.className.baseVal === undefined)
                        ? '.' + String(el.className).trim().split(/\\s+/).join('.')
                        : '';
                    out.push(el.tagName.toLowerCase() + cls
                        + ' [' + r.left.toFixed(0) + ',' + r.right.toFixed(0) + ']'
                        + ' ' + (el.textContent || '').trim().slice(0, 40));
                }
            });
            return out.slice(0, 8);
        }"""
    )


def test_no_horizontal_scroll_at_mobile_width(browser, site_url) -> None:
    context = browser.new_context(viewport=MOBILE)
    try:
        page = context.new_page()
        for path in _paths(page, site_url):
            page.goto(site_url + path)
            overflow = page.evaluate(
                "document.scrollingElement.scrollWidth > window.innerWidth"
            )
            assert not overflow, (
                f"{path}: horizontal scroll at 390px: {_wide_elements(page)}"
            )
    finally:
        context.close()


def test_screenshots_for_the_pr(browser, site_url) -> None:
    """The PR body needs home, policies, a policy page and clients, both sizes."""
    shots = {
        "home": "/",
        "policies": "/coding/policies/",
        "block-no-verify": "/coding/policies/block-no-verify/",
        "clients": "/coding/clients/",
    }
    for size_name, viewport in (("desktop", DESKTOP), ("mobile", MOBILE)):
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            for name, path in shots.items():
                page.goto(site_url + path)
                screenshot(page, f"{name}-{size_name}")
        finally:
            context.close()
