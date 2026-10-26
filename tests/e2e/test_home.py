"""The home page in a browser: tabs by keyboard, the calculator, no JavaScript, 390px."""

import re

import pytest
import yaml
from conftest import ROOT, assert_clean, collect

from sitegen import homedata

MOBILE = {"width": 390, "height": 844}


def _fmt_outputs(findings, share, minutes, rate, days) -> tuple[str, str, str]:
    hours, money, saved = homedata.savings(findings, share, minutes, rate, days)
    return (
        homedata.fmt_hours(hours),
        "$" + homedata.fmt_money(money),
        homedata.fmt_hours(saved),
    )


def _printed(page) -> tuple[str, str, str]:
    return (
        page.locator("#calc-out-hours").inner_text(),
        page.locator("#calc-out-money").inner_text(),
        page.locator("#calc-out-days").inner_text(),
    )


def test_home_requests_nothing_outside_the_site(page, site_url) -> None:
    response = page.goto(site_url + "/")
    assert response.status == 200
    page.wait_for_load_state("networkidle")
    assert_clean(page)


def test_demo_tabs_work_by_keyboard(page, site_url) -> None:
    page.goto(site_url + "/")
    tabs = page.locator('[data-demo] [role="tab"]')
    assert tabs.count() == 5
    assert tabs.nth(0).get_attribute("aria-selected") == "true"
    visible = page.locator(".demo-case:visible")
    assert visible.count() == 1
    assert "git commit --no-verify -m wip" in visible.inner_text()
    tabs.nth(0).focus()
    page.keyboard.press("ArrowRight")
    assert tabs.nth(1).get_attribute("aria-selected") == "true"
    assert page.evaluate("document.activeElement.id") == "tab-scan-secrets"
    visible = page.locator(".demo-case:visible")
    assert visible.count() == 1
    assert "Refused by scan-secrets" in visible.inner_text()
    assert ".env" in visible.inner_text()
    page.keyboard.press("End")
    assert tabs.nth(4).get_attribute("aria-selected") == "true"
    assert "protect-agent-config" in page.locator(".demo-case:visible").inner_text()
    page.keyboard.press("ArrowRight")
    assert tabs.nth(0).get_attribute("aria-selected") == "true"
    assert (
        page.locator(
            '.demo-case:visible a[href="/coding/policies/block-no-verify/"]'
        ).count()
        == 1
    )
    assert_clean(page)


def test_demo_lists_every_case_without_javascript(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(site_url + "/")
        cases = page.locator(".demo-case")
        assert cases.count() == 5
        for i in range(5):
            assert cases.nth(i).is_visible()
        assert page.locator('[role="tab"]').count() == 0
    finally:
        context.close()


def test_use_case_tabs_work_by_keyboard(page, site_url) -> None:
    page.goto(site_url + "/")
    tabs = page.locator('[data-usecases] [role="tab"]')
    assert tabs.count() == 4
    assert page.locator(".usecase-tabs").is_hidden()
    assert page.locator(".usecase:visible").count() == 1
    assert "block-no-verify" in page.locator(".usecase:visible").inner_text()
    tabs.nth(0).focus()
    page.keyboard.press("ArrowRight")
    assert page.locator(".usecase:visible").count() == 1
    assert "block-test-skips" in page.locator(".usecase:visible").inner_text()
    page.keyboard.press("Home")
    assert tabs.nth(0).get_attribute("aria-selected") == "true"
    page.keyboard.press("ArrowLeft")
    assert tabs.nth(3).get_attribute("aria-selected") == "true"
    assert (
        "owasp-asi01-agent-goal-hijack" in page.locator(".usecase:visible").inner_text()
    )
    assert_clean(page)


def test_use_cases_stack_without_javascript(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(site_url + "/")
        assert page.locator(".usecase").count() == 4
        for i in range(4):
            assert page.locator(".usecase").nth(i).is_visible()
        assert page.locator(".usecase-tabs a").count() == 4
    finally:
        context.close()


def test_calculator_prints_the_formula_result(page, site_url) -> None:
    page.goto(site_url + "/")
    assert _printed(page) == _fmt_outputs(20, 60, 45, 100, 3)
    assert _printed(page) == ("9", "$900", "1.8")
    for name, value in (
        ("findings", "35"),
        ("share", "40"),
        ("minutes", "50"),
        ("rate", "120"),
        ("days", "2.5"),
    ):
        page.fill(f"#calc-{name}", value)
    assert _printed(page) == _fmt_outputs(35, 40, 50, 120, 2.5)
    assert page.locator("#calc-invalid").is_hidden()
    page.fill("#calc-share", "150")
    assert page.locator("#calc-invalid").is_visible()
    assert page.locator("#calc-out-hours").inner_text() == "–"
    page.fill("#calc-share", "100")
    assert page.locator("#calc-invalid").is_hidden()
    assert _printed(page) == _fmt_outputs(35, 100, 50, 120, 2.5)
    assert_clean(page)


def test_calculator_text_shows_without_javascript(browser, site_url) -> None:
    context = browser.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(site_url + "/")
        text = page.locator("#cost-calculator").inner_text()
        assert (
            "Hours saved = findings × share covered × minutes per late fix ÷ 60" in text
        )
        assert "the formula gives 9 hours, $900 and 1.8 days" in text
        assert "These are example values, and we did not measure them." in text
    finally:
        context.close()


def test_faq_opens_with_the_keyboard(page, site_url) -> None:
    page.goto(site_url + "/")
    summary = page.locator(".faq-details summary", has_text="What are general agents?")
    summary.focus()
    page.keyboard.press("Enter")
    details = page.locator(".faq-details", has_text="What are general agents?")
    assert details.get_attribute("open") is not None
    assert "so there is nothing to install yet" in details.inner_text()


def test_home_fits_a_phone(browser, site_url) -> None:
    context = browser.new_context(viewport=MOBILE)
    try:
        page = context.new_page()
        page.goto(site_url + "/")
        page.wait_for_load_state("networkidle")
        assert not page.evaluate(
            "document.scrollingElement.scrollWidth > window.innerWidth"
        )
        hero = page.locator(".home-hero")
        assert hero.bounding_box()["width"] <= MOBILE["width"]
        for selector in (
            "h1",
            "#home-install",
            "#demo",
            "#track-coding",
            "#track-general",
            "#track-repos",
        ):
            box = page.locator(selector).first.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= MOBILE["width"] + 1, (
                selector
            )
        cards = page.locator(".track-card")
        assert cards.count() == 3
        for i in (0, 1):
            assert (
                cards.nth(i).bounding_box()["y"] < cards.nth(i + 1).bounding_box()["y"]
            )
        heading = page.locator("h1").inner_text()
        assert re.sub(r"\s+", " ", heading) == (
            "Blocks your coding agent's wrong moves before they land."
        )
    finally:
        context.close()


# VID-OFF: the voiced promos are gone; only the silent recording is on the home page.
MEDIA = (
    # DOCS-6: the own-policy VHS recording; its poster is the PNG VHS writes.
    ("/video/own-policy.mp4", "/video/own-policy.png"),
)


def test_videos_sit_below_the_hero(browser, site_url) -> None:
    for viewport in (MOBILE, {"width": 1280, "height": 800}):
        context = browser.new_context(viewport=viewport)
        try:
            page = context.new_page()
            collect(page, site_url)
            page.goto(site_url + "/")
            videos = page.locator("video.video-player")
            assert videos.count() == len(MEDIA)
            for i in range(len(MEDIA)):
                video = videos.nth(i)
                video.scroll_into_view_if_needed()
                assert video.is_visible()
                hero = page.locator("#top").bounding_box()
                box = video.bounding_box()
                assert box["y"] >= hero["y"] + hero["height"]
                assert abs(box["width"] / box["height"] - 16 / 9) < 0.02
            page.wait_for_load_state("networkidle")
            assert_clean(page)
        finally:
            context.close()


def test_video_media_served_and_mp4_waits_for_play(page, site_url) -> None:
    requested: list[str] = []
    page.on("request", lambda req: requested.append(req.url))
    page.goto(site_url + "/")
    videos = page.locator("video.video-player")
    for i in range(videos.count()):
        videos.nth(i).scroll_into_view_if_needed()
    page.wait_for_load_state("networkidle")
    assert not [url for url in requested if url.endswith(".mp4")]
    for video, poster in MEDIA:
        image = "image/png" if poster.endswith(".png") else "image/jpeg"
        for path, kind in ((poster, image), (video, "video/mp4")):
            response = page.request.head(site_url + path)
            assert response.status == 200, path
            assert response.headers["content-type"] == kind
    for gone in ("/video/chock-promo-v9b.mp4", "/video/chock-promo-v8-explainer.mp4"):
        assert page.request.get(site_url + gone).status == 404, gone
    assert_clean(page)


def test_home_has_no_horizontal_scroll_at_320px(browser, site_url) -> None:
    context = browser.new_context(viewport={"width": 320, "height": 640})
    try:
        page = context.new_page()
        page.goto(site_url + "/")
        assert not page.evaluate(
            "document.scrollingElement.scrollWidth > window.innerWidth"
        )
    finally:
        context.close()


PIPELINE_JS = """() => [...document.querySelectorAll(".pipeline-steps")].map((ol) => {
  const box = ol.getBoundingClientRect();
  return {
    right: box.right,
    chips: [...ol.children].map((li) => {
      const r = li.getBoundingClientRect();
      const after = getComputedStyle(li, "::after");
      const before = getComputedStyle(li, "::before");
      return {
        text: li.textContent.trim(),
        left: r.left, right: r.right, top: r.top, bottom: r.bottom,
        shown: getComputedStyle(li).visibility === "visible" && r.width > 0 && r.height > 0,
        arrow: after.content,
        arrowShown: after.content !== "none" && after.visibility === "visible"
          && after.opacity !== "0" && after.color !== "rgba(0, 0, 0, 0)",
        before: before.content,
        gradient: getComputedStyle(li).backgroundImage.includes("linear-gradient"),
      };
    }),
  };
})"""
ARROW_REACH = 26  # the arrow sits this far right of its chip; the row gap is wider
CARD_PADDING = 28


@pytest.mark.parametrize("size", [1280, 390], ids=lambda w: f"{w}px")
def test_pipeline_chips_and_arrows_are_visible_and_clear(
    browser, site_url, size
) -> None:
    """Both pipelines: every chip shows, none overlaps a neighbour, every arrow between chips shows."""
    land = yaml.safe_load((ROOT / "data" / "home.yaml").read_text("utf-8"))["landing"]
    # The steps come from data/home.yaml (shift_today, shift_with), rendered by templates/home/shift.html.
    wanted = [land["shift_today"], land["shift_with"]]
    context = browser.new_context(viewport={"width": size, "height": 900})
    try:
        page = context.new_page()
        collect(page, site_url)
        page.goto(site_url + "/")
        lists = page.evaluate(PIPELINE_JS)
        assert len(lists) == len(wanted) == 2
        for n, (got, steps) in enumerate(zip(lists, wanted, strict=True)):
            chips = got["chips"]
            assert [c["text"] for c in chips] == steps, f"pipeline {n}"
            for i, chip in enumerate(chips):
                where = f"pipeline {n} chip {i} ({chip['text']})"
                assert chip["shown"], f"{where}: not visible"
                assert 0 <= chip["left"] and chip["right"] <= size, (
                    f"{where}: outside the {size}px viewport"
                )
                assert chip["before"] == "none", f"{where}: numbered marker back"
                last = i == len(chips) - 1
                assert chip["arrowShown"] is (not last), f"{where}: arrow {chip}"
                assert chip["arrow"] == ("none" if last else '"→"'), where
                if not last:
                    assert chip["right"] + ARROW_REACH <= got["right"] + CARD_PADDING, (
                        f"{where}: arrow leaves the card"
                    )
                for other in chips[i + 1 :]:
                    apart = (
                        chip["right"] <= other["left"]
                        or other["right"] <= chip["left"]
                        or chip["bottom"] <= other["top"]
                        or other["bottom"] <= chip["top"]
                    )
                    assert apart, f"{where} overlaps {other['text']}"
                nxt = chips[i + 1] if not last else None
                if nxt and abs(nxt["top"] - chip["top"]) < 4:
                    assert nxt["left"] >= chip["right"] + ARROW_REACH, (
                        f"{where}: arrow runs into {nxt['text']}"
                    )
        # With chock, the two chock steps sit on the accent gradient and the others do not.
        with_chock = lists[1]["chips"]
        assert [c["gradient"] for c in with_chock] == [False, True, True, False]
        assert_clean(page)
    finally:
        context.close()
