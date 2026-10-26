"""The builder (plan 6.5, PR 3): presets, URL state, downloads, warnings, real install."""

import json
import re
import subprocess
import sys
from pathlib import Path

from combo import pick_start
from conftest import CATALOG, assert_clean, collect, screenshot

from sitegen import engine
from sitegen.presets import load_presets

ROOT = Path(__file__).resolve().parents[2]
PRESETS = {p.id: p for p in load_presets(ROOT / "data" / "presets.yaml")}
BUILDER = "/coding/builder/"
MOBILE = {"width": 390, "height": 844}


def _open(page, site_url: str, fragment: str = "") -> None:
    """Open the full builder; with no fragment the start screen shows, so skip it."""
    page.goto(site_url + BUILDER + fragment)
    if not fragment:
        page.get_by_role("button", name="Skip to the full builder").click()
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
    pick_start(page, "git-hygiene")
    members = _members("git-hygiene")
    assert _count(page) == f"{len(members)} policies"
    command = page.locator("[data-selection-code]").inner_text()
    assert re.search(r"--selection [A-Za-z0-9_-]+ --client ", command), command
    share = _share(page)
    assert share.endswith(f"#client=claude-code&p={','.join(members)}")
    assert (
        sorted(p["id"] for p in engine.load_selection(_code(page))["policies"])
        == members
    )
    assert page.evaluate("location.hash").startswith("#s=")
    assert engine.load_selection(page.url)["client"] == "claude-code"
    screenshot(page, "builder_git_hygiene")
    assert_clean(page)


def test_share_link_restores_the_picks_in_a_new_page(page, site_url) -> None:
    _open(page, site_url)
    pick_start(page, "git-hygiene")
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
    pick_start(page, "secrets")
    page.get_by_role("tab", name="Selection file").click()
    with page.expect_download() as info:
        page.get_by_role("button", name="Download chock.selection.json").click()
    download = info.value
    assert download.suggested_filename == "chock.selection.json"
    target = tmp_path / "chock.selection.json"
    download.save_as(str(target))
    selection = json.loads(target.read_text(encoding="utf-8"))
    engine.check_selection(selection)
    # The engine loads the saved file by path, as `chock install --selection <file>` does.
    assert engine.load_selection(str(target))["policies"] == selection["policies"]
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
    pick_start(page, "test-integrity")
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
    assert page.get_by_text("The site could not read this link.").is_visible()
    assert _count(page) == "0 policies"
    assert page.locator(".bmember input:checked").count() == 0
    assert_clean(page)


def test_other_catalog_ref_with_a_different_hash_shows_notice_and_can_be_used_anyway(
    page, site_url
) -> None:
    _open(page, site_url)
    pick_start(page, "git-hygiene")
    selection = engine.load_selection(_code(page))
    selection["catalog"]["ref"] = "0" * 40
    selection["policies"][0]["sha256"] = "0" * 64
    _open(page, site_url, "#s=" + engine.encode_selection(selection))
    notice = page.locator("#link-notice").inner_text()
    assert "000000000000" in notice
    assert "This site shows" in notice
    assert _count(page) == "0 policies"
    page.get_by_role("button", name="Use the same policies here").click()
    assert _picked_ids(page) == _members("git-hygiene")
    assert_clean(page)


def test_other_catalog_ref_with_same_hashes_is_taken_without_notice(
    page, site_url
) -> None:
    _open(page, site_url)
    pick_start(page, "git-hygiene")
    selection = engine.load_selection(_code(page))
    selection["catalog"]["ref"] = "0" * 40
    _open(page, site_url, "#s=" + engine.encode_selection(selection))
    assert page.locator("#link-notice").inner_text().strip() == ""
    assert page.get_by_role("button", name="Use the same policies here").count() == 0
    assert _picked_ids(page) == _members("git-hygiene")
    assert_clean(page)


def test_unknown_id_is_listed_not_dropped_silently(page, site_url) -> None:
    _open(page, site_url)
    pick_start(page, "test-integrity")
    selection = engine.load_selection(_code(page))
    selection["policies"].append(
        {
            "from": "catalog",
            "id": "no-such-policy",
            "version": "0.0.1",
            "sha256": "0" * 64,
        }
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
    pick_start(page, "git-hygiene")
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
    pick_start(page, "git-hygiene")
    code = _code(page)
    page.evaluate(
        "document.fonts.ready.then(() => true)"
    )  # no font fetch left to abort
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
        pick_start(page, "git-hygiene")
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


def test_sticky_panel_keeps_outputs_reachable(browser, site_url) -> None:
    """1280x800 with git-hygiene: the panel fits the window, so the command stays on screen."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    try:
        page = context.new_page()
        collect(page, site_url)
        _open(page, site_url, "#preset=git-hygiene")
        for scroll in (0, 1500, 3000):
            page.evaluate(f"window.scrollTo(0, {scroll})")
            tab = page.locator("#tab-command").bounding_box()
            panel = page.locator(".selection").bounding_box()
            assert panel["height"] <= 800, panel
            if scroll:
                assert 0 <= tab["y"] and tab["y"] + tab["height"] <= 800, (scroll, tab)
        assert_clean(page)
    finally:
        context.close()


def test_phone_bar_and_chips(browser, site_url) -> None:
    """390x844: bottom bar with count and Copy command; chips keep their natural width."""
    context = browser.new_context(
        viewport=MOBILE, permissions=["clipboard-read", "clipboard-write"]
    )
    try:
        page = context.new_page()
        collect(page, site_url)
        _open(page, site_url)
        bar = page.locator("#mobile-bar")
        assert not bar.is_visible()
        pick_start(page, "git-hygiene")
        assert bar.is_visible()
        assert "6 policies" in bar.inner_text()
        assert "note" in bar.inner_text()
        page.locator("#mb-copy").click()
        page.locator("#mb-copy", has_text="Copied").wait_for()
        command = page.locator("[data-selection-code]").inner_text()
        assert page.evaluate("navigator.clipboard.readText()") == command
        page.get_by_role("link", name="Your selection").click()
        assert page.locator("#your-selection").is_visible()
        for _ in range(40):  # the jump scrolls smoothly; wait for it to settle
            top = page.locator("#your-selection").bounding_box()["y"]
            if 0 <= top < 844:
                break
            page.wait_for_timeout(100)
        assert 0 <= top < 844, top
        assert _count(page) == "6 policies"
        row = page.locator(".bmember").first
        chip = row.locator(".label")
        assert chip.bounding_box()["width"] < row.bounding_box()["width"] * 0.5
        width = page.evaluate(
            "[document.scrollingElement.scrollWidth, window.innerWidth]"
        )
        assert width[0] <= width[1], width
        while page.locator(".sel-item .remove").count():
            page.locator(".sel-item .remove").first.click()
        assert not bar.is_visible()
        assert_clean(page)
    finally:
        context.close()


def test_phone_bar_is_hidden_on_desktop(page, site_url) -> None:
    _open(page, site_url, "#preset=git-hygiene")
    assert not page.locator("#mobile-bar").is_visible()


def test_phone_bar_does_not_cover_the_footer(browser, site_url) -> None:
    """390x844, git-hygiene picked, scrolled to the end: the last footer link
    sits wholly above the bar (plan 9, PR 4 item 2). Reduced motion turns off
    smooth scrolling, so the jump to the end lands before the boxes are read."""
    context = browser.new_context(viewport=MOBILE, reduced_motion="reduce")
    try:
        page = context.new_page()
        collect(page, site_url)
        _open(page, site_url, "#preset=git-hygiene")
        page.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
        page.wait_for_function(
            "Math.ceil(window.scrollY + window.innerHeight)"
            " >= document.scrollingElement.scrollHeight"
        )
        bar = page.locator("#mobile-bar").bounding_box()
        link = page.locator(".footer-links a").last.bounding_box()
        assert bar and link, (bar, link)
        assert link["y"] + link["height"] <= bar["y"], (
            f"footer link bottom {link['y'] + link['height']:.1f} "
            f"is below bar top {bar['y']:.1f}"
        )
        assert_clean(page)
    finally:
        context.close()


def test_smooth_scroll_respects_reduced_motion(browser, site_url) -> None:
    for motion, expected in (("reduce", "auto"), ("no-preference", "smooth")):
        context = browser.new_context(reduced_motion=motion)
        try:
            page = context.new_page()
            page.goto(site_url + BUILDER)
            behavior = page.evaluate(
                "getComputedStyle(document.documentElement).scrollBehavior"
            )
            assert behavior == expected, motion
        finally:
            context.close()


def test_link_notices_echo_only_short_catalog_shaped_ids(page, site_url) -> None:
    long_id = "a" * 65
    ids = [f"no-such-{i}" for i in range(6)] + ["Evil<b>Text", long_id]
    cases = (
        (
            "#client=codex&p=" + ",".join(ids),
            ["no-such-0", "no-such-4", "3 ids not shown"],
        ),
        ("#preset=" + "x" * 200, ["1 id not shown"]),
        ("#client=" + "b" * 80, ["1 id not shown"]),
    )
    for fragment, expected in cases:
        # A hash-only goto does not reload: open each fragment on a fresh page.
        other = page.context.new_page()
        collect(other, site_url)
        other.goto(site_url + BUILDER + fragment)
        other.wait_for_selector("#link-notice:not(:empty)")
        notes = other.locator("#link-notice").inner_text()
        for text in expected:
            assert text in notes, (fragment, notes)
        for text in ("no-such-5", "Evil", long_id, "x" * 65, "b" * 65):
            assert text not in notes, (fragment, notes)
        assert_clean(other)


def test_grade_notes_agree_in_number(page, site_url) -> None:
    _open(page, site_url, "#client=claude-code&p=agent-discipline")
    assert "agent-discipline is text only" in page.locator(".notes").inner_text()
    other = page.context.new_page()
    collect(other, site_url)
    _open(other, site_url, "#client=claude-code&p=agent-discipline,code-safety")
    notes = other.locator(".notes").inner_text()
    assert "agent-discipline, code-safety are text only" in notes
    assert_clean(page)
    assert_clean(other)


def test_label_note_names_the_picked_agent(page, site_url) -> None:
    _open(page, site_url, "#client=claude-code&p=agent-discipline")
    note = page.locator("#builder-grades-agent")
    assert (
        note.inner_text()
        == "Labels and counts are the catalog's grades on Claude Code."
    )
    page.locator("#client-codex").check()
    assert note.inner_text() == "Labels and counts are the catalog's grades on Codex."
    assert_clean(page)


_LAYOUT = """() => {
    const rgb = c => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
    const lum = c => {
        const [r, g, b] = rgb(c).map(v => {
            v /= 255;
            return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const contrast = (a, b) => {
        const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
        return (x + 0.05) / (y + 0.05);
    };
    const panel = document.querySelector(".selection");
    const box = panel.getBoundingClientRect();
    const scrolls = e => ["auto", "scroll"].includes(getComputedStyle(e).overflowX);
    const outside = [...panel.querySelectorAll("*")].filter(e => {
        for (let a = e.parentElement; a && a !== panel; a = a.parentElement) {
            if (scrolls(a)) return false;
        }
        return e.getBoundingClientRect().right > box.right + 1;
    }).map(e => e.tagName + "." + e.className);
    const groups = [...document.querySelectorAll(".bgroup:not(.hidden)")].map(g => {
        const cs = getComputedStyle(g);
        const h = g.querySelector("h3");
        const hs = getComputedStyle(h);
        return {
            border: parseFloat(cs.borderTopWidth),
            filled: cs.backgroundColor !== "rgba(0, 0, 0, 0)",
            rule: parseFloat(hs.borderBottomWidth),
            weight: Number(hs.fontWeight),
            contrast: contrast(hs.color, cs.backgroundColor),
        };
    });
    const says = new Set([...document.querySelectorAll(".bmember:not(.hidden) .bsays")]
        .map(e => Math.round(e.getBoundingClientRect().left)));
    return {
        right: box.right,
        width: innerWidth,
        scrollWidth: document.scrollingElement.scrollWidth,
        outside,
        groups,
        says: [...says],
    };
}"""


def test_full_builder_layout_from_1024_to_1920(browser, site_url) -> None:
    # Windows display scaling: 1.25 and 1.5 device pixels per CSS pixel.
    sizes = [(w, 1) for w in (1024, 1280, 1440, 1560, 1920)]
    sizes += [(w, scale) for w in (1280, 1536) for scale in (1.25, 1.5)]
    for width, scale in sizes:
        context = browser.new_context(
            viewport={"width": width, "height": 900}, device_scale_factor=scale
        )
        try:
            page = context.new_page()
            page.goto(site_url + "/coding/builder/#preset=git-hygiene")
            page.wait_for_selector(".sel-item")
            got = page.evaluate(_LAYOUT)
            where = f"{width} px at {scale}x"
            assert got["right"] <= got["width"], f"{where}: panel clipped {got}"
            assert got["scrollWidth"] <= got["width"], f"{where}: horizontal scroll"
            assert not got["outside"], (
                f"{where}: panel content clipped {got['outside']}"
            )
            assert len(got["says"]) == 1, f"{where}: says text starts at {got['says']}"
            assert got["groups"], where
            for group in got["groups"]:
                assert group["border"] >= 1 and group["filled"], f"{where}: {group}"
                assert group["rule"] >= 2 and group["weight"] >= 700, (
                    f"{where}: {group}"
                )
                assert group["contrast"] >= 4.5, f"{where}: {group}"
        finally:
            context.close()
