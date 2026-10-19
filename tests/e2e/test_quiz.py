"""R-3: the builder's start screen — three questions, a result, and the way into the full builder."""

import json
from pathlib import Path

from conftest import assert_clean, collect, screenshot

from sitegen import engine
from sitegen.presets import load_presets
from tests.fixtures.untested import CLIENT

ROOT = Path(__file__).resolve().parents[2]
PRESETS = {p.id: p for p in load_presets(ROOT / "data" / "presets.yaml")}
BUILDER = "/coding/builder/"
MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 900}
HARD = ("block", "ask")


def _site(page, site_url: str) -> dict:
    return json.loads(page.request.get(site_url + "/data/site.json").text())


def _start(page, site_url: str) -> None:
    page.goto(site_url + BUILDER)
    page.wait_for_selector("#quiz-title:not(:empty)")


def _worry(page, label: str) -> None:
    page.get_by_role("checkbox", name=label).check()


def _next(page) -> None:
    page.locator("#quiz-next").click()


def _result_ids(page) -> list[str]:
    return page.locator(".quiz-pick").evaluate_all(
        "els => els.map(e => e.dataset.policyId)"
    )


def _expected(site: dict, presets: list[str], keywords: tuple[str, ...]) -> list[str]:
    keyword = {p["id"]: p["keyword"] for p in site["policies"]}
    ids: list[str] = []
    for preset in presets:
        for member in PRESETS[preset].members:
            if keyword[member] in keywords and member not in ids:
                ids.append(member)
    return ids


def _answer_secrets_and_skipped(page, strictness: str) -> None:
    _next(page)
    _worry(page, "Leaked secrets")
    _worry(page, "Skipped checks")
    _next(page)
    page.get_by_role("radio", name=strictness).check()
    _next(page)
    page.wait_for_selector(".quiz-pick")


def test_no_fragment_shows_the_start_screen(page, site_url) -> None:
    _start(page, site_url)
    assert page.locator("#quiz").is_visible()
    assert not page.locator("#builder-full").is_visible()
    assert page.locator("#quiz-step").inner_text() == "QUESTION 1 OF 3"
    assert page.locator("#quiz-title").inner_text() == "Which agent do you use?"
    assert page.locator("#quiz-back").is_hidden()
    assert_clean(page)


def test_any_builder_fragment_opens_the_full_builder(page, site_url) -> None:
    for fragment in ("#preset=git-hygiene", "#add=block-no-verify"):
        page.goto(site_url + BUILDER + fragment)
        page.wait_for_selector(".sel-item")
        assert page.locator("#builder-full").is_visible()
        assert page.locator("#quiz").is_hidden()
    page.goto(site_url + BUILDER + "#preset=git-hygiene")
    page.wait_for_selector(".sel-item")
    share = page.locator("#share-url").input_value()
    page.goto(site_url + "/")
    page.goto(share)
    page.wait_for_selector(".sel-item")
    assert page.locator("#quiz").is_hidden()
    assert_clean(page)


def test_skip_opens_the_full_builder_empty(page, site_url) -> None:
    _start(page, site_url)
    page.get_by_role("button", name="Skip to the full builder").click()
    assert page.locator("#builder-full").is_visible()
    assert page.locator("#quiz").is_hidden()
    assert page.locator(".sel-count").inner_text() == "0 policies"
    assert page.evaluate("location.hash") == ""
    assert_clean(page)


def test_the_agent_answer_and_the_agent_picker_are_one_choice(page, site_url) -> None:
    _start(page, site_url)
    for client in ("cursor", "codex", "copilot", "devin", "claude-code"):
        page.locator(f"input[name='quiz-agent'][value='{client}']").check()
        assert page.locator(f"#client-{client}").is_checked()
        assert page.locator(".quiz-note").is_hidden()
        assert page.locator("#quiz-next").is_visible()
    page.locator("input[name='quiz-agent'][value='cursor']").check()
    _answer_secrets_and_skipped(page, "Only hard stops")
    command = page.locator("[data-quiz-command]").inner_text()
    assert command.endswith(" --client cursor --apply")
    assert engine.load_selection(command.split("'")[1])["client"] == "cursor"
    assert "Untested" not in page.locator(".quiz-command").inner_text()
    assert page.locator(".quiz-command .client-untested").count() == 0
    assert_clean(page)


def test_an_untested_agent_answer_says_so_and_skips_apply(page, untested_url) -> None:
    """On the test-only site where CLIENT is untested (tests/fixtures)."""
    _start(page, untested_url)
    page.locator(f"input[name='quiz-agent'][value='{CLIENT}']").check()
    _answer_secrets_and_skipped(page, "Only hard stops")
    command = page.locator("[data-quiz-command]").inner_text()
    assert command.endswith(f" --client {CLIENT}")
    assert engine.load_selection(command.split("'")[1])["client"] == CLIENT
    name = engine.client_name(CLIENT)
    assert f"Untested in {name}." in page.locator(".quiz-command").inner_text()
    assert_clean(page)


def test_next_waits_for_a_worry(page, site_url) -> None:
    _start(page, site_url)
    _next(page)
    assert page.locator("#quiz-next").is_disabled()
    assert "Pick at least one worry" in page.locator(".quiz-need").inner_text()
    _worry(page, "Compliance")
    assert page.locator("#quiz-next").is_enabled()
    assert_clean(page)


def test_secrets_and_skipped_checks_with_hard_stops_give_exactly_those_ids(
    page, site_url
) -> None:
    _start(page, site_url)
    site = _site(page, site_url)
    _answer_secrets_and_skipped(page, "Only hard stops")
    expected = _expected(site, ["secrets", "git-hygiene", "test-integrity"], HARD)
    got = _result_ids(page)
    assert got == expected
    assert len(got) == len(set(got))
    assert page.locator("#quiz-title").inner_text() == (
        f"Your plugin: {len(expected)} guardrails"
    )
    # scan-secret-files blocks and scan-secrets-entropy asks, so both are in; warns and advice are not.
    assert "scan-secret-files" in got and "scan-secrets-entropy" in got
    assert_clean(page)


def test_strictness_adds_warnings_then_advice(page, site_url) -> None:
    _start(page, site_url)
    site = _site(page, site_url)
    presets = ["secrets", "git-hygiene", "test-integrity"]
    _answer_secrets_and_skipped(page, "Stops and warnings")
    assert _result_ids(page) == _expected(site, presets, (*HARD, "warn"))
    page.locator("#quiz-back").click()
    page.get_by_role("radio", name="Everything").check()
    _next(page)
    assert _result_ids(page) == _expected(site, presets, (*HARD, "warn", "advise"))
    assert_clean(page)


def test_a_policy_reached_by_two_answers_appears_once(page, site_url) -> None:
    _start(page, site_url)
    site = _site(page, site_url)
    _next(page)
    worries = page.locator(".quiz-opt input[type=checkbox]")
    for i in range(worries.count()):
        worries.nth(i).check()
    _next(page)
    page.get_by_role("radio", name="Everything").check()
    _next(page)
    page.wait_for_selector(".quiz-pick")
    got = _result_ids(page)
    union = {m for p in PRESETS.values() for m in p.members}
    covered = {
        m
        for preset in [
            "secrets",
            "git-hygiene",
            "test-integrity",
            "shell-containment",
            "agent-config",
            "supply-chain",
            "ci-pipeline",
            "prompt-injection",
            "code-hardening",
            "cloud-iac",
            "owasp-agentic-top10",
            "eu-ai-act",
        ]
        for m in PRESETS[preset].members
    }
    assert len(got) == len(set(got)) == len(covered)
    assert covered <= union
    assert {p["id"] for p in site["policies"]} >= set(got)
    assert_clean(page)


def test_remove_drops_a_pick_and_the_command(page, site_url) -> None:
    _start(page, site_url)
    _answer_secrets_and_skipped(page, "Only hard stops")
    before = _result_ids(page)
    page.get_by_role("button", name=f"Remove {before[0]}", exact=True).click()
    after = _result_ids(page)
    assert after == before[1:]
    command = page.locator("[data-quiz-command]").inner_text()
    ids = [p["id"] for p in engine.load_selection(command.split("'")[1])["policies"]]
    assert sorted(ids) == sorted(after)
    assert_clean(page)


def test_command_is_a_valid_selection_with_the_picked_ids(page, site_url) -> None:
    _start(page, site_url)
    _answer_secrets_and_skipped(page, "Only hard stops")
    command = page.locator("[data-quiz-command]").inner_text()
    assert command.startswith("chock install --selection '")
    assert command.endswith("' --client claude-code --apply")
    selection = engine.load_selection(command.split("'")[1])
    assert sorted(p["id"] for p in selection["policies"]) == sorted(_result_ids(page))
    site = _site(page, site_url)
    assert selection["catalog"]["ref"] == site["catalog"]["ref"]
    assert_clean(page)


def test_open_in_the_full_builder_restores_the_same_ids(page, site_url) -> None:
    _start(page, site_url)
    _answer_secrets_and_skipped(page, "Only hard stops")
    expected = sorted(_result_ids(page))
    page.get_by_role("link", name="Open in the full builder").click()
    page.wait_for_selector(".sel-item")
    assert page.locator("#builder-full").is_visible()
    assert page.locator("#quiz").is_hidden()
    got = sorted(
        page.locator(".sel-item").evaluate_all(
            "els => els.map(e => e.dataset.policyId)"
        )
    )
    assert got == expected
    assert page.evaluate("location.hash").startswith("#s=")
    assert_clean(page)


def test_start_over_returns_to_question_one(page, site_url) -> None:
    _start(page, site_url)
    _answer_secrets_and_skipped(page, "Only hard stops")
    assert page.locator("#quiz-next").inner_text() == "Start over"
    _next(page)
    assert page.locator("#quiz-step").inner_text() == "QUESTION 1 OF 3"
    assert_clean(page)


def test_the_whole_quiz_works_by_keyboard(page, site_url) -> None:
    _start(page, site_url)
    keys = page.keyboard
    # Question 1: Claude Code is preselected; tab to Next and press it.
    page.locator("#quiz-title").focus()
    keys.press("Tab")
    assert page.evaluate("document.activeElement.name") == "quiz-agent"
    keys.press("ArrowDown")  # Cursor: the agent picker follows, focus stays here
    assert page.locator("#client-cursor").is_checked()
    assert page.evaluate("document.activeElement.value") == "cursor"
    keys.press("ArrowUp")  # Claude Code again
    assert page.locator("#client-claude-code").is_checked()
    assert page.evaluate("document.activeElement.name") == "quiz-agent"
    while page.evaluate("document.activeElement.id") != "quiz-next":
        keys.press("Tab")
    keys.press("Enter")
    assert page.locator("#quiz-step").inner_text() == "QUESTION 2 OF 3"
    assert page.evaluate("document.activeElement.id") == "quiz-title"
    # Question 2: tab to the first checkbox, tick it with Space, move on.
    keys.press("Tab")
    assert page.evaluate("document.activeElement.type") == "checkbox"
    keys.press("Space")
    while page.evaluate("document.activeElement.id") != "quiz-next":
        keys.press("Tab")
    keys.press("Enter")
    assert page.locator("#quiz-step").inner_text() == "QUESTION 3 OF 3"
    # Question 3: choose "Only hard stops" with the arrow keys, then show the result.
    keys.press("Tab")
    assert page.evaluate("document.activeElement.name") == "quiz-strictness"
    keys.press("ArrowUp")
    while page.evaluate("document.activeElement.id") != "quiz-next":
        keys.press("Tab")
    keys.press("Enter")
    assert page.locator("#quiz-step").inner_text() == "YOUR RESULT"
    ids = _result_ids(page)
    assert ids == _expected(_site(page, site_url), ["secrets"], HARD)
    # Result: remove a pick, copy, and open the full builder, all from the keyboard.
    page.locator(".quiz-pick .remove").first.focus()
    keys.press("Enter")
    assert _result_ids(page) == ids[1:]
    assert page.evaluate("document.activeElement.classList.contains('remove')")
    page.locator("#quiz-open").focus()
    keys.press("Enter")
    page.wait_for_selector(".sel-item")
    assert page.locator("#builder-full").is_visible()
    assert_clean(page)


def test_start_screen_fits_a_phone_and_screenshots(browser, site_url) -> None:
    for size, viewport in (("desktop", DESKTOP), ("mobile", MOBILE)):
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            collect(page, site_url)
            _start(page, site_url)
            screenshot(page, f"quiz-q1-{size}")
            _next(page)
            _worry(page, "Leaked secrets")
            _worry(page, "Skipped checks")
            screenshot(page, f"quiz-q2-{size}")
            _next(page)
            screenshot(page, f"quiz-q3-{size}")
            _next(page)
            page.wait_for_selector(".quiz-pick")
            screenshot(page, f"quiz-result-{size}")
            overflow = page.evaluate(
                "document.scrollingElement.scrollWidth > window.innerWidth"
            )
            assert not overflow, f"horizontal scroll on the result at {size}"
            page.locator("#quiz-back").click()
            page.locator("#quiz-back").click()
            overflow = page.evaluate(
                "document.scrollingElement.scrollWidth > window.innerWidth"
            )
            assert not overflow, f"horizontal scroll on question 2 at {size}"
            assert_clean(page)
        finally:
            context.close()


def test_result_rows_show_policy_names(page, site_url) -> None:
    site = _site(page, site_url)
    names = {p["id"]: p["name"] for p in site["policies"]}
    _start(page, site_url)
    _answer_secrets_and_skipped(page, "Stops and warnings")
    rows = page.locator(".quiz-pick")
    assert rows.count() > 0
    for i in range(rows.count()):
        row = rows.nth(i)
        policy_id = row.get_attribute("data-policy-id")
        name = row.locator(".quiz-pick-name")
        assert name.inner_text().startswith(names[policy_id])
        assert name.locator(".quiz-pick-id").inner_text() == policy_id
    assert_clean(page)


WIDE = {"width": 1900, "height": 1000}


def _option_boxes(page) -> list[dict]:
    return page.locator(".quiz-opt-box").evaluate_all(
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {top: r.top, height: r.height, label: e.textContent}; })"
    )


def _assert_cards_aligned(boxes: list[dict], where: str, whole: bool) -> None:
    """One height for the whole grid (desktop) or per row (phone), and shared row tops."""
    rows: dict[int, list[dict]] = {}
    for box in boxes:
        rows.setdefault(round(box["top"] / 4), []).append(box)
    for group in [boxes] if whole else rows.values():
        heights = [box["height"] for box in group]
        assert max(heights) - min(heights) <= 1, f"{where}: card heights {heights}"
    for row in rows.values():
        tops = [box["top"] for box in row]
        assert max(tops) - min(tops) <= 1, f"{where}: card tops {tops}"


def test_every_quiz_step_has_equal_option_cards(browser, site_url) -> None:
    for viewport in (DESKTOP, WIDE, MOBILE):
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            collect(page, site_url)
            _start(page, site_url)
            for step in range(1, 4):
                page.wait_for_selector(".quiz-opt-box")
                where = f"{viewport['width']} px, question {step}"
                boxes = _option_boxes(page)
                assert len(boxes) > 1, where
                _assert_cards_aligned(boxes, where, viewport["width"] > 760)
                if step == 2:
                    page.locator(".quiz-opt input").first.check()
                if step < 3:
                    _next(page)
                    page.wait_for_function(
                        "n => document.querySelector('#quiz-step').textContent"
                        ".startsWith('QUESTION ' + n)",
                        arg=step + 1,
                    )
            assert_clean(page)
        finally:
            context.close()


def test_every_strictness_leaves_out_ungraded_policies_unless_asked(
    page, site_url
) -> None:
    _start(page, site_url)
    site = _site(page, site_url)
    ungraded = site["builder_clients"]["ungraded"]
    grok = {p["id"]: p["agent_labels"]["grok"]["keyword"] for p in site["policies"]}
    assert set(grok.values()) == {ungraded}  # the catalog grades nothing on grok yet
    page.locator("input[name='quiz-agent'][value='grok']").check()
    _next(page)
    for worry in ("Leaked secrets", "Skipped checks", "Destructive or risky shell"):
        _worry(page, worry)
    _next(page)
    page.get_by_role("radio", name="Only hard stops").check()
    _next(page)
    page.wait_for_selector(".quiz-empty")
    assert _result_ids(page) == []
    page.locator("#quiz-back").click()
    page.get_by_role(
        "checkbox", name="Include policies this agent is not graded on"
    ).check()
    _next(page)
    page.wait_for_selector(".quiz-pick")
    assert any(grok[i] == ungraded for i in _result_ids(page))
    page.locator("#quiz-back").click()
    page.get_by_role("radio", name="Everything").check()
    page.get_by_role(
        "checkbox", name="Include policies this agent is not graded on"
    ).uncheck()
    _next(page)
    page.wait_for_selector(".quiz-empty")
    assert _result_ids(page) == []
