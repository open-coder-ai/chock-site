"""A policy page: label word, examples, sha256 copy, add-to-builder."""

from conftest import assert_clean, screenshot
from playwright.sync_api import expect

PAGE = "/coding/policies/block-no-verify/"


def test_policy_page_content(page, site_url, request) -> None:
    page.goto(site_url + PAGE)
    assert "blocks" in page.locator(".label").first.inner_text()
    assert "git commit --no-verify -m wip" in page.content()
    assert "08c7d6e422b0" in page.content()  # sha256 prefix
    assert page.locator("#misses").count() == 1
    add = page.locator("a", has_text="Add to my plugin")
    assert add.get_attribute("href") == "/coding/builder/#add=block-no-verify"
    assert_clean(page)
    screenshot(page, request.node.name)


def test_policy_page_print_keeps_title_and_label(page, site_url) -> None:
    page.goto(site_url + PAGE)
    page.emulate_media(media="print")
    expect(page.locator("#policy-name")).to_be_visible()
    expect(page.locator("#label")).to_be_visible()
    expect(page.locator("body > header")).to_be_hidden()
    expect(page.locator("footer")).to_be_hidden()
    expect(page.locator(".side-buttons")).to_be_hidden()
    expect(page.locator(".breadcrumb")).to_be_hidden()
    assert_clean(page)


def test_copy_button_shows_copied(browser, site_url) -> None:
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    try:
        page = context.new_page()
        page.goto(site_url + PAGE)
        button = page.locator("button.copy").first
        button.click()
        expect(button).to_have_text("Copied")
        assert "Copied" in page.locator("#live").inner_text()
    finally:
        context.close()
