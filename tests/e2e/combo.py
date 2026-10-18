"""Drive the builder's "Start from" combobox (select.js) the way a visitor does."""


def pick_start(page, value: str) -> None:
    """Open the "Start from" list and click the option whose native value is `value`."""
    index = page.locator("#builder-start").evaluate(
        "(s, v) => [...s.options].findIndex((o) => o.value === v)", value
    )
    assert index >= 0, f"no preset {value!r} in the Start from list"
    page.locator("#builder-start-combo").click()
    page.locator(f"#builder-start-list-{index}").click()
