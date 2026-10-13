"""The author page (BV-S2): interview, files, catalog mixing, drafts, setup script."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from chock.lock import compute_pack_hash
from conftest import SCREENSHOTS, assert_clean, collect, screenshot

from sitegen import clientdata, engine
from tests.fixtures.untested import CLIENT

AUTHOR = "/coding/author/"
ROOT = Path(__file__).resolve().parents[2]
# The picker's order: witness.yaml's rows, then the engine clients without one (S-ALL).
WITNESS_ORDER = list(
    clientdata.load_witness(ROOT / "data", engine.client_ids())["clients"]
)
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
    _assert_engine_hash(page, root / ".agents" / "policies" / KIND_IDS[kind])
    assert_clean(page)


@pytest.mark.parametrize("agent", WITNESS_ORDER)
def test_generated_script_builds_for_every_agent(
    page, site_url, tmp_path, agent
) -> None:
    """The agent typed into the script lands in the selection, and chock install accepts it."""
    _open(page, site_url)
    _fill(page, "guard")
    result = _run_script(_script(page), tmp_path, f"{agent}\n./my-guardrails\nbuild\n")
    assert result.returncode == 0, result.stdout + result.stderr
    selection = tmp_path / "my-guardrails" / "chock.selection.yaml"
    assert yaml.safe_load(selection.read_text(encoding="utf-8"))["client"] == agent
    assert engine.load_selection(str(selection))["client"] == agent
    assert "custom, not reviewed" in result.stdout
    assert_clean(page)


def _assert_engine_hash(page, policy_dir: Path) -> None:
    """The page's JS pack hash equals the pinned engine's hash of the written files."""
    js_hash = re.search(r"sha256: ([0-9a-f]{64})", _selection(page)).group(1)
    assert compute_pack_hash(policy_dir) == js_hash


def test_pack_hash_matches_engine_on_nested_executable_utf8_pack(
    page, site_url, tmp_path
) -> None:
    _open(page, site_url)
    page.evaluate("localStorage.removeItem('chock.author.draft.v1')")
    page.check("input[name='author-kind'][value='guard']")
    page.fill("#author-name", "no destroy")
    page.fill("#af-stop", "terraform destroy")
    # Non-ASCII UTF-8: accents, guillemets, an em dash and a 4-byte emoji.
    page.fill("#af-message", "Ne lancez pas « terraform destroy » — ça casse tout ✋🙂")
    page.fill("#af-refuse_example", "terraform destroy -auto-approve")
    page.fill("#af-pass_example", "terraform plan")
    page.wait_for_function(
        "document.querySelector('#author-script').textContent.startsWith('#!')"
    )
    # An advanced edit adds a non-ASCII last line, with no final newline, to the
    # executable implementation; the heredoc writes that newline.
    impl = page.locator(".afile").filter(
        has=page.locator("code", has_text="implementations/")
    )
    area = impl.locator(".afile-text")
    area.fill(area.input_value() + "# Résumé: naïve façade, 日本語 ✓")
    page.wait_for_function(
        "document.querySelector('#author-script').textContent.includes('日本語')"
    )
    result = _run_script(
        _script(page), tmp_path, "claude-code\n./my-guardrails\nbuild\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    policy_dir = tmp_path / "my-guardrails" / ".agents" / "policies" / "my-no-destroy"
    written = sorted(
        p.relative_to(policy_dir).as_posix()
        for p in policy_dir.rglob("*")
        if p.is_file()
    )
    assert written == [
        "evals/suite.yaml",
        "implementations/my-no-destroy.py",
        "manifest.yaml",
    ]
    executable = policy_dir / "implementations" / "my-no-destroy.py"
    assert os.access(executable, os.X_OK)
    assert "日本語".encode() in executable.read_bytes()
    assert any("✋🙂".encode() in p.read_bytes() for p in policy_dir.rglob("*.*"))
    _assert_engine_hash(page, policy_dir)
    assert_clean(page)


def test_install_mode_says_untested_and_skips_apply(
    page, untested_url, tmp_path
) -> None:
    """On the test-only site where CLIENT is untested (tests/fixtures)."""
    _open(page, untested_url)
    _fill(page, "rule")
    answers = f"{CLIENT}\n./my-guardrails\ninstall\n"
    result = _run_script(_script(page), tmp_path, answers)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"not been witnessed applying to {CLIENT}" in result.stdout
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


@pytest.mark.parametrize("fragment", ["#client=constructor", "#client=__proto__&p=x"])
def test_prototype_client_names_do_not_break_the_page(page, site_url, fragment) -> None:
    _open(page, site_url, fragment)
    assert page.locator("input[name='client']:checked").count() == 1
    assert page.locator("input[name='client'][value='constructor']").count() == 0
    assert_clean(page)


def test_prototype_names_in_a_draft_do_not_break_the_page(page, site_url) -> None:
    _open(page, site_url)
    page.evaluate(
        "localStorage.setItem('chock.author.draft.v1', JSON.stringify("
        "{kind: 'constructor', client: '__proto__', name: 'x'}))"
    )
    page.reload()
    page.wait_for_selector("#author-fields .field")
    assert page.locator("input[name='author-kind']:checked").count() == 1
    assert page.locator("input[name='client']:checked").count() == 1
    assert_clean(page)


def test_link_notice_echoes_only_short_catalog_shaped_ids(page, site_url) -> None:
    long_id = "a" * 65
    ids = [f"no-such-{i}" for i in range(7)] + ["Evil<b>Text", long_id]
    _open(page, site_url, "#client=codex&p=" + ",".join(ids))
    notice = page.locator("#link-notice").inner_text()
    assert "no-such-0" in notice and "no-such-4" in notice
    assert "no-such-5" not in notice
    assert "Evil" not in notice and long_id not in notice
    assert "4 ids not shown" in notice
    assert_clean(page)


@pytest.mark.parametrize("answer", ["true", "null", "0x1f", "- x", "foo:"])
def test_yaml_values_that_look_typed_stay_strings(page, site_url, answer) -> None:
    _open(page, site_url)
    page.evaluate("localStorage.removeItem('chock.author.draft.v1')")
    page.check("input[name='author-kind'][value='guard']")
    page.fill("#author-name", "typed values")
    page.fill("#af-stop", "terraform destroy")
    page.fill("#af-message", "Run terraform yourself.")
    page.fill("#af-refuse_example", "terraform destroy -auto-approve")
    page.fill("#af-pass_example", answer)
    page.wait_for_function(
        "document.querySelector('#author-script').textContent.startsWith('#!')"
    )
    boxes = page.locator(".afile")
    suite = next(
        boxes.nth(i).locator(".afile-text").input_value()
        for i in range(boxes.count())
        if boxes.nth(i).locator("code").inner_text() == "evals/suite.yaml"
    )
    cases = yaml.safe_load(suite)["suite"]["cases"]
    commands = [case["execute"]["command"] for case in cases if "execute" in case]
    assert answer in commands
    assert all(isinstance(command, str) for command in commands)
    assert_clean(page)


@pytest.mark.parametrize("answer", ["a\u001bb", "bell\u0007", "zero\u200bwidth"])
def test_control_characters_reach_yaml_double_quoted(page, site_url, answer) -> None:
    """A single-quoted scalar cannot carry them; the script stays refused meanwhile."""
    _open(page, site_url)
    page.evaluate("localStorage.removeItem('chock.author.draft.v1')")
    page.check("input[name='author-kind'][value='guard']")
    page.fill("#author-name", "control chars")
    page.fill("#af-stop", "terraform destroy")
    page.fill("#af-message", "Run terraform yourself.")
    page.fill("#af-refuse_example", "terraform destroy -auto-approve")
    page.fill("#af-pass_example", answer)
    suite_box = page.locator(".afile").filter(
        has=page.locator("code", has_text="evals/suite.yaml")
    )
    text = suite_box.locator(".afile-text")
    page.wait_for_function(
        "el => el.value.includes('expect: allow') && !el.value.includes(\"'terraform plan'\")",
        arg=text.element_handle(),
    )
    suite = text.input_value()
    assert all(ch not in suite for ch in "\u001b\u0007\u200b")
    cases = yaml.safe_load(suite)["suite"]["cases"]
    commands = [case["execute"]["command"] for case in cases if "execute" in case]
    assert answer in commands
    assert not page.locator("#author-script").text_content().startswith("#!")
    assert_clean(page)
