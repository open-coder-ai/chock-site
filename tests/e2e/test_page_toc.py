"""SITE-TOC: the FAQ's "On this page" column at 1,920, 1,280 and 390 px."""

import pytest
from conftest import assert_clean, collect

WIDE = ({"width": 1920, "height": 1080}, {"width": 1280, "height": 800})
PHONE = {"width": 390, "height": 844}


def _open(browser, site_url, viewport):
    context = browser.new_context(viewport=viewport)
    page = context.new_page()
    collect(page, site_url)
    page.goto(site_url + "/faq/")
    return context, page


def _overflow(page) -> int:
    return page.evaluate(
        "() => document.documentElement.scrollWidth - window.innerWidth"
    )


def _header_bottom(page) -> float:
    return page.evaluate(
        "() => document.querySelector('header').getBoundingClientRect().bottom"
    )


def _settle(page) -> None:
    """Wait until a smooth scroll has stopped: scrollY unchanged over five frames."""
    page.wait_for_function(
        """() => new Promise(done => {
            let last = -1, same = 0;
            const tick = () => {
                same = window.scrollY === last ? same + 1 : 0;
                last = window.scrollY;
                if (same >= 5) done(true); else requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
        })"""
    )


@pytest.mark.parametrize("viewport", WIDE, ids=lambda v: str(v["width"]))
def test_toc_is_a_sticky_column_beside_the_text(browser, site_url, viewport) -> None:
    context, page = _open(browser, site_url, viewport)
    try:
        toc = page.locator(".docs-toc")
        assert toc.is_visible()
        main = page.locator(".toc-main").bounding_box()
        box = toc.bounding_box()
        assert box["x"] >= main["x"] + main["width"]
        answer = page.locator(".faq-item p").first.bounding_box()
        assert answer["width"] <= 720
        assert _overflow(page) <= 0
        # Halfway down, before the footer: the list stays parked under the header.
        page.evaluate("() => window.scrollTo(0, 600)")
        _settle(page)
        box = toc.bounding_box()
        assert page.evaluate("() => window.scrollY") == 600
        assert abs(box["y"] - _header_bottom(page)) <= 1, box
        assert box["y"] + box["height"] <= viewport["height"]
        assert page.locator(".docs-toc a").last.is_visible()
        assert_clean(page)
    finally:
        context.close()


@pytest.mark.parametrize("viewport", WIDE, ids=lambda v: str(v["width"]))
def test_every_toc_link_lands_on_its_heading(browser, site_url, viewport) -> None:
    context, page = _open(browser, site_url, viewport)
    try:
        links = page.locator(".docs-toc a")
        hrefs = links.evaluate_all("as => as.map(a => a.getAttribute('href'))")
        assert len(hrefs) >= 3
        for i, href in enumerate(hrefs):
            page.evaluate("() => window.scrollTo(0, 0)")
            links.nth(i).click()
            page.wait_for_function(f"() => location.hash === {href!r}")
            _settle(page)
            top = page.evaluate(
                "id => document.getElementById(id).getBoundingClientRect().top",
                href[1:],
            )
            assert _header_bottom(page) <= top < viewport["height"] - 40, (href, top)
        assert _overflow(page) <= 0
        assert_clean(page)
    finally:
        context.close()


def test_toc_is_hidden_on_a_phone(browser, site_url) -> None:
    context, page = _open(browser, site_url, PHONE)
    try:
        assert page.locator(".docs-toc").count() == 1
        assert not page.locator(".docs-toc").is_visible()
        assert page.locator(".faq-item h3").first.is_visible()
        assert _overflow(page) <= 0
        assert_clean(page)
    finally:
        context.close()


@pytest.mark.parametrize("viewport", (*WIDE, PHONE), ids=lambda v: str(v["width"]))
def test_focus_reads_the_answers_then_the_toc_then_the_footer(
    browser, site_url, viewport
) -> None:
    context, page = _open(browser, site_url, viewport)
    try:
        page.locator(".toc-main a").last.focus()
        page.keyboard.press("Tab")
        focused = page.evaluate(
            "() => [document.activeElement.className, document.activeElement.textContent,"
            " !!document.activeElement.closest('.docs-toc'),"
            " !!document.activeElement.closest('footer')]"
        )
        if viewport is PHONE:
            assert focused[3], focused
        else:
            assert focused[2] and "docs-toc-title" in focused[0], focused
            page.keyboard.press("Tab")
            first = page.locator(".docs-toc a").first
            assert first.evaluate("a => a === document.activeElement")
            for _ in range(page.locator(".docs-toc a").count()):
                page.keyboard.press("Tab")
            assert page.evaluate("() => !!document.activeElement.closest('footer')")
        assert_clean(page)
    finally:
        context.close()
