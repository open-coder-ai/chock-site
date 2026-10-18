"""LIGHT-1: the theme follows the system setting, the header toggle flips it, and a reload keeps it."""

import pytest
from conftest import assert_clean, collect

DESKTOP = {"width": 1280, "height": 900}
LIGHT_BG = "rgb(251, 250, 247)"
DARK_BG = "rgb(34, 44, 68)"


def _theme(page) -> tuple[str | None, str, str | None]:
    """The data-theme on <html>, the body background and the toggle's aria-pressed."""
    return (
        page.evaluate("document.documentElement.dataset.theme || null"),
        page.evaluate("getComputedStyle(document.body).backgroundColor"),
        page.locator(".theme-toggle").get_attribute("aria-pressed"),
    )


@pytest.mark.parametrize(
    ("scheme", "expected"),
    [("light", ("light", LIGHT_BG, "false")), ("dark", ("dark", DARK_BG, "true"))],
)
def test_default_follows_the_system_scheme(page, site_url, scheme, expected) -> None:
    page.emulate_media(color_scheme=scheme)
    page.set_viewport_size(DESKTOP)
    page.goto(site_url + "/")
    assert _theme(page) == expected
    assert_clean(page)


def test_toggle_flips_the_theme_and_a_reload_keeps_it(page, site_url) -> None:
    page.emulate_media(color_scheme="light")
    page.set_viewport_size(DESKTOP)
    page.goto(site_url + "/docs/")
    toggle = page.locator(".theme-toggle")
    assert toggle.is_visible()
    assert toggle.get_attribute("aria-label") == "Dark theme"

    toggle.click()
    assert _theme(page) == ("dark", DARK_BG, "true")
    page.reload()
    assert _theme(page) == ("dark", DARK_BG, "true")

    # The stored choice beats the system setting, on this page and on the next.
    page.emulate_media(color_scheme="light")
    page.goto(site_url + "/faq/")
    assert _theme(page) == ("dark", DARK_BG, "true")

    page.locator(".theme-toggle").click()
    page.reload()
    assert _theme(page) == ("light", LIGHT_BG, "false")
    assert_clean(page)


def test_toggle_works_from_the_keyboard_with_a_visible_focus(page, site_url) -> None:
    page.emulate_media(color_scheme="light")
    page.set_viewport_size(DESKTOP)
    page.goto(site_url + "/")
    toggle = page.locator(".theme-toggle")
    page.locator(".header-inner .button-small").focus()
    page.keyboard.press("Tab")
    assert toggle.evaluate(
        "e => e === document.activeElement && e.matches(':focus-visible')"
    )
    assert toggle.evaluate("e => getComputedStyle(e).outlineStyle") != "none"
    page.keyboard.press("Enter")
    assert _theme(page)[0] == "dark"
    page.keyboard.press("Space")
    assert _theme(page)[0] == "light"
    assert_clean(page)


def test_no_js_hides_the_toggle_and_follows_the_system(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False, color_scheme="dark")
    page = context.new_page()
    collect(page, site_url)
    page.goto(site_url + "/")
    assert not page.locator(".theme-toggle").is_visible()
    assert (
        page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor")
        == DARK_BG
    )
    assert_clean(page)
    context.close()
