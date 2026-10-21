"""SITE-PRESET-SELECT: the builder's "Start from" combobox (select.js) over the native select."""

from pathlib import Path

import pytest
from combo import pick_start
from conftest import assert_clean, collect, screenshot
from test_sentence_case import _lowercase

from sitegen.presets import load_presets

ROOT = Path(__file__).resolve().parents[2]
PRESETS = load_presets(ROOT / "data" / "presets.yaml")
BY_ID = {p.id: p for p in PRESETS}
BUILDER = "/coding/builder/"
COMBO = "#builder-start-combo"
LIST = "#builder-start-list"


def _open(page, site_url: str, fragment: str = "") -> None:
    """Open the full builder; with no fragment the start screen shows, so skip it."""
    collect(page, site_url)
    page.goto(site_url + BUILDER + fragment)
    if not fragment:
        page.get_by_role("button", name="Skip to the full builder").click()
    page.wait_for_selector("#builder-status:not(:empty)")


def _shown(page) -> str:
    return page.locator(f"{COMBO} .combo-value").inner_text()


def _active(page) -> str:
    """The text of the option aria-activedescendant points at."""
    active = page.locator(COMBO).get_attribute("aria-activedescendant")
    assert active, "no aria-activedescendant while the list is open"
    return page.locator(f"#{active}").inner_text()


def _label(preset) -> str:
    return f"{preset.title} · {len(preset.members)}"


def test_roles_states_and_same_options_as_the_native_select(page, site_url) -> None:
    """Button with role combobox named by its label, a listbox with one option per preset."""
    _open(page, site_url)
    assert page.locator("#builder-start").is_hidden()
    combo = page.get_by_role("combobox", name="Start from")
    assert combo.get_attribute("id") == "builder-start-combo"
    assert combo.get_attribute("aria-haspopup") == "listbox"
    assert combo.get_attribute("aria-expanded") == "false"
    assert combo.get_attribute("aria-controls") == "builder-start-list"
    assert page.locator(LIST).is_hidden()
    assert _shown(page) == "Nothing"
    combo.click()
    assert combo.get_attribute("aria-expanded") == "true"
    listbox = page.get_by_role("listbox", name="Start from")
    assert listbox.is_visible()
    options = listbox.get_by_role("option")
    native = page.locator("#builder-start option").all_inner_texts()
    assert options.all_inner_texts() == native
    assert native == ["Nothing"] + [_label(p) for p in PRESETS]
    assert page.locator(f"{LIST} [aria-selected='true']").count() == 1
    assert _active(page) == "Nothing"
    assert_clean(page)


def test_mouse_pick_applies_preset_marks_it_and_returns_focus(page, site_url) -> None:
    """Click opens the list under the button; clicking an option picks it and closes."""
    _open(page, site_url)
    page.locator(COMBO).click()
    button = page.locator(COMBO).bounding_box()
    listbox = page.locator(LIST).bounding_box()
    assert listbox["y"] >= button["y"] + button["height"]
    assert abs(listbox["x"] - button["x"]) <= 1
    page.get_by_role("option", name=_label(BY_ID["secrets"])).click()
    assert page.locator(COMBO).get_attribute("aria-expanded") == "false"
    assert page.locator(LIST).is_hidden()
    assert page.evaluate("document.activeElement.id") == "builder-start-combo"
    assert _shown(page) == _label(BY_ID["secrets"])
    assert page.locator("#builder-start").input_value() == "secrets"
    assert page.locator(".sel-count").inner_text() == (
        f"{len(BY_ID['secrets'].members)} policies"
    )
    page.locator(COMBO).click()
    current = page.locator(f"{LIST} .combo-option.is-current")
    assert current.inner_text() == _label(BY_ID["secrets"])
    assert _active(page) == _label(BY_ID["secrets"])
    page.mouse.click(5, 5)
    assert page.locator(LIST).is_hidden()
    assert_clean(page)


def test_keyboard_arrows_home_end_type_ahead_enter_escape(page, site_url) -> None:
    """The APG select-only keys; Escape closes without picking, focus stays on the button."""
    _open(page, site_url)
    page.locator(COMBO).focus()
    page.keyboard.press("ArrowDown")
    assert page.locator(COMBO).get_attribute("aria-expanded") == "true"
    assert _active(page) == "Nothing"
    page.keyboard.press("ArrowDown")
    assert _active(page) == _label(PRESETS[0])
    page.keyboard.press("End")
    assert _active(page) == _label(PRESETS[-1])
    page.keyboard.press("ArrowDown")
    assert _active(page) == _label(PRESETS[-1])
    page.keyboard.press("Home")
    assert _active(page) == "Nothing"
    page.keyboard.press("ArrowUp")
    assert _active(page) == "Nothing"
    page.keyboard.press("Escape")
    assert page.locator(COMBO).get_attribute("aria-expanded") == "false"
    assert _shown(page) == "Nothing"
    assert page.locator(".sel-count").inner_text() == "0 policies"
    # Type-ahead opens the list and moves to the first match after the active option.
    page.keyboard.type("s")
    assert page.locator(COMBO).get_attribute("aria-expanded") == "true"
    assert _active(page) == _label(BY_ID["secrets"])
    page.keyboard.type("h")
    assert _active(page) == _label(BY_ID["shell-containment"])
    page.keyboard.press("Enter")
    assert page.locator(COMBO).get_attribute("aria-expanded") == "false"
    assert page.evaluate("document.activeElement.id") == "builder-start-combo"
    assert page.locator("#builder-start").input_value() == "shell-containment"
    assert page.locator(".sel-count").inner_text() == (
        f"{len(BY_ID['shell-containment'].members)} policies"
    )
    assert_clean(page)


def test_declined_replace_keeps_the_shown_preset(page, site_url) -> None:
    """Replacing picks asks first; declining leaves the control on the previous preset."""
    _open(page, site_url, "#preset=git-hygiene")
    assert _shown(page) == _label(BY_ID["git-hygiene"])
    page.once("dialog", lambda dialog: dialog.dismiss())
    pick_start(page, "secrets")
    assert _shown(page) == _label(BY_ID["git-hygiene"])
    assert page.locator("#builder-start").input_value() == "git-hygiene"
    page.once("dialog", lambda dialog: dialog.accept())
    pick_start(page, "secrets")
    assert _shown(page) == _label(BY_ID["secrets"])
    assert_clean(page)


def test_share_link_round_trip_shows_the_preset(page, site_url) -> None:
    """A preset picked here comes back in the control when its share link is opened."""
    _open(page, site_url)
    pick_start(page, "ci-pipeline")
    share = page.locator("#share-url").input_value()
    assert share.endswith(f"&p={','.join(sorted(BY_ID['ci-pipeline'].members))}")
    assert_clean(page)
    other = page.context.new_page()
    collect(other, site_url)
    other.goto(share)
    other.wait_for_selector("#builder-status:not(:empty)")
    assert _shown(other) == _label(BY_ID["ci-pipeline"])
    assert other.locator("#builder-start").input_value() == "ci-pipeline"
    assert_clean(other)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_list_uses_site_tokens_in_both_themes(browser, site_url, scheme) -> None:
    """Button and list take the theme's panel, text and line colours, not the OS defaults."""
    context = browser.new_context(color_scheme=scheme)
    try:
        page = context.new_page()
        _open(page, site_url)
        page.locator(COMBO).click()
        got = page.evaluate(
            """() => {
              const css = getComputedStyle(document.documentElement);
              const probe = document.createElement("div");
              document.body.appendChild(probe);
              const colour = (name) => {
                probe.style.color = css.getPropertyValue(name);
                return getComputedStyle(probe).color;
              };
              const tokens = { panel: colour("--panel"), text: colour("--text"),
                               line: colour("--line-2") };
              probe.remove();
              const list = getComputedStyle(document.getElementById("builder-start-list"));
              const button = getComputedStyle(document.getElementById("builder-start-combo"));
              return { tokens, list: list.backgroundColor, border: list.borderTopColor,
                       button: button.backgroundColor, color: button.color,
                       overflow: list.overflowY, maxHeight: list.maxHeight };
            }"""
        )
        assert got["list"] == got["tokens"]["panel"]
        assert got["button"] == got["tokens"]["panel"]
        assert got["color"] == got["tokens"]["text"]
        assert got["border"] == got["tokens"]["line"]
        assert got["overflow"] == "auto"
        assert got["maxHeight"] != "none"
        screenshot(page, f"preset-select-{scheme}-1280")
    finally:
        context.close()


def test_list_fits_a_phone_screen(browser, site_url) -> None:
    """At 390 px the open list stays inside the viewport and the page does not scroll sideways."""
    context = browser.new_context(viewport={"width": 390, "height": 844})
    try:
        page = context.new_page()
        _open(page, site_url)
        page.locator(COMBO).click()
        box = page.locator(LIST).bounding_box()
        assert box["x"] >= 0
        assert box["x"] + box["width"] <= 390
        assert page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
        page.get_by_role("option", name=_label(BY_ID["git-hygiene"])).click()
        assert _shown(page) == _label(BY_ID["git-hygiene"])
        screenshot(page, "preset-select-390")
    finally:
        context.close()


def test_without_javascript_the_native_select_stays(browser, site_url) -> None:
    """Progressive enhancement: no script, no combobox; the native select is shown."""
    context = browser.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(site_url + BUILDER)
        select = page.locator("#builder-start")
        assert select.is_visible()
        assert select.locator("option").count() == len(PRESETS) + 1
        assert page.locator(COMBO).count() == 0
        assert page.get_by_label("Start from").get_attribute("id") == "builder-start"
    finally:
        context.close()


def test_open_list_text_starts_uppercase(page, site_url) -> None:
    """SITE-CAPS checker over the builder with the list open."""
    _open(page, site_url)
    page.locator(COMBO).click()
    assert _lowercase(page, site_url) == []
    assert_clean(page)
