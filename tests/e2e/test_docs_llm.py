"""SITE-LLM: the docs page actions (Copy page and its menu), with and without JS."""

from pathlib import Path
from urllib.parse import quote

import yaml
from conftest import SCREENSHOTS, assert_clean, collect

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = yaml.safe_load(
    (ROOT / "data" / "page_actions.yaml").read_text(encoding="utf-8")
)
DESKTOP = {"width": 1366, "height": 900}
MOBILE = {"width": 390, "height": 844}
PAGE = "/docs/quickstart/plugin/"
TWIN = PAGE + "index.md"
TOGGLE = ".page-actions-toggle"
MENU = ".page-actions-menu"


def _focused(page) -> str:
    return page.evaluate("document.activeElement.textContent")


def _labels() -> list[str]:
    labels = ACTIONS["labels"]
    return [labels["copy_markdown"], labels["view"]] + [
        item["label"] for item in ACTIONS["open"]
    ]


def _viewport_shot(page, name: str) -> None:
    """The visible viewport only, under test-results/screenshots/<name>.png."""
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENSHOTS / f"{name}.png"))


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
        button = page.locator(".page-actions-copy")
        assert button.inner_text() == ACTIONS["labels"]["copy"]
        assert page.locator(".page-actions-fallback").is_hidden()
        button.click()
        page.wait_for_function(
            "t => document.querySelector('.page-actions-copy').textContent === t",
            arg=ACTIONS["labels"]["copied"],
        )
        expected = page.request.get(site_url + TWIN).text()
        assert page.evaluate("navigator.clipboard.readText()") == expected
        assert page.locator("#live").inner_text() == ACTIONS["labels"]["copied"]
        assert sent == [site_url + TWIN]
        # The menu's copy item does the same and hands focus back to the arrow.
        page.evaluate("navigator.clipboard.writeText('')")
        page.locator(TOGGLE).click()
        page.locator(f"{MENU} [role=menuitem]").first.click()
        for _ in range(50):
            if page.evaluate("navigator.clipboard.readText()"):
                break
            page.wait_for_timeout(100)
        assert page.evaluate("navigator.clipboard.readText()") == expected
        assert page.locator(MENU).is_hidden()
        assert page.evaluate("document.activeElement.id") == "page-actions-button"
        assert_clean(page)
    finally:
        context.close()


def test_menu_follows_the_menu_button_pattern(browser, site_url) -> None:
    context = browser.new_context(viewport=DESKTOP)
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + PAGE)
        page.wait_for_load_state("networkidle")
        sent: list[str] = []
        page.on("request", lambda req: sent.append(req.url))
        toggle = page.locator(TOGGLE)
        menu = page.locator(MENU)
        assert toggle.get_attribute("aria-haspopup") == "menu"
        assert toggle.get_attribute("aria-expanded") == "false"
        assert menu.is_hidden()
        items = menu.locator("[role=menuitem]")
        assert [i.text_content() for i in items.all()] == _labels()

        for key in ("Enter", " ", "ArrowDown"):
            toggle.focus()
            page.keyboard.press(key)
            assert menu.is_visible(), key
            assert toggle.get_attribute("aria-expanded") == "true"
            assert _focused(page) == _labels()[0], key
            page.keyboard.press("Escape")
            assert menu.is_hidden(), key
            assert toggle.get_attribute("aria-expanded") == "false"
            assert page.evaluate("document.activeElement.id") == "page-actions-button"

        toggle.focus()
        page.keyboard.press("ArrowUp")
        assert _focused(page) == _labels()[-1]
        page.keyboard.press("ArrowDown")
        assert _focused(page) == _labels()[0]
        page.keyboard.press("ArrowDown")
        assert _focused(page) == _labels()[1]
        page.keyboard.press("End")
        assert _focused(page) == _labels()[-1]
        page.keyboard.press("Home")
        assert _focused(page) == _labels()[0]
        page.keyboard.press("ArrowUp")
        assert _focused(page) == _labels()[-1]

        page.mouse.click(5, 5)
        assert menu.is_hidden()
        assert toggle.get_attribute("aria-expanded") == "false"
        assert sent == [], "opening the menu must not make a request"
        assert_clean(page)
    finally:
        context.close()


def test_menu_links_come_from_data(page, site_url) -> None:
    page.goto(site_url + PAGE)
    prompt = ACTIONS["prompt"].replace("__TWIN__", f"https://chock.sh{TWIN}")
    links = page.locator(f"{MENU} a")
    assert links.nth(0).get_attribute("href") == TWIN
    for n, item in enumerate(ACTIONS["open"], start=1):
        link = links.nth(n)
        assert link.inner_text() == item["label"]
        assert link.get_attribute("href") == item["href"].replace(
            "__PROMPT__", quote(prompt, safe="")
        )
        assert link.get_attribute("target") == "_blank"
        assert link.get_attribute("rel") == "noopener noreferrer"
    assert links.count() == 1 + len(ACTIONS["open"])
    assert_clean(page)


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
        page.locator(".page-actions-copy").click()
        page.wait_for_function(
            "t => document.getElementById('live').textContent === t",
            arg=ACTIONS["labels"]["failed"],
        )
        assert (
            page.locator(".page-actions-copy").inner_text() == ACTIONS["labels"]["copy"]
        )
        assert_clean(page)
    finally:
        context.close()


def test_without_js_the_twin_link_stays(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False, viewport=DESKTOP)
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + PAGE)
        assert page.locator(".page-actions-split").is_hidden()
        assert page.locator(MENU).is_hidden()
        link = page.locator(".page-actions-fallback")
        assert link.is_visible()
        assert link.inner_text() == ACTIONS["labels"]["view"]
        assert link.get_attribute("href") == TWIN
        response = page.request.get(site_url + TWIN)
        assert response.ok
        assert response.text().startswith("# Quickstart: plugin path\n")
        assert page.locator("h1").count() == 1
        assert_clean(page)
    finally:
        context.close()


def test_open_menu_fits_desktop_and_phone(browser, site_url) -> None:
    for name, viewport in (("desktop", DESKTOP), ("mobile", MOBILE)):
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            collect(page, site_url)
            page.goto(site_url + PAGE)
            page.locator(TOGGLE).click()
            box = page.locator(MENU).bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"], name
            wide = page.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth"
            )
            assert wide <= 0, f"{name}: {wide}px wider than the viewport"
            page.locator(MENU).scroll_into_view_if_needed()
            _viewport_shot(page, f"page-actions-{name}")
            assert_clean(page)
        finally:
            context.close()
