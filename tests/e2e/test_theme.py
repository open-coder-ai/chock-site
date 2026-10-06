"""Self-hosted fonts load from /fonts/ as font/woff2."""

import re
import urllib.request

from conftest import assert_clean

FONTS = [
    "InstrumentSans-Regular",
    "InstrumentSans-Medium",
    "InstrumentSans-SemiBold",
    "InstrumentSans-Bold",
    "JetBrainsMono-Regular",
    "JetBrainsMono-Medium",
    "JetBrainsMono-Bold",
]


def test_css_font_urls_are_local(site_url) -> None:
    with urllib.request.urlopen(site_url + "/css/site.css") as response:
        css = response.read().decode("utf-8")
    urls = re.findall(r'url\("([^"]+)"\)', css)
    assert urls and all(url.startswith("/fonts/") for url in urls)


def test_every_font_file_serves_as_woff2(page, site_url) -> None:
    page.goto(site_url + "/")
    for name in FONTS:
        response = page.request.get(site_url + f"/fonts/{name}.woff2")
        assert response.status == 200, name
        assert response.headers["content-type"] == "font/woff2", name
        assert response.body()[:4] == b"wOF2", name
    assert_clean(page)
