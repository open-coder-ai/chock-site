"""The builder (plan 6.5, PR 3): presets, URL state, downloads, warnings, real install."""

import json
import subprocess
import sys
from pathlib import Path

from conftest import CATALOG, assert_clean, collect, screenshot

from sitegen import engine
from sitegen.presets import load_presets

ROOT = Path(__file__).resolve().parents[2]
PRESETS = {p.id: p for p in load_presets(ROOT / "data" / "presets.yaml")}
BUILDER = "/coding/builder/"
MOBILE = {"width": 390, "height": 844}


def _open(page, site_url: str, fragment: str = "") -> None:
    page.goto(site_url + BUILDER + fragment)
    page.wait_for_selector("#builder-status:not(:empty)")


def _members(preset: str) -> list[str]:
    return sorted(PRESETS[preset].members)


def _share(page) -> str:
    return page.locator("#share-url").input_value()


def _code(page) -> str:
    return page.locator("[data-selection-code]").get_attribute("data-selection-code")


def _count(page) -> str:
    return page.locator(".sel-count").inner_text()


def _picked_ids(page) -> list[str]:
    return sorted(
        page.locator(".sel-item").evaluate_all(
            "els => els.map(e => e.dataset.policyId)"
        )
    )


def test_preset_gives_command_share_link_and_valid_selection(page, site_url) -> None:
    _open(page, site_url)
    page.select_option("#builder-start", "git-hygiene")
    members = _members("git-hygiene")
    assert _count(page) == f"{len(members)} policies"
    assert "--selection '" in page.locator("[data-selection-code]").inner_text()
    share = _share(page)
    assert "#s=" in share
    assert sorted(p["id"] for p in engine.load_selection(share)["policies"]) == members
    assert page.evaluate("location.hash").startswith("#s=")
    screenshot(page, "builder_git_hygiene")
    assert_clean(page)


def test_share_link_restores_the_picks_in_a_new_page(page, site_url) -> None:
    _open(page, site_url)
    page.select_option("#builder-start", "git-hygiene")
    share = _share(page)
    other = page.context.new_page()
    collect(other, site_url)
    other.goto(share)
    other.wait_for_selector(".sel-item")
    assert _picked_ids(other) == _members("git-hygiene")
    assert other.locator(".bmember input:checked").count() >= len(
        _members("git-hygiene")
    )
    assert_clean(other)


def test_download_is_a_valid_selection(page, site_url, tmp_path: Path) -> None:
    _open(page, site_url)
    page.select_option("#builder-start", "secrets")
    page.get_by_role("tab", name="Selection file").click()
    with page.expect_download() as info:
        page.get_by_role("button", name="Download chock.selection.yaml").click()
    download = info.value
    assert download.suggested_filename == "chock.selection.yaml"
    target = tmp_path / "chock.selection.yaml"
    download.save_as(str(target))
    selection = json.loads(target.read_text(encoding="utf-8"))
    engine.check_selection(selection)
    assert sorted(p["id"] for p in selection["policies"]) == _members("secrets")
    assert selection["preset"] == "secrets"
    assert_clean(page)


def test_missing_partner_note_names_the_twin(page, site_url) -> None:
    _open(page, site_url)
    page.check("input[value='block-wildcard-agent-permissions']")
    notes = page.locator(".notes")
    assert "agent-permissions-scan" in notes.inner_text()
    assert page.locator(".notes").get_attribute("aria-live") == "polite"
    page.check("input[value='agent-permissions-scan']")
    assert "without agent-permissions-scan" not in notes.inner_text()
    assert_clean(page)


def test_file_absent_note(page, site_url) -> None:
    _open(page, site_url)
    page.check("input[value='verify-dependency-exists']")
    text = page.locator(".notes").inner_text()
    assert "verify-dependency-exists" in text
    assert ".chock/dependency-allowlist.txt" in text
    assert_clean(page)


def test_removing_every_pick_disables_outputs_and_clears_the_fragment(
    page, site_url
) -> None:
    _open(page, site_url)
    page.select_option("#builder-start", "test-integrity")
    assert page.evaluate("location.hash").startswith("#s=")
    while page.locator(".sel-item .remove").count():
        page.locator(".sel-item .remove").first.click()
    assert _count(page) == "0 policies"
    assert page.locator("#need-one").is_visible()
    for tab in page.get_by_role("tab").all():
        assert tab.is_disabled()
    assert page.evaluate("location.hash") == ""
    assert_clean(page)


def test_unreadable_link_says_so_and_starts_empty(page, site_url) -> None:
    _open(page, site_url, "#s=not-base64!")
    assert page.get_by_text("This link could not be read.").is_visible()
    assert _count(page) == "0 policies"
    assert page.locator(".bmember input:checked").count() == 0
    assert_clean(page)


def test_other_catalog_ref_shows_notice_and_can_be_used_anyway(page, site_url) -> None:
    _open(page, site_url)
    page.select_option("#builder-start", "git-hygiene")
    selection = engine.load_selection(_share(page))
    selection["catalog"]["ref"] = "0" * 40
    _open(page, site_url, "#s=" + engine.encode_selection(selection))
    notice = page.locator("#link-notice").inner_text()
    assert "000000000000" in notice
    assert "this site shows" in notice
    assert _count(page) == "0 policies"
    page.get_by_role("button", name="Use the same policies here").click()
    assert _picked_ids(page) == _members("git-hygiene")
    assert_clean(page)


def test_unknown_id_is_listed_not_dropped_silently(page, site_url) -> None:
    _open(page, site_url)
    page.select_option("#builder-start", "test-integrity")
    selection = engine.load_selection(_share(page))
    selection["policies"].append(
        {"id": "no-such-policy", "version": "0.0.1", "sha256": "0" * 64}
    )
    _open(page, site_url, "#s=" + engine.encode_selection(selection))
    assert (
        "Not available here: no-such-policy"
        in page.locator("#link-notice").inner_text()
    )
    assert _picked_ids(page) == _members("test-integrity")


def test_preset_and_add_fragments(page, site_url) -> None:
    _open(page, site_url, "#preset=secrets")
    assert _picked_ids(page) == _members("secrets")
    assert page.evaluate("location.hash").startswith("#s=")
    _open(page, site_url, "#add=block-no-verify")
    assert _picked_ids(page) == ["block-no-verify"]


def test_command_installs_end_to_end(page, site_url, tmp_path: Path) -> None:
    _open(page, site_url)
    page.select_option("#builder-start", "git-hygiene")
    code = _code(page)
    # chock reads the source's main branch; CI checks .catalog out detached at the
    # pin, so install from a throwaway clone whose main sits at that same commit.
    ref = (ROOT / ".catalog-ref").read_text(encoding="utf-8").strip()
    clone = tmp_path / "catalog"
    for git in (
        ["clone", "-q", "--no-checkout", str(CATALOG.resolve()), str(clone)],
        ["-C", str(clone), "checkout", "-q", "-B", "main", ref],
    ):
        subprocess.run(["git", *git], check=True, capture_output=True, timeout=120)
    selection = engine.load_selection(code)
    assert selection["catalog"]["ref"] == ref
    selection["catalog"]["source"] = str(clone)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "chock",
            "install",
            "--selection",
            engine.encode_selection(selection),
            "--dest",
            str(tmp_path / "marketplace"),
            "--allow-source",
            str(clone),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for policy_id in _members("git-hygiene"):
        assert policy_id in result.stdout, policy_id
    assert any(
        word in result.stdout for word in ("blocks", "asks", "warns", "advisory")
    )


def test_outputs_work_from_the_keyboard(page, site_url) -> None:
    _open(page, site_url)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    box = page.locator("#pick-test-integrity-block-test-skips")
    box.focus()
    page.keyboard.press("Space")
    assert _count(page) == "1 policy"
    page.keyboard.press("Space")
    assert _count(page) == "0 policies"
    page.keyboard.press("Space")
    tab = page.get_by_role("tab", name="Command")
    tab.focus()
    page.keyboard.press("ArrowRight")
    assert (
        page.get_by_role("tab", name="Share link").get_attribute("aria-selected")
        == "true"
    )
    page.keyboard.press("ArrowLeft")
    page.get_by_role("button", name="Copy command").focus()
    page.keyboard.press("Enter")
    page.get_by_role("button", name="Copied").wait_for()
    assert "chock install --selection" in page.evaluate(
        "navigator.clipboard.readText()"
    )
    assert_clean(page)


def test_picks_never_leave_the_browser(page, site_url) -> None:
    requests: list[str] = []
    page.on("request", lambda req: requests.append(req.url))
    _open(page, site_url)
    page.select_option("#builder-start", "git-hygiene")
    code = _code(page)
    page.reload()
    page.wait_for_selector(".sel-item")
    assert requests
    assert not any(code in url or "#" in url for url in requests)
    assert_clean(page)


def test_filters_narrow_the_list(page, site_url) -> None:
    _open(page, site_url)
    total = page.locator(".bmember:not(.hidden)").count()
    page.get_by_role("button", name="blocks").click()
    rows = page.locator(".bmember:not(.hidden)")
    assert 0 < rows.count() < total
    assert set(rows.evaluate_all("els => els.map(e => e.dataset.label)")) == {"block"}
    page.fill("#builder-search", "no-verify")
    assert (
        page.locator(".bmember:not(.hidden)[data-policy-id='block-no-verify']").count()
        >= 1
    )
    assert_clean(page)


def test_builder_screenshots(browser, site_url) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    try:
        page = context.new_page()
        collect(page, site_url)
        _open(page, site_url)
        screenshot(page, "builder_empty")
        page.select_option("#builder-start", "git-hygiene")
        assert page.locator(".notes .note-card").count() >= 1
        screenshot(page, "builder_git_hygiene_with_note")
        assert_clean(page)
    finally:
        context.close()
    mobile = browser.new_context(viewport=MOBILE)
    try:
        page = mobile.new_page()
        collect(page, site_url)
        _open(page, site_url, "#preset=git-hygiene")
        width = page.evaluate(
            "[document.scrollingElement.scrollWidth, window.innerWidth]"
        )
        assert width[0] <= width[1], width
        screenshot(page, "builder_mobile")
        assert_clean(page)
    finally:
        mobile.close()
