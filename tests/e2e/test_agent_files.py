"""Agent-readable output: llms.txt, api/*.json, and twin front matter."""

import json
import re
import urllib.request

from conftest import assert_clean


def _get(site_url: str, path: str) -> str:
    with urllib.request.urlopen(site_url + path) as r:
        return r.read().decode("utf-8")


def test_llms_txt_lists_block_no_verify(site_url) -> None:
    text = _get(site_url, "/llms.txt")
    assert "# chock.sh" in text
    assert "/coding/policies/block-no-verify/index.md" in text
    for heading in (
        "## Docs",
        "## Coding agents",
        "## Coding agents: policies",
        "## Coding agents: presets",
        "## Data",
    ):
        assert heading in text


def test_api_index_and_catalog(site_url) -> None:
    index = json.loads(_get(site_url, "/api/index.json"))
    assert index["schema_version"] == 1
    assert index["tracks"] == [
        {
            "id": "coding",
            "title": "Coding agents",
            "home": "/coding/",
            "api": "/api/coding/",
        }
    ]
    catalog = json.loads(_get(site_url, "/api/coding/catalog.json"))
    assert catalog["schema_version"] == 1
    assert catalog["track"] == "coding"
    assert all(p["track"] == "coding" for p in catalog["policies"])
    schema = json.loads(_get(site_url, "/api/coding/selection.schema.json"))
    assert "policies" in schema["properties"]


def test_twin_front_matter_sha_matches_page(site_url) -> None:
    html = _get(site_url, "/coding/policies/block-no-verify/")
    sha = re.search(r"sha256-value[^>]*>([0-9a-f]{64})<", html).group(1)
    twin = _get(site_url, "/coding/policies/block-no-verify/index.md")
    front = twin.split("---", 2)[1]
    assert f"sha256: {sha}" in front
    assert "track: coding" in front
    record = json.loads(_get(site_url, "/api/coding/policies/block-no-verify.json"))
    assert record["sha256"] == sha


def test_llms_full_loads(site_url, page) -> None:
    response = page.goto(site_url + "/llms-full.txt")
    assert response.status == 200
    assert "/coding/policies/block-no-verify/index.md" in response.body().decode(
        "utf-8"
    )
    assert_clean(page)
