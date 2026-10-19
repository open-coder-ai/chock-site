"""The Report an issue page: each button's form link, context from the query, hostile values."""

from urllib.parse import parse_qs, urlencode, urlsplit

from conftest import assert_clean, screenshot

PAGE = "/report/"
CATALOG_REF = "catalog-ref"
FORMS = {
    "policy-wrong": ("chock-catalog", "policy-wrong.yml"),
    "install": ("chock", "bug-report.yml"),
    "site-bug": ("chock-site", "site-bug.yml"),
    "policy-proposal": ("chock-catalog", "policy-proposal.yml"),
}


def _links(page) -> dict[str, tuple[str, dict[str, list[str]]]]:
    """Each button's form path and query, by kind."""
    out = {}
    for kind in FORMS:
        href = page.locator(f'a[data-report-kind="{kind}"]').get_attribute("href")
        parts = urlsplit(href)
        out[kind] = (f"{parts.netloc}{parts.path}", parse_qs(parts.query))
    return out


def test_buttons_open_each_form(page, site_url, request) -> None:
    page.goto(site_url + PAGE)
    links = _links(page)
    for kind, (repo, template) in FORMS.items():
        path, query = links[kind]
        assert path == f"github.com/open-coder-ai/{repo}/issues/new", kind
        assert query["template"] == [template], kind
        assert "title" not in query and "agent" not in query, kind
    assert set(links["site-bug"][1]) == {"template", CATALOG_REF, "engine-ref"}
    assert set(links["policy-wrong"][1]) == {"template", CATALOG_REF}
    # The security card comes before every other card.
    first = page.locator("main h2").first
    assert first.get_attribute("id") == "vulnerability"
    assert_clean(page)
    screenshot(page, request.node.name)


def test_policy_context_fills_the_fields(page, site_url) -> None:
    page.goto(site_url + "/coding/policies/block-no-verify/")
    page.locator("a", has_text="Report a problem with this policy").click()
    page.wait_for_url("**/report/?**")
    links = _links(page)
    query = links["policy-wrong"][1]
    assert query["policy-id"] == ["block-no-verify"]
    assert query["title"][0].startswith("[policy-wrong]: block-no-verify ")
    site = links["site-bug"][1]
    assert site["page-url"] == ["https://chock.sh/coding/policies/block-no-verify/"]
    assert "agent" not in site
    assert_clean(page)


def test_agent_context_reaches_every_form(page, site_url) -> None:
    query = urlencode({"agent": "codex", "page": "/coding/install/"})
    page.goto(f"{site_url}{PAGE}?{query}")
    for kind, (_, form) in _links(page).items():
        assert form["agent"] == ["codex"], kind


def test_hostile_query_is_dropped(page, site_url) -> None:
    query = urlencode(
        {
            "policy": "<img src=x onerror=alert(1)>",
            "version": "1 2",
            "agent": "not-an-agent",
            "page": "https://evil.example/",
            "title": "planted",
            "body": "planted",
        }
    )
    page.goto(f"{site_url}{PAGE}?{query}")
    for kind, (_, form) in _links(page).items():
        assert set(form) <= {"template", CATALOG_REF, "engine-ref"}, (kind, form)
    assert_clean(page)


def test_builder_link_follows_the_picked_agent(page, site_url) -> None:
    page.goto(site_url + "/coding/builder/#client=cursor")
    link = page.locator("#report-link")
    assert (
        link.get_attribute("href")
        == "/report/?agent=cursor&page=%2Fcoding%2Fbuilder%2F"
    )
    assert_clean(page)


def test_an_agent_the_forms_do_not_offer_is_sent_as_other(page, site_url) -> None:
    page.goto(site_url + PAGE + "?agent=grok")
    assert _links(page)["site-bug"][1]["agent"] == ["other"]
    page.goto(site_url + PAGE + "?agent=cursor")
    assert _links(page)["site-bug"][1]["agent"] == ["cursor"]
