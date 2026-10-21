"""SITE-SEARCH: the docs search box as a WAI-ARIA combobox, in a browser."""

import json
import re

from conftest import assert_clean, collect
from playwright.sync_api import expect
from test_a11y import _CONTRAST

MOBILE = {"width": 390, "height": 844}
INDEX = "/api/docs/search.json"
INPUT = "#docs-search-input"


def _options(page) -> list[dict]:
    return page.eval_on_selector_all(
        "#docs-search-list [role=option]",
        """os => os.map(o => ({
            id: o.id,
            selected: o.getAttribute('aria-selected'),
            title: o.querySelector('.docs-search-title').textContent,
        }))""",
    )


def _type(page, query: str) -> None:
    page.locator(INPUT).fill(query)


def test_box_replaces_the_fallback_link_with_js(page, site_url) -> None:
    page.goto(site_url + "/docs/configure/")
    assert page.locator(".docs-search-fallback").is_hidden()
    box = page.locator(INPUT)
    assert box.is_visible()
    assert box.get_attribute("role") == "combobox"
    assert box.get_attribute("aria-expanded") == "false"
    assert page.locator("label[for=docs-search-input]").text_content() == (
        "Search the docs"
    )
    assert page.locator("#docs-search-list").is_hidden()
    assert_clean(page)


def test_index_is_fetched_once_on_first_use_from_this_site(page, site_url) -> None:
    fetched: list[str] = []
    page.on("request", lambda r: fetched.append(r.url) if "/api/" in r.url else None)
    page.goto(site_url + "/docs/")
    page.wait_for_load_state("networkidle")
    assert fetched == []
    page.locator(INPUT).focus()
    _type(page, "codex")
    page.wait_for_selector("#docs-search-list [role=option]")
    _type(page, "secret")
    page.wait_for_selector("#docs-search-list [role=option]")
    assert fetched == [site_url + INDEX]
    assert_clean(page)


def test_arrow_keys_escape_and_enter_follow_combobox(page, site_url) -> None:
    page.goto(site_url + "/docs/monitor/")
    box = page.locator(INPUT)
    box.focus()
    _type(page, "secret")
    page.wait_for_selector("#docs-search-list [role=option]")
    options = _options(page)
    assert 1 < len(options) <= 8
    assert box.get_attribute("aria-expanded") == "true"
    assert box.get_attribute("aria-activedescendant") is None
    assert all(o["selected"] == "false" for o in options)

    page.keyboard.press("ArrowDown")
    assert box.get_attribute("aria-activedescendant") == options[0]["id"]
    assert _options(page)[0]["selected"] == "true"
    page.keyboard.press("ArrowUp")
    assert box.get_attribute("aria-activedescendant") == options[-1]["id"]
    page.keyboard.press("ArrowDown")
    assert box.get_attribute("aria-activedescendant") == options[0]["id"]
    assert page.evaluate("document.activeElement.id") == "docs-search-input"

    page.keyboard.press("Escape")
    assert box.get_attribute("aria-expanded") == "false"
    assert page.locator("#docs-search-list").is_hidden()
    assert box.input_value() == "secret"
    page.keyboard.press("Escape")
    assert box.input_value() == ""

    _type(page, "secret")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    second = _options(page)[1]["title"]
    with page.expect_navigation():
        page.keyboard.press("Enter")
    assert page.locator("h1").inner_text() == second
    assert_clean(page)


def test_heading_match_opens_the_page_at_that_heading(page, site_url) -> None:
    page.goto(site_url + "/docs/")
    _type(page, "ssl certificate")
    page.wait_for_selector("#docs-search-list [role=option]")
    where = page.locator("#docs-search-list [role=option] .docs-search-where").first
    heading = where.inner_text()
    with page.expect_navigation():
        page.locator("#docs-search-list [role=option]").first.click()
    assert page.url.startswith(site_url + "/docs/troubleshooting/#")
    target = page.url.split("#", 1)[1]
    assert page.locator(f"[id='{target}']").inner_text() == heading
    assert_clean(page)


def test_results_and_no_results_are_announced(page, site_url) -> None:
    page.goto(site_url + "/docs/")
    _type(page, "allowlist")
    page.wait_for_selector("#docs-search-list [role=option]")
    count = len(_options(page))
    expect(page.locator("#docs-search-status")).to_have_text(
        f"{count} results. Use the arrow keys to choose, Enter to open."
    )
    _type(page, "zzqx <b>$&")
    expect(page.locator("#docs-search-status")).to_have_text(
        "No docs page matches zzqx <b>$&."
    )
    assert page.locator("#docs-search-list").is_hidden()
    assert page.locator(INPUT).get_attribute("aria-expanded") == "false"
    assert page.locator("#docs-search-list b").count() == 0
    assert_clean(page)


def test_focus_leaving_the_box_closes_the_list(page, site_url) -> None:
    page.goto(site_url + "/docs/")
    _type(page, "codex")
    page.wait_for_selector("#docs-search-list [role=option]")
    page.keyboard.press("Tab")
    assert page.locator("#docs-search-list").is_hidden()
    assert page.locator(INPUT).get_attribute("aria-expanded") == "false"
    assert_clean(page)


def test_every_result_link_resolves(page, site_url) -> None:
    index = json.loads(page.request.get(site_url + INDEX).text())
    for row in index["pages"]:
        assert page.request.get(site_url + row["url"]).ok, row["url"]
    assert_clean(page)


def test_without_js_the_fallback_links_to_the_docs_index(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False, viewport=MOBILE)
    page = context.new_page()
    collect(page, site_url)
    try:
        page.goto(site_url + "/docs/configure/")
        link = page.locator(".docs-search-fallback a")
        assert link.is_visible()
        assert link.get_attribute("href") == "/docs/"
        assert page.locator(".docs-search-box").is_hidden()
        assert_clean(page)
    finally:
        context.close()


def test_results_fit_and_pass_contrast_on_mobile(browser, site_url) -> None:
    context = browser.new_context(viewport=MOBILE)
    page = context.new_page()
    collect(page, site_url)
    try:
        page.goto(site_url + "/docs/policies/")
        _type(page, "secret")
        page.wait_for_selector("#docs-search-list [role=option]")
        page.keyboard.press("ArrowDown")
        width = page.evaluate("document.documentElement.scrollWidth")
        assert width <= MOBILE["width"]
        box = page.locator("#docs-search-list").bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= MOBILE["width"]
        rows = page.evaluate(
            _CONTRAST,
            ".docs-search-title, .docs-search-where, .docs-search-excerpt",
        )
        assert rows
        low = [r for r in rows if r["ratio"] < 4.5]
        assert not low, low
        assert_clean(page)
    finally:
        context.close()


def test_placeholder_passes_contrast(page, site_url) -> None:
    page.goto(site_url + "/docs/")
    colours = page.evaluate(
        """() => {
            const box = document.getElementById('docs-search-input');
            return [getComputedStyle(box, '::placeholder').color,
                    getComputedStyle(box).backgroundColor];
        }"""
    )
    lum = []
    for colour in colours:
        r, g, b = (int(v) / 255 for v in re.findall(r"\d+", colour)[:3])
        lin = [
            v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
            for v in (r, g, b)
        ]
        lum.append(0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2])
    ratio = (max(lum) + 0.05) / (min(lum) + 0.05)
    assert ratio >= 4.5, colours
    assert_clean(page)
