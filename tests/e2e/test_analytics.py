"""Site events (plan AN-1): each call site sends exactly its event, and nothing is sent when it must not be."""

import json

import pytest
from conftest import assert_clean
from test_author import _fill
from test_author import _open as _open_author

BUILDER = "/coding/builder/"
REPORT = "/report/"
POLICY = "block-no-verify"
# How long a test waits for a beacon that must not come.
QUIET_MS = 600


def _record(page, status: int = 204) -> list[dict]:
    """Intercept /api/event; every body sent, parsed, in order."""
    sent: list[dict] = []

    def handle(route) -> None:
        sent.append(json.loads(route.request.post_data))
        route.fulfill(status=status, body="")

    page.route("**/api/event", handle)
    return sent


def _wait_for(page, sent: list[dict], count: int) -> list[dict]:
    """The bodies once `count` have arrived (or after 3 s), then a quiet spell for extras."""
    for _ in range(60):
        if len(sent) >= count:
            break
        page.wait_for_timeout(50)
    page.wait_for_timeout(200)
    return sent


def _default_agent(page, site_url: str) -> str:
    site = json.loads(page.request.get(site_url + "/data/site.json").text())
    return site["builder_clients"]["default"]


def _open_builder(page, site_url: str, fragment: str = "#preset=git-hygiene") -> None:
    page.goto(site_url + BUILDER + "?track=1" + fragment)
    page.wait_for_selector(".sel-item")


def test_builder_copy_share_download_and_preset(page, site_url) -> None:
    agent = _default_agent(page, site_url)
    sent = _record(page)
    _open_builder(page, site_url)
    assert _wait_for(page, sent, 1) == []
    page.locator("#copy-command").click()
    assert _wait_for(page, sent, 1) == [
        {"name": "install-copied", "props": {"agent": agent}}
    ]
    page.locator("#tab-share").click()
    page.locator("#copy-share").click()
    assert _wait_for(page, sent, 2)[1] == {"name": "share-copied", "props": {}}
    page.locator("#tab-file").click()
    with page.expect_download():
        page.locator("#download-file").click()
    assert _wait_for(page, sent, 3)[2] == {"name": "selection-downloaded", "props": {}}
    page.on("dialog", lambda dialog: dialog.accept())
    page.select_option("#builder-start", "secrets")
    assert _wait_for(page, sent, 4)[3] == {
        "name": "preset-picked",
        "props": {"preset": "secrets"},
    }
    assert len(sent) == 4
    assert_clean(page)


def test_builder_install_copy_names_the_picked_agent(page, site_url) -> None:
    sent = _record(page)
    _open_builder(page, site_url, "#client=codex&p=block-no-verify")
    page.locator("#copy-command").click()
    assert _wait_for(page, sent, 1) == [
        {"name": "install-copied", "props": {"agent": "codex"}}
    ]
    assert_clean(page)


def test_quiz_finished_and_its_copy(page, site_url) -> None:
    agent = _default_agent(page, site_url)
    sent = _record(page)
    page.goto(site_url + BUILDER + "?track=1")
    page.wait_for_selector("#quiz-title:not(:empty)")
    for _ in range(10):
        if page.locator(".quiz-command").count():
            break
        if page.locator("#quiz-next").is_disabled():
            page.locator(".quiz-opt input").first.check()
        page.locator("#quiz-next").click()
    assert _wait_for(page, sent, 1) == [{"name": "quiz-finished", "props": {}}]
    page.locator(".quiz-command button").click()
    assert _wait_for(page, sent, 2)[1] == {
        "name": "install-copied",
        "props": {"agent": agent},
    }
    assert len(sent) == 2
    assert_clean(page)


@pytest.mark.parametrize(
    ("kind", "sent_kind"), [("rule", "rule"), ("content_regex", "content-regex")]
)
def test_author_script_download(page, site_url, kind, sent_kind) -> None:
    agent = _default_agent(page, site_url)
    sent = _record(page)
    _open_author(page, site_url, "?track=1")
    _fill(page, kind)
    with page.expect_download():
        page.locator("#author-download").click()
    assert _wait_for(page, sent, 1) == [
        {
            "name": "author-script-downloaded",
            "props": {"kind": sent_kind, "agent": agent},
        }
    ]
    assert_clean(page)


@pytest.mark.parametrize(
    "form", ["policy-wrong", "install", "site-bug", "policy-proposal"]
)
def test_report_form_opened(page, site_url, form) -> None:
    sent = _record(page)
    page.goto(site_url + REPORT + "?track=1&policy=x%3Cscript%3E&agent=evil")
    # Stay on the page: the test counts the click, it does not open GitHub.
    page.evaluate("document.addEventListener('click', (e) => e.preventDefault())")
    page.locator(f'a[data-report-kind="{form}"]').click()
    assert _wait_for(page, sent, 1) == [
        {"name": "report-form-opened", "props": {"form": form}}
    ]
    assert_clean(page)


def test_policy_page_build_for_agent(page, site_url) -> None:
    sent = _record(page)
    page.goto(f"{site_url}/coding/policies/{POLICY}/?track=1")
    # Stay on the page, so the intercepted beacon never races the navigation.
    page.evaluate("document.addEventListener('click', (e) => e.preventDefault())")
    page.locator(".agent-labels a[data-client='codex']").click()
    assert _wait_for(page, sent, 1) == [
        {"name": "policy-build-clicked", "props": {"policy": POLICY, "agent": "codex"}}
    ]
    assert_clean(page)


def _copy_command_sends(
    page, site_url, query: str, fragment: str = "#preset=git-hygiene"
) -> list[dict]:
    sent = _record(page)
    page.goto(site_url + BUILDER + query + fragment)
    page.wait_for_selector(".sel-item")
    page.locator("#copy-command").click()
    page.locator("#tab-share").click()
    page.locator("#copy-share").click()
    page.wait_for_timeout(QUIET_MS)
    return sent


def test_nothing_is_sent_on_localhost_by_default(page, site_url) -> None:
    assert "127.0.0.1" in site_url
    assert _copy_command_sends(page, site_url, "") == []
    assert _copy_command_sends(page, site_url, "?track=0") == []
    assert_clean(page)


@pytest.mark.parametrize(
    "script",
    [
        "Object.defineProperty(Navigator.prototype, 'globalPrivacyControl', {get: () => true})",
        "Object.defineProperty(Navigator.prototype, 'doNotTrack', {get: () => '1'})",
    ],
)
def test_nothing_is_sent_with_gpc_or_dnt(page, site_url, script) -> None:
    page.add_init_script(script)
    assert _copy_command_sends(page, site_url, "?track=1") == []
    assert_clean(page)


def test_hostile_hash_sends_only_known_values(page, site_url) -> None:
    sent = _record(page)
    hostile = "#client=codex&p=block-no-verify,%22%3E%3Cimg%20src=x%3E%3Cscript%3E"
    page.goto(site_url + BUILDER + "?track=1" + hostile)
    page.wait_for_selector(".sel-item")
    page.wait_for_timeout(QUIET_MS)
    assert sent == []
    page.locator("#copy-command").click()
    bodies = _wait_for(page, sent, 1)
    assert bodies == [{"name": "install-copied", "props": {"agent": "codex"}}]
    raw = json.dumps(bodies)
    for leak in ("script", "img", "block-no-verify", "#", "track", "127.0.0.1"):
        assert leak not in raw, leak


@pytest.mark.parametrize("status", [500, 404])
def test_ui_works_when_the_endpoint_fails(page, site_url, status) -> None:
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    sent = _record(page, status=status)
    _open_builder(page, site_url)
    page.locator("#copy-command").click()
    page.get_by_role("button", name="Copied").first.wait_for()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert "chock" in copied
    page.locator("#tab-file").click()
    with page.expect_download() as info:
        page.locator("#download-file").click()
    assert info.value.suggested_filename
    assert len(_wait_for(page, sent, 2)) == 2


def test_ui_works_when_the_endpoint_is_unreachable(page, site_url) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.route("**/api/event", lambda route: route.abort())
    _open_builder(page, site_url)
    page.locator("#copy-command").click()
    page.locator("#tab-file").click()
    with page.expect_download():
        page.locator("#download-file").click()
    page.select_option("#builder-start", "")
    assert errors == []


def test_track_drops_bad_calls(page, site_url) -> None:
    sent = _record(page)
    page.goto(site_url + REPORT + "?track=1")
    page.evaluate(
        """async () => {
          const { track } = await import('/js/common.js');
          track('unknown-event');
          track('share-copied', { agent: 'claude-code' });
          track('install-copied');
          track('install-copied', { agent: 'Claude Code' });
          track('install-copied', { agent: 'x'.repeat(65) });
          track('install-copied', { agent: 'codex', url: location.href });
          track('install-copied', { agent: 7 });
          track('toString');
          track('__proto__');
        }"""
    )
    page.wait_for_timeout(QUIET_MS)
    assert sent == []
    assert_clean(page)
