"""R-4: the Git repositories section in a browser — quiz, commands, download, share links."""

import json
import shlex
from pathlib import Path
from types import SimpleNamespace

from conftest import assert_clean, collect, screenshot

from sitegen import repodata

BUILDER = "/repos/builder/"
MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 900}
HEADER = "#!/bin/sh\nset -eu\n"


def _site(page, site_url: str) -> dict:
    return json.loads(page.request.get(site_url + "/data/site.json").text())


def _start(page, site_url: str, fragment: str = "") -> None:
    page.goto(site_url + BUILDER + fragment)
    page.wait_for_selector("#quiz-title:not(:empty)")


def _next(page) -> None:
    page.locator("#quiz-next").click()


def _answer(page, host: str = "GitHub", strictness: str = "Everything") -> None:
    page.get_by_role("radio", name=host).check()
    _next(page)
    page.get_by_role("checkbox", name="Skipped checks").check()
    _next(page)
    page.get_by_role("radio", name=strictness).check()
    _next(page)
    page.wait_for_selector(".quiz-pick")


def _ids(page) -> list[str]:
    return page.locator(".quiz-pick").evaluate_all(
        "els => els.map(e => e.dataset.policyId)"
    )


def _command(page) -> str:
    return page.locator("[data-quiz-command]").text_content()


def _expected(site: dict, ids: list[str], ci: bool) -> str:
    by_id = {p["id"]: p for p in site["policies"]}
    commands = site["repos"]["commands"]
    lines = [commands["init"]]
    for pid in sorted(ids):
        lines.append(
            repodata.shell_line(
                commands["add"],
                {
                    "id": pid,
                    "ref": site["catalog"]["ref"],
                    "sha256": by_id[pid]["sha256"],
                },
            )
        )
    lines += [commands["sync_ci"] if ci else commands["sync"], commands["review"]]
    return "\n".join(lines)


def test_first_question_is_where_the_code_lives(page, site_url) -> None:
    _start(page, site_url)
    assert page.locator("#quiz-title").text_content() == "Where does your code live?"
    names = page.locator(".quiz-opt-label").all_text_contents()
    assert names == ["GitHub", "GitLab", "Other git host"]
    assert page.locator("#quiz-skip").count() == 0
    assert_clean(page)


def test_other_hosts_continue_and_say_ci_is_github_only(page, site_url) -> None:
    _start(page, site_url)
    page.get_by_role("radio", name="GitLab").check()
    assert "GitHub Actions only" in page.locator(".quiz-note").text_content()
    assert page.locator("#quiz-next").is_visible()
    _answer(page, host="GitLab")
    assert not page.get_by_role(
        "checkbox", name="Add the GitHub Actions gate"
    ).is_checked()
    assert _command(page).splitlines()[-2] == "chock sync --repo ."


def test_github_adds_ci_and_the_command_matches_the_build(page, site_url) -> None:
    site = _site(page, site_url)
    _start(page, site_url)
    _answer(page)
    ids = _ids(page)
    assert ids
    assert _command(page) == _expected(site, ids, True)
    assert _command(page).splitlines()[-2] == "chock sync --repo . --ci"
    page.get_by_role("checkbox", name="Add the GitHub Actions gate").uncheck()
    assert _command(page) == _expected(site, ids, False)


def test_strictness_reads_the_repo_words(page, site_url) -> None:
    site = _site(page, site_url)
    tier = site["repos"]["tier_of"]
    git = next(p for p in site["presets"] if p["id"] == "git-hygiene")["members"]
    test = next(p for p in site["presets"] if p["id"] == "test-integrity")["members"]
    pool = list(dict.fromkeys(git + test))
    for choice, allowed in (
        ("Only hard stops", {"commit"}),
        ("Stops and warnings", {"commit", "agent"}),
        ("Everything", {"commit", "agent", "advise"}),
    ):
        _start(page, site_url)
        _answer(page, strictness=choice)
        assert sorted(_ids(page)) == sorted(i for i in pool if tier[i] in allowed)
        chips = page.locator(".quiz-pick .label").all_text_contents()
        assert all(
            c.strip().endswith(("At commit", "In agent", "Advisory")) for c in chips
        )


def test_remove_updates_the_commands(page, site_url) -> None:
    site = _site(page, site_url)
    _start(page, site_url)
    _answer(page)
    first = _ids(page)[0]
    page.get_by_role("button", name=f"Remove {first}").click()
    assert first not in _ids(page)
    assert _command(page) == _expected(site, _ids(page), True)


def test_download_is_the_copied_block_plus_two_header_lines(
    page, site_url, tmp_path: Path
) -> None:
    _start(page, site_url)
    _answer(page)
    block = _command(page)
    with page.expect_download() as info:
        page.get_by_role("button", name="Download chock-setup.sh").click()
    download = info.value
    assert download.suggested_filename == "chock-setup.sh"
    path = tmp_path / "chock-setup.sh"
    download.save_as(path)
    assert path.read_text(encoding="utf-8") == HEADER + block + "\n"


def test_share_link_round_trips(page, site_url) -> None:
    _start(page, site_url)
    _answer(page)
    ids = sorted(_ids(page))
    link = page.locator("#quiz-share-url").input_value()
    assert link.endswith("#p=" + ",".join(ids) + "&host=github&ci=1")
    _start(page, site_url, "#p=" + ",".join(ids))
    assert sorted(_ids(page)) == ids
    assert "came from a share link" in page.locator("#link-notice").text_content()


def test_share_link_carries_host_and_ci(page, site_url) -> None:
    site = _site(page, site_url)
    _start(page, site_url, "#p=block-no-verify&host=gitlab&ci=1")
    assert _command(page) == _expected(site, ["block-no-verify"], True)
    assert (
        page.locator("#quiz-share-url")
        .input_value()
        .endswith("#p=block-no-verify&host=gitlab&ci=1")
    )
    _start(page, site_url, "#p=block-no-verify&host=gitlab&ci=0")
    assert _command(page) == _expected(site, ["block-no-verify"], False)


def test_unknown_ids_are_dropped_and_named(page, site_url) -> None:
    _start(page, site_url, "#p=block-no-verify,../x,nope")
    assert _ids(page) == ["block-no-verify"]
    note = page.locator("#link-notice").text_content()
    assert "Not available here: ../x, nope" in note
    text = _command(page)
    assert "../x" not in text and "nope" not in text


def test_a_link_cannot_change_the_ref_or_a_sha256(page, site_url) -> None:
    site = _site(page, site_url)
    by_id = {p["id"]: p for p in site["policies"]}
    fake = "f" * 40
    _start(page, site_url, f"#p=block-no-verify,{fake},sha256={'e' * 64}&ref={fake}")
    text = _command(page)
    assert text == _expected(site, ["block-no-verify"], True)
    assert fake not in text and "e" * 64 not in text
    assert by_id["block-no-verify"]["sha256"] in text
    assert f"--ref {site['catalog']['ref']} " in text


def test_a_link_with_only_unknown_ids_shows_the_quiz(page, site_url) -> None:
    _start(page, site_url, "#p=nope")
    assert page.locator("#quiz-title").text_content() == "Where does your code live?"
    assert "Not available here: nope" in page.locator("#link-notice").text_content()


def test_whole_quiz_works_by_keyboard(page, site_url) -> None:
    _start(page, site_url)
    page.locator("input[name='quiz-host'][value='github']").focus()
    page.locator("#quiz-next").focus()
    page.keyboard.press("Enter")
    page.wait_for_selector("input[name='quiz-worries']")
    page.locator("input[name='quiz-worries'][value='secrets']").focus()
    page.keyboard.press("Space")
    page.locator("#quiz-next").focus()
    page.keyboard.press("Enter")
    page.locator("#quiz-next").focus()
    page.keyboard.press("Enter")
    page.wait_for_selector(".quiz-pick")
    assert _ids(page)


def test_pages_fit_a_phone_and_screenshots(browser, site_url) -> None:
    for size, viewport in (("desktop", DESKTOP), ("mobile", MOBILE)):
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            collect(page, site_url)
            page.goto(site_url + "/repos/")
            screenshot(page, f"repos-home-{size}")
            assert not page.evaluate(
                "document.scrollingElement.scrollWidth > window.innerWidth"
            )
            _start(page, site_url)
            screenshot(page, f"repos-quiz-q1-{size}")
            _answer(page)
            screenshot(page, f"repos-result-{size}")
            assert not page.evaluate(
                "document.scrollingElement.scrollWidth > window.innerWidth"
            )
            page.goto(site_url + "/coding/policies/protect-main-branch/")
            screenshot(page, f"policy-tier-tile-{size}")
            assert not page.evaluate(
                "document.scrollingElement.scrollWidth > window.innerWidth"
            )
            page.goto(site_url + "/")
            assert page.locator(".track-card").count() == 3
            assert not page.evaluate(
                "document.scrollingElement.scrollWidth > window.innerWidth"
            )
            assert_clean(page)
        finally:
            context.close()


def test_policy_tile_and_nav(page, site_url) -> None:
    page.goto(site_url + "/coding/policies/protect-main-branch/")
    assert page.locator("#repo-tier .fact-value").text_content() == "At commit"
    assert page.locator('#nav-links a[href="/repos/"]').count() == 1
    page.goto(site_url + "/repos/")
    assert (
        page.locator("h1").text_content() == "Guardrails that live in your repository"
    )
    assert_clean(page)


# --- SITE-1: the browser quotes the way Python does ----------------------------------------

# Values a catalog could carry: the review's injection, quotes, spaces, globs, unicode, empty.
TRICKY = [
    "safe;echo PWNED > pwned",
    "a'b",
    "it's",
    "two words",
    "$(id)",
    "`id`",
    "a&&b",
    "*.py",
    "~user",
    "naïve",
    "",
    "--ref",
    "{id}",
    "a\nb",
    "back\\slash",
    '"quoted"',
]
IMPORT = "const m = await import('/js/repos.js');"


def _js(page, body: str, arg):
    return page.evaluate(f"async (arg) => {{ {IMPORT} {body} }}", arg)


def test_shell_arg_twins_agree_on_the_sites_values_and_on_hostile_ones(
    page, site_url
) -> None:
    site = _site(page, site_url)
    _start(page, site_url)
    values = (
        [p["id"] for p in site["policies"]]
        + [p["sha256"] for p in site["policies"]]
        + [site["catalog"]["ref"], *TRICKY]
    )
    assert len(values) > len(TRICKY) + 1
    quoted = _js(page, "return arg.map(m.shellArg);", values)
    assert quoted == [shlex.quote(v) for v in values]
    assert_clean(page)


def test_command_lines_twins_agree_on_the_sites_data(page, site_url) -> None:
    site = _site(page, site_url)
    _start(page, site_url)
    ids = [p["id"] for p in site["policies"]]
    picks = [SimpleNamespace(id=p["id"], sha256=p["sha256"]) for p in site["policies"]]
    for ci in (False, True):
        lines = _js(
            page,
            "const site = await (await fetch('/data/site.json')).json();"
            " return m.commandLines(site, arg.ids, arg.ci);",
            {"ids": ids, "ci": ci},
        )
        assert lines == repodata.command_lines(
            site["repos"]["commands"], picks, site["catalog"]["ref"], ci
        )


def test_command_lines_twins_agree_on_a_hostile_catalog(page, site_url) -> None:
    """A registry the build would refuse: both twins still emit one argument per value."""
    site = _site(page, site_url)
    _start(page, site_url)
    hostile = {
        "catalog": {"ref": "r$(id)"},
        "repos": {"commands": site["repos"]["commands"]},
        "policies": [
            {"id": value, "sha256": f"{value}'s hash"} for value in TRICKY if value
        ],
    }
    ids = [p["id"] for p in hostile["policies"]]
    lines = _js(
        page,
        "return m.commandLines(arg.site, arg.ids, false);",
        {"site": hostile, "ids": ids},
    )
    picks = [
        SimpleNamespace(id=p["id"], sha256=p["sha256"]) for p in hostile["policies"]
    ]
    assert lines == repodata.command_lines(
        hostile["repos"]["commands"], picks, "r$(id)", False
    )
    for line, pid in zip(lines[1:-2], sorted(ids), strict=True):
        assert shlex.split(line)[:5] == ["chock", "add", pid, "--ref", "r$(id)"]
