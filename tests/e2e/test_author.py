"""The author page (BV-S2): interview, files, catalog mixing, drafts, setup script."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import SCREENSHOTS, assert_clean, collect, screenshot

AUTHOR = "/coding/author/"
MOBILE = {"width": 390, "height": 844}

# Answers that satisfy every kind's cross-field validation.
FILLS = {
    "content_regex": {
        "name": "block secrets",
        "stop": "BEGIN PRIVATE KEY",
        "message": "That line is marked do-not-commit; remove it.",
        "refuse_example": "key = BEGIN PRIVATE KEY",
        "pass_example": "key = os.environ['KEY']",
    },
    "guard": {
        "name": "no destroy",
        "stop": "terraform destroy",
        "message": "Run terraform yourself after review.",
        "refuse_example": "terraform destroy -auto-approve",
        "pass_example": "terraform plan",
    },
    "script": {
        "name": "no env files",
        "stop": ".env, secrets.yaml",
        "message": "That file holds secrets; never write it.",
        "refuse_example": "secrets/.env",
        "pass_example": "src/app.py",
    },
    "rule": {
        "name": "tests stay green",
        "stop": "commit code while a test fails",
        "message": "fix the code until the tests pass",
        "refuse_example": "Mark a failing test as skipped.",
        "pass_example": "Fix the code so the test passes.",
    },
    "skill": {
        "name": "release notes",
        "stop": "writing a release note for a merged change",
        "message": "Read the diff.\nWrite one line on what changed for a user.",
        "refuse_example": "Write the release note for the dark-mode change.",
        "pass_example": "Fix the failing build.",
    },
}

KIND_IDS = {
    "content_regex": "my-block-secrets",
    "guard": "my-no-destroy",
    "script": "my-no-env-files",
    "rule": "my-tests-stay-green",
    "skill": "my-release-notes",
}


def _open(page, site_url: str, fragment: str = "") -> None:
    page.goto(site_url + AUTHOR + fragment)
    page.wait_for_selector("#author-fields .field")


def _fill(page, kind: str) -> None:
    page.evaluate("localStorage.removeItem('chock.author.draft.v1')")
    page.check(f"input[name='author-kind'][value='{kind}']")
    page.fill("#author-name", FILLS[kind]["name"])
    for key in ("stop", "message", "refuse_example", "pass_example"):
        page.fill(f"#af-{key}", FILLS[kind][key])
    page.wait_for_function(
        "document.querySelector('#author-script').textContent.startsWith('#!')"
    )


def _script(page) -> str:
    return page.locator("#author-script").text_content()


def _selection(page) -> str:
    return page.locator("#author-selection").text_content()


def test_page_loads_with_five_kinds_and_catalog(page, site_url) -> None:
    _open(page, site_url)
    assert page.locator("h1").inner_text() == "Author a policy"
    assert page.locator("input[name='author-kind']").count() == 5
    assert page.locator("#author-fields .field").count() == 4
    assert page.locator("#author-catalog-list .amember").count() > 10
    assert "localStorage draft" in page.locator(".saved-note").inner_text()
    assert page.locator("#author-download").is_disabled()
    screenshot(page, "author_interview")
    assert_clean(page)


@pytest.mark.parametrize("kind", sorted(FILLS))
def test_each_kind_generates_selection_and_script(page, site_url, kind) -> None:
    _open(page, site_url)
    _fill(page, kind)
    policy_id = KIND_IDS[kind]
    selection = _selection(page)
    assert f"id: {policy_id}" in selection
    assert f"path: .agents/policies/{policy_id}" in selection
    assert re.search(r"sha256: [0-9a-f]{64}", selection)
    script = _script(page)
    assert script.startswith("#!/bin/sh")
    assert "set -eu" in script
    assert 'chock check --repo "$FOLDER" --only validate,evals' in script
    assert 'chock install --selection "$FOLDER/chock.selection.yaml"' in script
    assert f"--trust-local {policy_id}=" in script
    assert re.fullmatch(r"[0-9a-f]{64}", page.locator("#author-sha").inner_text())
    assert page.locator("#author-download").is_enabled()
    assert_clean(page)


def test_validation_blocks_contradictory_answers(page, site_url) -> None:
    _open(page, site_url)
    page.evaluate("localStorage.removeItem('chock.author.draft.v1')")
    page.fill("#author-name", "block secrets")
    page.fill("#af-stop", "BEGIN PRIVATE KEY")
    page.fill("#af-message", "remove it")
    page.fill("#af-refuse_example", "key = BEGIN PRIVATE KEY")
    # The passing example contains the stopped text: a contradiction.
    page.fill("#af-pass_example", "still BEGIN PRIVATE KEY here")
    errors = page.locator("#author-error-list")
    errors.wait_for()
    assert "must not contain" in errors.inner_text()
    assert page.locator("#author-download").is_disabled()
    assert (
        page.locator("#author-selection").text_content()
        == page.locator("#author-script").text_content()
    )
    assert_clean(page)


def test_advanced_edit_wins_and_restore_regenerates(page, site_url) -> None:
    _open(page, site_url)
    _fill(page, "rule")
    area = page.locator(".afile-text").first
    before = area.input_value()
    area.fill(before + "\n# a reviewer note\n")
    assert page.locator(".afile-edited").first.is_visible()
    page.wait_for_timeout(500)
    assert "# a reviewer note" in _script(page)
    screenshot(page, "author_advanced")
    page.locator(".areset").first.click()
    page.wait_for_timeout(500)
    assert area.input_value() == before
    assert page.locator(".afile-edited").first.is_hidden()
    assert_clean(page)


def test_draft_persists_across_reload_and_clears(page, site_url) -> None:
    _open(page, site_url)
    _fill(page, "guard")
    page.wait_for_timeout(600)  # the draft save is debounced 300 ms
    page.reload()
    page.wait_for_selector("#author-fields .field")
    assert page.locator("#author-name").input_value() == FILLS["guard"]["name"]
    assert page.locator("#af-stop").input_value() == FILLS["guard"]["stop"]
    page.get_by_role("button", name="Clear draft").click()
    assert page.locator("#author-clear-done").is_visible()
    page.reload()
    page.wait_for_selector("#author-fields .field")
    assert page.locator("#author-name").input_value() == ""
    assert_clean(page)


def test_catalog_picks_join_the_selection_and_share(page, site_url) -> None:
    _open(page, site_url)
    _fill(page, "rule")
    first = page.locator("#author-catalog-list .amember input").first
    policy_id = first.get_attribute("value")
    first.check()
    page.wait_for_timeout(600)
    selection = _selection(page)
    assert f"id: {policy_id}" in selection
    assert "from: catalog" in selection
    assert "catalog:\n  source:" in selection
    page.locator("#author-share").click()
    share = page.locator("#author-share-url").input_value()
    assert f"#client=claude-code&p={policy_id}" in share
    other = page.context.new_page()
    collect(other, site_url)
    other.goto(share)
    other.wait_for_selector("#author-fields .field")
    assert other.locator(
        f"#author-catalog-list input[value='{policy_id}']"
    ).is_checked()
    assert_clean(page)
    assert_clean(other)


def test_unknown_catalog_ids_in_share_link_get_a_notice(page, site_url) -> None:
    _open(page, site_url, "#client=codex&p=no-such-policy")
    notice = page.locator("#link-notice").inner_text()
    assert "no-such-policy" in notice
    assert page.locator("input[name='client'][value='codex']").is_checked()
    assert_clean(page)


def test_schema_2_fragment_restores_catalog_picks(page, site_url) -> None:
    page.goto(site_url + "/coding/builder/")
    page.get_by_role("button", name="Skip to the full builder").click()
    page.wait_for_selector("#builder-status:not(:empty)")
    page.check("input[value='block-no-verify']")
    fragment = page.evaluate("location.hash")
    assert fragment.startswith("#s=")
    # A hash-only goto does not reload: open each fragment on a fresh page.
    first = page.context.new_page()
    collect(first, site_url)
    _open(first, site_url, fragment)
    assert first.locator("input[value='block-no-verify']").is_checked()
    second = page.context.new_page()
    collect(second, site_url)
    _open(second, site_url, "#s=not-base64!")
    assert "could not be read" in second.locator("#link-notice").inner_text()
    assert_clean(first)
    assert_clean(second)


def test_builder_link_carries_the_picks(page, site_url) -> None:
    page.goto(site_url + "/coding/builder/")
    page.get_by_role("button", name="Skip to the full builder").click()
    page.wait_for_selector("#builder-status:not(:empty)")
    page.check("input[value='block-no-verify']")
    link = page.locator("#author-link")
    assert link.get_attribute("href").endswith("#client=claude-code&p=block-no-verify")
    link.click()
    page.wait_for_selector("#author-fields .field")
    assert page.locator("input[value='block-no-verify']").is_checked()
    assert_clean(page)


def test_download_names_the_setup_script(page, site_url, tmp_path) -> None:
    _open(page, site_url)
    _fill(page, "content_regex")
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    page.locator(".output-box").last.screenshot(
        path=str(SCREENSHOTS / "author_download.png")
    )
    with page.expect_download() as info:
        page.get_by_role("button", name="Download chock-setup.sh").click()
    download = info.value
    assert download.suggested_filename == "chock-setup.sh"
    target = tmp_path / "chock-setup.sh"
    download.save_as(str(target))
    assert target.read_text(encoding="utf-8").startswith("#!/bin/sh")
    assert_clean(page)


def test_copy_button_uses_the_clipboard(page, site_url) -> None:
    _open(page, site_url)
    _fill(page, "rule")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.get_by_role("button", name="Copy script").click()
    page.get_by_role("button", name="Copied").wait_for()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied.startswith("#!/bin/sh")
    assert_clean(page)


def test_delimiter_collision_still_round_trips(page, site_url, tmp_path) -> None:
    _open(page, site_url)
    page.evaluate("localStorage.removeItem('chock.author.draft.v1')")
    page.check("input[name='author-kind'][value='rule']")
    page.fill("#author-name", "delimiter trap")
    page.fill("#af-stop", "CHOCK_FILE_1 in a sentence")
    page.fill("#af-message", "mentions CHOCK_FILE_1 too")
    page.fill("#af-refuse_example", "do the CHOCK_FILE_1 thing")
    page.fill("#af-pass_example", "an ordinary change")
    page.wait_for_function(
        "document.querySelector('#author-script').textContent.startsWith('#!')"
    )
    script = _script(page)
    # The first-choice delimiter occurs in the content, so the generator moved on.
    assert "CHOCK_FILE_1_X" in script
    result = _run_script(script, tmp_path, "claude-code\n./my-guardrails\nbuild\n")
    assert result.returncode == 0, result.stdout + result.stderr
    # Every generated file lands byte for byte.
    boxes = page.locator(".afile")
    for i in range(boxes.count()):
        path = boxes.nth(i).locator("code").inner_text()
        text = boxes.nth(i).locator(".afile-text").input_value()
        written = (
            tmp_path
            / "my-guardrails"
            / ".agents"
            / "policies"
            / "my-delimiter-trap"
            / path
        ).read_text(encoding="utf-8")
        expected = text if text.endswith("\n") else text + "\n"
        assert written == expected, path
    assert_clean(page)


def test_mobile_layout(page, site_url) -> None:
    page.set_viewport_size(MOBILE)
    _open(page, site_url)
    _fill(page, "guard")
    screenshot(page, "author_mobile")
    assert page.locator("#author-script").is_visible()
    assert_clean(page)


def _sh() -> str:
    shell = shutil.which("sh") or shutil.which("bash")
    assert shell, "no POSIX shell on PATH"
    return shell


def _chock_bin(tmp_path: Path) -> Path:
    """A `chock` on PATH that runs the pinned engine under this interpreter."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "chock"
    shim.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" -m chock "$@"\n', encoding="utf-8"
    )
    shim.chmod(0o755)
    return bin_dir


def _run_script(
    script_text: str, work: Path, answers: str
) -> subprocess.CompletedProcess:
    bin_dir = _chock_bin(work)
    home = work / "home"
    home.mkdir(exist_ok=True)
    script = work / "setup.sh"
    script.write_text(script_text, encoding="utf-8", newline="\n")
    # Redirect every home lookup so the build lands under tmp_path, not ~.
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(home),
        "USERPROFILE": str(home),
        "HOMEDRIVE": home.drive,
        "HOMEPATH": str(home)[len(home.drive) :],
    }
    # Bytes input: text mode would translate \n to \r\n and `read` keeps the \r.
    raw = subprocess.run(
        [_sh(), str(script)],
        input=answers.encode(),
        capture_output=True,
        cwd=work,
        env=env,
        timeout=300,
        check=False,
    )
    return subprocess.CompletedProcess(
        raw.args,
        raw.returncode,
        raw.stdout.decode("utf-8", "replace"),
        raw.stderr.decode("utf-8", "replace"),
    )


@pytest.mark.parametrize("kind", sorted(FILLS))
def test_generated_script_runs_end_to_end(page, site_url, tmp_path, kind) -> None:
    _open(page, site_url)
    _fill(page, kind)
    result = _run_script(
        _script(page), tmp_path / kind, "claude-code\n./my-guardrails\nbuild\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    root = tmp_path / kind / "my-guardrails"
    assert (root / "chock.selection.yaml").is_file()
    assert (root / ".agents" / "policies" / KIND_IDS[kind] / "manifest.yaml").is_file()
    assert "custom, not reviewed" in result.stdout
    assert_clean(page)


def test_install_mode_says_untested_and_skips_apply(page, site_url, tmp_path) -> None:
    _open(page, site_url)
    _fill(page, "rule")
    result = _run_script(_script(page), tmp_path, "cursor\n./my-guardrails\ninstall\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "not been witnessed applying to cursor" in result.stdout
    assert "custom, not reviewed" in result.stdout
    assert_clean(page)


def test_script_validates_inputs_and_never_evaluates_the_folder(
    page, site_url, tmp_path
) -> None:
    _open(page, site_url)
    _fill(page, "rule")
    script = _script(page)
    bad_agent = _run_script(script, tmp_path / "a", "zsh\n./my-guardrails\nbuild\n")
    assert bad_agent.returncode != 0
    assert "Unknown agent" in bad_agent.stderr
    bad_mode = _run_script(
        script, tmp_path / "b", "claude-code\n./my-guardrails\nyolo\n"
    )
    assert bad_mode.returncode != 0
    # The folder is quoted, never evaluated: the command substitution cannot run.
    injected = _run_script(
        script, tmp_path / "c", "claude-code\nsub$(touch INJECTED)\nbuild\n"
    )
    assert not (tmp_path / "c" / "INJECTED").exists()
    assert injected.returncode == 0
    assert_clean(page)
