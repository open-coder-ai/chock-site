"""The Report an issue page (IS-1b): issue-form links, hostile context, and where it is linked."""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml

from sitegen import report

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE_URL = "https://chock.sh"
AGENTS = ["claude-code", "cursor", "codex", "copilot", "devin"]
REPORT = yaml.safe_load((DATA / "report.yaml").read_text(encoding="utf-8"))
KINDS = {kind["id"]: kind for kind in REPORT["kinds"]}
FULL = {
    "policy": "block-no-verify",
    "version": "0.4.4",
    "agent": "cursor",
    "page": "/coding/policies/block-no-verify/",
    "catalog_ref": "3c082c9ca94da22e9daffb4e7b11aa6f5fff4c30",
    "engine_ref": "7f472b7b85d6c9fb6af491db051b57988cadda6a",
}
HOSTILE = [
    "<script>alert(1)</script>",
    "a b",
    "Block-No-Verify",
    "x" * 65,
    "",
    "id\nmore",
    "cursor\n",
    "evil&template=x.yml",
]


def _url(kind_id: str, context: dict) -> tuple[str, dict[str, list[str]]]:
    url = report.issue_url(REPORT, KINDS[kind_id], context, AGENTS, SITE_URL)
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}", parse_qs(parts.query)


def test_report_yaml_passes_its_check() -> None:
    report.check_report(REPORT)


@pytest.mark.parametrize(
    ("kind_id", "repo", "template"),
    [
        ("policy-wrong", "chock-catalog", "policy-wrong.yml"),
        ("install", "chock", "bug-report.yml"),
        ("site-bug", "chock-site", "site-bug.yml"),
        ("policy-proposal", "chock-catalog", "policy-proposal.yml"),
    ],
)
def test_each_kind_opens_its_form(kind_id, repo, template) -> None:
    base, query = _url(kind_id, {})
    assert base == f"https://github.com/open-coder-ai/{repo}/issues/new"
    assert query == {"template": [template]}


def test_full_context_fills_each_kinds_fields() -> None:
    _, query = _url("policy-wrong", FULL)
    assert query == {
        "template": ["policy-wrong.yml"],
        "title": ["[policy-wrong]: block-no-verify 0.4.4"],
        "policy-id": ["block-no-verify"],
        "agent": ["cursor"],
        "catalog-ref": [FULL["catalog_ref"]],
    }
    _, query = _url("install", FULL)
    assert query == {"template": ["bug-report.yml"], "agent": ["cursor"]}
    _, query = _url("site-bug", FULL)
    assert query == {
        "template": ["site-bug.yml"],
        "page-url": [SITE_URL + FULL["page"]],
        "agent": ["cursor"],
        "catalog-ref": [FULL["catalog_ref"]],
        "engine-ref": [FULL["engine_ref"]],
    }
    _, query = _url("policy-proposal", FULL)
    assert query == {"template": ["policy-proposal.yml"], "agent": ["cursor"]}


def test_title_needs_every_key() -> None:
    _, query = _url("policy-wrong", {"policy": "block-no-verify"})
    assert "title" not in query
    assert query["policy-id"] == ["block-no-verify"]


@pytest.mark.parametrize("value", HOSTILE)
@pytest.mark.parametrize("key", ["policy", "version", "agent", "page"])
def test_hostile_values_are_dropped(key, value) -> None:
    for kind_id in KINDS:
        _, query = _url(kind_id, {key: value})
        assert list(query) == ["template"], (kind_id, key, value)


@pytest.mark.parametrize(
    "page",
    [
        "https://evil.example/",
        "//evil.example/",
        "/coding/../x/",
        "/coding",
        "/a/b/c/d/e/",
    ],
)
def test_page_must_be_a_site_path(page) -> None:
    _, query = _url("site-bug", {"page": page})
    assert "page-url" not in query


def test_unknown_agent_and_unknown_keys_are_dropped() -> None:
    _, query = _url("site-bug", {"agent": "other-agent", "body": "x", "title": "x"})
    assert list(query) == ["template"]


def test_report_link_keeps_only_known_id_shaped_values() -> None:
    assert report.report_link() == "/report/"
    assert (
        report.report_link(agent="codex", page="/coding/install/")
        == "/report/?agent=codex&page=%2Fcoding%2Finstall%2F"
    )
    assert (
        report.report_link(policy="<b>", page="https://evil/", title="x") == "/report/"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"repo": "other-repo"},
        {"template": "../x.yml"},
        {"fields": {"policy-id": "body"}},
        {"title": "[x]: {body}"},
        {"id": "Bad Id"},
    ],
)
def test_check_report_refuses_bad_data(change) -> None:
    bad = {**REPORT, "kinds": [{**REPORT["kinds"][0], **change}]}
    with pytest.raises(report.ReportError):
        report.check_report(bad)


def test_site_bug_fields_exist_in_this_repos_form() -> None:
    form = yaml.safe_load(
        (ROOT / ".github" / "ISSUE_TEMPLATE" / "site-bug.yml").read_text(
            encoding="utf-8"
        )
    )
    ids = {item["id"]: item for item in form["body"] if "id" in item}
    assert set(KINDS["site-bug"]["fields"]) <= set(ids)
    assert set(AGENTS) <= set(ids["agent"]["attributes"]["options"])


def test_page_puts_security_first_and_has_every_button(built) -> None:
    html = (built.out / "report" / "index.html").read_text(encoding="utf-8")
    security = html.index('class="report-security"')
    cards = html.index('id="report-cards"')
    assert security < cards
    for advisory in ("chock", "chock-catalog", "chock-site"):
        assert f"open-coder-ai/{advisory}/security/advisories/new" in html
    hrefs = re.findall(r'href="(https://github\.com/[^"]+/issues/new[^"]*)"', html)
    assert len(hrefs) == len(KINDS)
    assert 'src="/js/report.js"' in html
    assert "form-action 'none'" in html


def test_twin_lists_every_form_and_asks_first(built) -> None:
    twin = (built.out / "report" / "index.md").read_text(encoding="utf-8")
    for kind in KINDS.values():
        assert f"{kind['repo']}/issues/new?template={kind['template']}" in twin
    assert "ask before you open an issue" in twin


def test_pages_link_to_the_report_page(built) -> None:
    out = built.out
    policy = (out / "coding" / "policies" / "block-no-verify" / "index.html").read_text(
        encoding="utf-8"
    )
    version = next(p.version for p in built.site.policies if p.id == "block-no-verify")
    assert (
        f'href="/report/?policy=block-no-verify&amp;version={version}'
        '&amp;page=%2Fcoding%2Fpolicies%2Fblock-no-verify%2F"'
    ) in policy
    install = (out / "coding" / "install" / "index.html").read_text(encoding="utf-8")
    for agent in built.site.data["builder_clients"]["order"]:
        assert (
            f'href="/report/?agent={agent}&amp;page=%2Fcoding%2Finstall%2F"' in install
        )
    for page in ("builder", "author"):
        html = (out / "coding" / page / "index.html").read_text(encoding="utf-8")
        assert f'href="/report/?page=%2Fcoding%2F{page}%2F"' in html
    faq = (out / "faq" / "index.html").read_text(encoding="utf-8")
    assert 'href="/report/"' in faq.split("<footer>")[0]
    footer = (out / "index.html").read_text(encoding="utf-8").split("<footer>")[1]
    assert 'href="/report/"' in footer


def test_report_js_uses_no_forbidden_apis() -> None:
    src = (ROOT / "static" / "js" / "report.js").read_text(encoding="utf-8")
    for banned in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "eval(",
        "new Function",
    ):
        assert banned not in src, banned
    assert not re.search(r"setTimeout\s*\(\s*['\"`]", src)
