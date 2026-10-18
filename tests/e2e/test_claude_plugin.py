"""CC-4: picking an agent in the builder shows chock's Claude Code plugin option only where chock offers it."""

import chock.install.claude_plugin as chock_offer
import pytest
from conftest import SCREENSHOTS, assert_clean, collect

from sitegen import engine

BUILDER = "/coding/builder/"
HEADING = "Use the Claude Code plugin"
OFFERED = [c for c in chock_offer.settings()["clients"] if chock_offer.routes(c)]


def _pick(page, site_url: str, client: str) -> None:
    page.goto(site_url + BUILDER + "#preset=git-hygiene")
    page.wait_for_selector("#builder-status:not(:empty)")
    page.locator(f"#client-{client}").check()


@pytest.mark.parametrize("client", engine.client_ids())
def test_the_option_follows_the_picked_agent(page, site_url, client) -> None:
    """The picked agent's panel shows chock's routes; every other agent's stays hidden."""
    collect(page, site_url)
    _pick(page, site_url, client)
    shown = page.locator(".client-steps:not([hidden]) .claude-plugin")
    entry = chock_offer.settings()["clients"].get(client, {})
    if client in OFFERED:
        assert shown.count() == 1
        assert shown.locator(".steps-heading").inner_text() == HEADING
        wheres = shown.locator(".claude-route strong").all_inner_texts()
        assert wheres == [f"{r['where']}:" for r in chock_offer.routes(client)]
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        shown.screenshot(path=str(SCREENSHOTS / f"claude_plugin_{client}.png"))
    elif "not_offered" in entry:
        assert shown.count() == 1
        assert HEADING not in shown.inner_text()
        assert shown.inner_text() == entry["not_offered"]
    else:
        assert shown.count() == 0
    assert page.locator(".client-steps[hidden] .claude-plugin").count() == len(
        [
            c
            for c in engine.client_ids()
            if c != client
            and (
                c in OFFERED
                or "not_offered" in chock_offer.settings()["clients"].get(c, {})
            )
        ]
    )
    assert_clean(page)
