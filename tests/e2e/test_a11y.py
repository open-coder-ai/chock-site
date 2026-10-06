"""Accessibility smoke (plan 9.0, PR 4): tab order, alt, headings, labels, lang."""

import itertools
import re

from conftest import assert_clean, collect

MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 800}

_FOCUSABLE = (
    "'.builder-grid a[href], .builder-grid button, .builder-grid input,"
    " .builder-grid select, .builder-grid textarea, .builder-grid [tabindex],"
    " #mobile-bar a[href], #mobile-bar button'"
)

# A radio group is one tab stop (arrow keys move inside it), so it counts once, by name.
_DESCRIBE = """
    e => (e.type === 'radio' ? 'radio-group:' + e.name : '')
      || e.id || e.getAttribute('href') || e.value
      || (e.textContent || '').trim().slice(0, 40)
"""


def _paths(page, site_url: str) -> list[str]:
    """Every sitemap URL plus the 404 page (not in the sitemap)."""
    response = page.goto(site_url + "/sitemap.xml")
    xml = response.body().decode("utf-8")
    paths = [
        loc[len("https://chock.sh") :] for loc in re.findall(r"<loc>([^<]+)</loc>", xml)
    ]
    return paths + ["/404.html"]


def _heading_levels(page) -> list[int]:
    return page.evaluate(
        """() => [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
            .map(e => Number(e.tagName.slice(1)))"""
    )


def _controls(page) -> list[str]:
    """Keys for every visible, enabled builder control that can take focus."""
    return page.evaluate(
        f"""() => [...document.querySelectorAll({_FOCUSABLE})]
            .filter(e => !e.disabled && e.tabIndex >= 0 && e.getClientRects().length > 0)
            .map({_DESCRIBE})"""
    )


def _tabbed_keys(page, limit: int) -> set[str]:
    """The focused element after each Tab, until focus leaves the page."""
    seen: set[str] = set()
    left_page = 0
    for _ in range(limit):
        page.keyboard.press("Tab")
        key = page.evaluate(
            f"""() => document.activeElement === document.body
                ? null
                : ({_DESCRIBE})(document.activeElement)"""
        )
        if key is None:
            left_page += 1
            if left_page >= 2:
                break
        else:
            seen.add(key)
    return seen


def test_every_page_has_lang_en(page, site_url) -> None:
    for path in _paths(page, site_url):
        page.goto(site_url + path)
        assert page.locator("html").get_attribute("lang") == "en", path
    assert_clean(page)


def test_headings_never_skip_a_level(page, site_url) -> None:
    for path in _paths(page, site_url):
        page.goto(site_url + path)
        levels = _heading_levels(page)
        assert levels, f"{path}: no headings"
        assert levels[0] == 1, f"{path}: first heading is h{levels[0]}"
        for earlier, level in itertools.pairwise(levels):
            assert level <= earlier + 1, f"{path}: h{earlier} then h{level}"
    assert_clean(page)


def test_every_image_has_alt(page, site_url) -> None:
    total = 0
    for path in _paths(page, site_url):
        page.goto(site_url + path)
        images = page.locator("img")
        total += images.count()
        for i in range(images.count()):
            assert images.nth(i).get_attribute("alt") is not None, f"{path}: img {i}"
    assert total == 0, f"{total} <img> elements: every one needs an alt"
    assert_clean(page)


def test_every_input_is_labelled(page, site_url) -> None:
    for path in _paths(page, site_url):
        page.goto(site_url + path)
        unlabelled = page.evaluate(
            """() => [...document.querySelectorAll('input, select, textarea')]
                .filter(e => e.type !== 'hidden' && e.getClientRects().length > 0)
                .filter(e => !(
                    (e.id && document.querySelector('label[for="' + e.id + '"]'))
                    || e.closest('label')
                    || e.getAttribute('aria-label')
                    || e.getAttribute('aria-labelledby')
                ))
                .map(e => e.outerHTML.slice(0, 80))"""
        )
        assert not unlabelled, f"{path}: {unlabelled}"
    assert_clean(page)


def _check_tab_order(page, site_url: str) -> None:
    page.goto(site_url + "/coding/builder/#preset=git-hygiene")
    page.wait_for_selector("#builder-status:not(:empty)")
    expected = set(_controls(page))
    reached = _tabbed_keys(page, len(expected) * 2 + 80)
    missing = expected - reached
    assert not missing, f"controls not reached by Tab: {sorted(missing)}"


def test_tab_order_reaches_every_builder_control(browser, site_url) -> None:
    for viewport in (DESKTOP, MOBILE):
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            collect(page, site_url)
            _check_tab_order(page, site_url)
            assert_clean(page)
        finally:
            context.close()
