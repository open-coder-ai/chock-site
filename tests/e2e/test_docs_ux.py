"""SITE-UX: path tabs, copy buttons, the "On this page" list and callouts, in a browser."""

from conftest import assert_clean, collect

MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1366, "height": 900}


def _state(page) -> list[dict]:
    return page.eval_on_selector_all(
        ".docs-tabs [role=tab]",
        """tabs => tabs.map(t => ({
            name: t.textContent,
            selected: t.getAttribute('aria-selected'),
            tabindex: t.tabIndex,
            panelShown: !document.getElementById(t.getAttribute('aria-controls')).hidden,
        }))""",
    )


def test_path_tabs_follow_the_aria_tabs_pattern(page, site_url) -> None:
    page.goto(site_url + "/docs/")
    tablist = page.locator(".docs-tabs [role=tablist]")
    assert tablist.get_attribute("aria-label") == "Two paths"
    state = _state(page)
    assert [t["name"] for t in state] == ["Plugin path", "Repo path"]
    assert [t["selected"] for t in state] == ["true", "false"]
    assert [t["tabindex"] for t in state] == [0, -1]
    assert [t["panelShown"] for t in state] == [True, False]
    for panel in page.locator(".docs-tab-panel").all():
        assert panel.get_attribute("role") == "tabpanel"
        tab = page.locator(f"#{panel.get_attribute('aria-labelledby')}")
        assert tab.get_attribute("aria-controls") == panel.get_attribute("id")
        assert panel.locator(".docs-tab-heading").is_hidden()

    page.locator("[role=tab]").first.focus()
    page.keyboard.press("ArrowRight")
    assert [t["selected"] for t in _state(page)] == ["false", "true"]
    assert page.evaluate("document.activeElement.textContent") == "Repo path"
    assert (
        page.locator(".docs-tab-panel").nth(1).inner_text().count("chock init .") == 1
    )
    page.keyboard.press("ArrowRight")
    assert [t["selected"] for t in _state(page)] == ["true", "false"]
    page.keyboard.press("End")
    assert [t["panelShown"] for t in _state(page)] == [False, True]
    page.keyboard.press("Home")
    assert [t["panelShown"] for t in _state(page)] == [True, False]
    page.keyboard.press("ArrowLeft")
    assert [t["tabindex"] for t in _state(page)] == [-1, 0]
    # Tab leaves the tab list for the open panel.
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "docs-tab-panel"
    page.locator("[role=tab]").first.click()
    assert [t["selected"] for t in _state(page)] == ["true", "false"]
    assert_clean(page)


def test_without_js_the_paths_stack_and_the_toc_is_open(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False, viewport=MOBILE)
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + "/docs/")
        assert page.locator("[role=tablist]").count() == 0
        assert page.locator(".code-copy").count() == 0
        headings = page.locator(".docs-tab-heading")
        assert [h.inner_text() for h in headings.all()] == ["Plugin path", "Repo path"]
        for panel in page.locator(".docs-tab-panel").all():
            assert panel.is_visible()
        assert page.locator(".docs-toc details").get_attribute("open") is not None
        assert page.locator(".docs-toc a").first.is_visible()
        assert_clean(page)
    finally:
        context.close()


def test_every_code_block_has_a_copy_button_that_copies_it(browser, site_url) -> None:
    context = browser.new_context(viewport=DESKTOP)
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + "/docs/quickstart/repo/")
        blocks = page.locator(".docs-main pre")
        assert blocks.count() > 3
        assert page.locator(
            ".docs-main .code-block > pre + button.code-copy"
        ).count() == (blocks.count())
        block = page.locator(".code-block").nth(1)
        expected = block.locator("pre").text_content()
        button = block.locator("button")
        assert button.inner_text() == "Copy"
        button.click()
        assert page.evaluate("navigator.clipboard.readText()") == expected
        assert button.inner_text() == "Copied"
        assert page.locator("#live").inner_text() == "Copied"
        assert_clean(page)
    finally:
        context.close()


def test_copy_button_never_sends_an_event(page, site_url) -> None:
    sent: list[str] = []
    page.on("request", lambda req: sent.append(req.url) if "/api/" in req.url else None)
    page.goto(site_url + "/docs/?track=1")
    page.locator(".code-copy").first.click()
    page.wait_for_timeout(200)
    assert sent == []
    assert_clean(page)


def test_toc_is_a_column_on_desktop_and_closed_on_a_phone(browser, site_url) -> None:
    for viewport, side in ((DESKTOP, True), (MOBILE, False)):
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            collect(page, site_url)
            page.goto(site_url + "/docs/policies/block-curl-pipe-sh/")
            toc = page.locator(".docs-toc")
            main = page.locator(".docs-main").bounding_box()
            box = toc.bounding_box()
            if side:
                assert box["x"] >= main["x"] + main["width"]
                assert page.locator(".docs-toc details").get_attribute("open") == ""
            else:
                assert box["y"] + box["height"] <= main["y"]
                assert page.locator(".docs-toc details").get_attribute("open") is None
                page.locator(".docs-toc summary").click()
                assert page.locator(".docs-toc a").first.is_visible()
            wide = page.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth"
            )
            assert wide <= 0, f"{viewport}: {wide}px wider than the viewport"
            assert_clean(page)
        finally:
            context.close()


def test_toc_marks_the_section_scrolled_to(browser, site_url) -> None:
    context = browser.new_context(viewport=DESKTOP)
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + "/docs/")
        current = page.locator('.docs-toc a[aria-current="true"]')
        assert current.count() == 1
        last = page.locator(".docs-toc a").last
        last.click()
        page.wait_for_function(
            "() => [...document.querySelectorAll('.docs-toc a')].at(-1)"
            ".hasAttribute('aria-current')"
        )
        assert current.count() == 1
        assert_clean(page)
    finally:
        context.close()
