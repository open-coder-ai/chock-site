"""LN-3: link-preview tags (og: and twitter:) on every page, and the FAQ's comparison entry."""

import struct
from pathlib import Path

from tests.test_marketing import MetaParser

COMPARE_URL = "https://github.com/open-coder-ai/chock/blob/main/docs/compare.md"
SITE = "https://chock.sh"


def _meta(page: Path) -> MetaParser:
    parser = MetaParser()
    parser.feed(page.read_text(encoding="utf-8"))
    return parser


def test_preview_image_is_an_absolute_url_with_its_real_size(built) -> None:
    for page in sorted(built.out.rglob("*.html")):
        tags = _meta(page).og
        image = tags["og:image"]
        assert image.startswith(SITE + "/"), (
            f"{page}: og:image {image!r} is not absolute"
        )
        head = (built.out / image.removeprefix(SITE + "/")).read_bytes()[:24]
        assert head[:8] == b"\x89PNG\r\n\x1a\n", page
        width, height = struct.unpack(">II", head[16:24])
        assert tags["og:image:type"] == "image/png", page
        assert tags["og:image:width"] == str(width), page
        assert tags["og:image:height"] == str(height), page
        assert tags["og:image:alt"], page
        # summary_large_image wants about 2:1 and at least 300x157.
        assert width >= 2 * 300 and 1.8 <= width / height <= 2.1, (width, height)


def test_twitter_tags_repeat_the_open_graph_ones(built) -> None:
    for page in sorted(built.out.rglob("*.html")):
        tags = _meta(page).og
        assert tags["twitter:card"] == "summary_large_image", page
        assert tags["twitter:title"] == tags["og:title"], page
        assert tags["twitter:description"] == tags["og:description"], page
        assert tags["twitter:image"] == tags["og:image"], page
        assert tags["twitter:image:alt"] == tags["og:image:alt"], page


def test_home_and_builder_previews_say_more_than_their_title(built) -> None:
    for page in ("index.html", "coding/builder/index.html"):
        parser = _meta(built.out / page)
        title = parser.og["og:title"].removesuffix(" · chock.sh")
        assert parser.og["og:description"] == parser.description, page
        assert parser.description != title, page


def test_faq_links_the_comparison_in_the_chock_repository(built) -> None:
    page = (built.out / "faq" / "index.html").read_text(encoding="utf-8")
    assert '<h3 id="compare">How does Chock compare with other tools?</h3>' in page
    assert f'<a class="arrow-link" href="{COMPARE_URL}">' in page
    twin = (built.out / "faq" / "index.md").read_text(encoding="utf-8")
    assert f"]({COMPARE_URL})" in twin
    assert f"]({SITE}{COMPARE_URL})" not in twin
    assert f"]({SITE}/report/)" in twin
