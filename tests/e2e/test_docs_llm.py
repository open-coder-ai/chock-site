"""SITE-LLM: "Copy page as Markdown" in a browser, with and without JS."""

from conftest import assert_clean, collect

DESKTOP = {"width": 1366, "height": 900}
PAGE = "/docs/quickstart/plugin/"
TWIN = PAGE + "index.md"


def test_copy_page_copies_the_twin_and_fetches_nothing_else(browser, site_url) -> None:
    context = browser.new_context(viewport=DESKTOP)
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + PAGE)
        page.wait_for_load_state("networkidle")
        sent: list[str] = []
        page.on("request", lambda req: sent.append(req.url))
        button = page.locator(".docs-md button.docs-copy-page")
        assert button.inner_text() == "Copy page as Markdown"
        button.click()
        page.wait_for_function(
            "() => document.querySelector('.docs-copy-page').textContent === 'Copied'"
        )
        expected = page.request.get(site_url + TWIN).text()
        assert page.evaluate("navigator.clipboard.readText()") == expected
        assert page.locator("#live").inner_text() == "Copied"
        assert sent == [site_url + TWIN]
        assert_clean(page)
    finally:
        context.close()


def test_copy_page_says_so_when_the_clipboard_is_refused(browser, site_url) -> None:
    context = browser.new_context(viewport=DESKTOP)
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + PAGE)
        page.evaluate(
            "() => { navigator.clipboard.write = () => Promise.reject(new Error('no'));"
            " navigator.clipboard.writeText = navigator.clipboard.write; }"
        )
        page.locator(".docs-copy-page").click()
        page.wait_for_function(
            "() => document.getElementById('live').textContent.startsWith('Copy failed')"
        )
        assert page.locator(".docs-copy-page").inner_text() == "Copy page as Markdown"
        assert_clean(page)
    finally:
        context.close()


def test_without_js_the_twin_link_stays(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False, viewport=DESKTOP)
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + PAGE)
        assert page.locator(".docs-copy-page").count() == 0
        link = page.locator(".docs-md a")
        assert link.is_visible()
        assert link.inner_text() == "View as Markdown"
        assert link.get_attribute("href") == TWIN
        response = page.request.get(site_url + link.get_attribute("href"))
        assert response.ok
        assert response.text().startswith("# Quickstart: plugin path\n")
        assert page.locator("h1").count() == 1
        assert_clean(page)
    finally:
        context.close()
