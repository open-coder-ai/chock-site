"""BV-S1: the agent picker, each agent's own labels, command, steps and share link."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import CATALOG, SCREENSHOTS, assert_clean, collect

from sitegen import engine
from sitegen.presets import load_presets

ROOT = Path(__file__).resolve().parents[2]
PRESETS = {p.id: p for p in load_presets(ROOT / "data" / "presets.yaml")}
BUILDER = "/coding/builder/"
CLIENTS = ("claude-code", "cursor", "codex", "copilot", "devin")
PRESET = "git-hygiene"
SIZES = {
    "desktop": {"width": 1280, "height": 900},
    "phone": {"width": 390, "height": 844},
}


def _site(page, site_url: str) -> dict:
    return json.loads(page.request.get(site_url + "/data/site.json").text())


def _open(page, site_url: str, fragment: str) -> None:
    page.goto(site_url + BUILDER + fragment)
    page.wait_for_selector("#builder-status:not(:empty)")


def _pick(page, site_url: str, client: str) -> None:
    """The full builder with the preset picked, then the agent chosen in the picker."""
    _open(page, site_url, f"#preset={PRESET}")
    page.locator(f"#client-{client}").check()


def _code(page) -> str:
    return page.locator("[data-selection-code]").get_attribute("data-selection-code")


def _visible_clients(page, selector: str) -> list[str]:
    return page.locator(selector).evaluate_all(
        "els => els.filter(e => !e.hidden).map(e => e.dataset.client)"
    )


def test_default_is_claude_code_and_the_picker_lists_five_agents(
    page, site_url
) -> None:
    page.goto(site_url + BUILDER)
    page.wait_for_selector("#quiz-title:not(:empty)")
    values = page.locator("#client-picker input[name='client']").evaluate_all(
        "els => els.map(e => e.value)"
    )
    assert values == list(CLIENTS)
    assert page.locator("#client-claude-code").is_checked()
    assert page.evaluate("location.hash") == ""
    assert_clean(page)


@pytest.mark.parametrize("client", CLIENTS)
def test_each_agent_gets_its_command_steps_and_labels(page, site_url, client) -> None:
    site = _site(page, site_url)
    about = site["builder_clients"]["clients"][client]
    _pick(page, site_url, client)
    command = page.locator("[data-selection-code]").inner_text()
    if about["witness"] == "witnessed":
        assert command.endswith(f" --client {client} --apply")
    else:
        assert command.endswith(f" --client {client}")
    selection = engine.check_selection(engine.load_selection(_code(page)))
    assert selection["client"] == client
    assert selection["schema"] == 2
    assert [p["id"] for p in selection["policies"]] == sorted(PRESETS[PRESET].members)
    assert _visible_clients(page, ".client-steps") == [client]
    untested = _visible_clients(page, ".client-untested")
    assert untested == ([] if about["witness"] == "witnessed" else [client])
    if untested:
        link = page.locator(f".client-untested[data-client='{client}'] a")
        assert link.get_attribute("href") == site["builder_clients"]["checklist"]
        assert about["untested_label"] in page.locator("#panel-command").inner_text()
    rows = page.locator(".bmember[data-policy-id]").evaluate_all(
        "els => els.map(e => [e.dataset.policyId, e.dataset.label,"
        " e.querySelector('.bsays').textContent])"
    )
    for policy_id, keyword, says in rows:
        label = about["labels"][policy_id]
        assert (keyword, says) == (label["keyword"], label["says"]), policy_id
    assert page.locator(".sel-item").count() == len(PRESETS[PRESET].members)
    assert_clean(page)


@pytest.mark.parametrize("client", CLIENTS)
def test_share_link_round_trips_per_agent(page, site_url, client) -> None:
    _pick(page, site_url, client)
    code = _code(page)
    share = page.locator("#share-url").input_value()
    ids = ",".join(sorted(PRESETS[PRESET].members))
    assert share.endswith(f"{BUILDER}#client={client}&p={ids}")
    other = page.context.new_page()
    collect(other, site_url)
    other.goto(share)
    other.wait_for_selector(".sel-item")
    assert other.locator(f"#client-{client}").is_checked()
    assert engine.load_selection(_code(other)) == engine.load_selection(code)
    assert_clean(page)
    assert_clean(other)


def test_the_page_fragment_keeps_the_agent(page, site_url) -> None:
    _pick(page, site_url, "devin")
    assert engine.load_selection(page.url)["client"] == "devin"
    page.reload()
    page.wait_for_selector(".sel-item")
    assert page.locator("#client-devin").is_checked()
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#builder-start").select_option("")
    assert page.evaluate("location.hash") == "#client=devin"
    assert_clean(page)


def test_an_unknown_agent_in_a_link_is_named(page, site_url) -> None:
    _open(page, site_url, "#client=vim&p=block-no-verify")
    assert "vim" in page.locator("#link-notice").inner_text()
    assert page.locator("#client-claude-code").is_checked()
    assert page.locator(".sel-item").count() == 0
    assert_clean(page)


def test_grades_note_shows_only_without_per_client_grades(page, site_url) -> None:
    graded = _site(page, site_url)["builder_clients"]["graded"]
    page.goto(site_url + BUILDER)
    assert page.locator("#grades-note").count() == (0 if graded else 1)
    assert_clean(page)


@pytest.mark.parametrize("size", SIZES)
def test_panel_screenshots(browser, site_url, size) -> None:
    context = browser.new_context(viewport=SIZES[size])
    try:
        page = context.new_page()
        collect(page, site_url)
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        for client in CLIENTS:
            _pick(page, site_url, client)
            width = page.evaluate(
                "[document.scrollingElement.scrollWidth, window.innerWidth]"
            )
            assert width[0] <= width[1], (client, width)
            page.locator("#client-picker").screenshot(
                path=str(SCREENSHOTS / f"clients_picker_{client}_{size}.png")
            )
            page.locator("#panel-command").screenshot(
                path=str(SCREENSHOTS / f"clients_panel_{client}_{size}.png")
            )
        assert_clean(page)
    finally:
        context.close()


@pytest.mark.parametrize("client", CLIENTS)
def test_the_command_builds_for_each_agent(page, site_url, client, tmp_path) -> None:
    """The builder's code, run through `chock install --client` without --apply: build only."""
    _pick(page, site_url, client)
    ref = (ROOT / ".catalog-ref").read_text(encoding="utf-8").strip()
    clone = tmp_path / "catalog"
    for git in (
        ["clone", "-q", "--no-checkout", str(CATALOG.resolve()), str(clone)],
        ["-C", str(clone), "checkout", "-q", "-B", "main", ref],
    ):
        subprocess.run(["git", *git], check=True, capture_output=True, timeout=120)
    selection = engine.load_selection(_code(page))
    selection["catalog"]["source"] = str(clone)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "chock",
            "install",
            "--selection",
            engine.encode_selection(selection),
            "--client",
            client,
            "--dest",
            str(tmp_path / "plugins"),
            "--allow-source",
            str(clone),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for policy_id in PRESETS[PRESET].members:
        assert policy_id in result.stdout, policy_id
