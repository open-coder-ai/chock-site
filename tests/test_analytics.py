"""Site events (plan AN-1): the allowlist data, the generated module and the Security page section."""

import copy
import html
import re
from pathlib import Path

import pytest
import yaml

from sitegen import analytics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
# Every event the plan's table names, with the keys it carries.
EXPECTED = {
    "install-copied": ["agent"],
    "share-copied": [],
    "selection-downloaded": [],
    "quiz-finished": [],
    "preset-picked": ["preset"],
    "author-script-downloaded": ["kind", "agent"],
    "report-form-opened": ["form"],
    "policy-build-clicked": ["policy", "agent"],
}


@pytest.fixture
def data() -> dict:
    """analytics.yaml, loaded and checked."""
    return analytics.load(DATA)


def test_allowlist_is_the_planned_events(data) -> None:
    assert {name: e["props"] for name, e in data["events"].items()} == EXPECTED
    assert data["keys"] == ["agent", "kind", "preset", "policy", "form"]
    assert data["value"] == "^[a-z0-9.-]{1,64}$"
    assert data["max_body"] == 1024


def test_value_pattern_accepts_ids_only(data) -> None:
    value = re.compile(data["value"])
    for good in ("claude-code", "git-hygiene", "content-regex", "v1.2", "a" * 64):
        assert value.fullmatch(good), good
    for bad in ("", "a" * 65, "Claude", "a b", "a_b", "<x>", "a/b", "#s=x", "é", "a\n"):
        assert not value.fullmatch(bad), bad


def test_committed_module_matches_data(data) -> None:
    current = (ROOT / analytics.ALLOWLIST).read_text(encoding="utf-8")
    assert current == analytics.module_text(data)
    analytics.check_module(data, ROOT)


def test_stale_module_refuses_the_build(data, tmp_path) -> None:
    changed = copy.deepcopy(data)
    changed["events"]["extra-event"] = {"props": [], "what": "x"}
    with pytest.raises(analytics.AnalyticsError, match="python -m sitegen allowlist"):
        analytics.check_module(changed, ROOT)
    with pytest.raises(analytics.AnalyticsError):
        analytics.check_module(data, tmp_path)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda d: d["events"].update({"Bad_Name": {"props": [], "what": "x"}}),
            "not an id",
        ),
        (lambda d: d["events"]["share-copied"].update(props=["url"]), "not in keys"),
        (
            lambda d: d["events"]["share-copied"].update(props=["agent", "agent"]),
            "not in keys",
        ),
        (lambda d: d["events"]["share-copied"].update(what=""), "missing what"),
        (lambda d: d.update(value="[a-z]+"), "anchored"),
        (lambda d: d.update(value="^[a-z$"), "not a pattern"),
        (lambda d: d.update(max_body=4096), "max_body"),
        (lambda d: d.update(keys=["agent", "agent"]), "keys"),
        (lambda d: d.update(events={}), "no events"),
    ],
)
def test_bad_data_is_refused(tmp_path, change, message) -> None:
    raw = yaml.safe_load((DATA / analytics.DATA_FILE).read_text(encoding="utf-8"))
    change(raw)
    (tmp_path / analytics.DATA_FILE).write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(analytics.AnalyticsError, match=message):
        analytics.load(tmp_path)


def test_build_ships_the_same_module(built) -> None:
    shipped = (built.out / analytics.DIST_ALLOWLIST).read_text(encoding="utf-8")
    assert shipped == (ROOT / analytics.ALLOWLIST).read_text(encoding="utf-8")


def test_security_page_lists_every_event(built, data) -> None:
    page = (built.out / "security" / "index.html").read_text(encoding="utf-8")
    twin = (built.out / "security" / "index.md").read_text(encoding="utf-8")
    assert 'id="what-this-site-counts"' in page
    assert "## What this site counts" in twin
    for event in data["events"].values():
        assert f"<li>{html.escape(event['what'])}</li>" in page
        assert f"- {event['what']}\n" in twin
    for text in (page, twin):
        assert "Global Privacy Control" in text
        assert "sends nothing" in text
        assert "no analytics" not in text.lower()


# ----- page views (plan AN-2) -----

BEACON_SCRIPT = "https://static.cloudflareinsights.com"
BEACON_CONNECT = "https://cloudflareinsights.com"
TOKEN_META = re.compile(r'<meta name="web-analytics-token" content="([^"]*)">')


def _directive(csp: str, name: str) -> list[str]:
    """The sources of one CSP directive."""
    for part in csp.split(";"):
        words = part.split()
        if words and words[0] == name:
            return words[1:]
    raise AssertionError(name)


def test_site_json_token_is_empty_until_the_owner_adds_it() -> None:
    import json

    site = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
    assert site["web_analytics_token"] == ""


def test_pages_carry_the_token_meta_and_no_beacon_script(built) -> None:
    for path in ("index.html", "security/index.html", "coding/builder/index.html"):
        page = (built.out / path).read_text(encoding="utf-8")
        assert TOKEN_META.findall(page) == [""], path
        assert "cloudflareinsights.com/beacon" not in page, path
        assert "data-cf-beacon" not in page, path


def test_csp_adds_exactly_the_two_beacon_origins(built) -> None:
    page = (built.out / "index.html").read_text(encoding="utf-8")
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', page)[1]
    assert _directive(csp, "script-src") == ["'self'", BEACON_SCRIPT]
    assert _directive(csp, "connect-src") == ["'self'", BEACON_CONNECT]
    for name in ("default-src", "style-src", "img-src", "font-src", "object-src"):
        assert BEACON_SCRIPT not in _directive(csp, name), name
        assert BEACON_CONNECT not in _directive(csp, name), name
    assert (built.out / "_headers").read_text(encoding="utf-8").count(
        BEACON_SCRIPT
    ) == 1


def test_security_text_says_page_views_honour_gpc_and_dnt(built, data) -> None:
    sentence = (
        "Page views are counted with Cloudflare Web Analytics, which sets no cookie. "
        "It records the page address, referrer, country and browser type in aggregate. "
        "It does not load when your browser sends Global Privacy Control or Do Not Track."
    )
    assert sentence in data["security"]["body"]
    page = (built.out / "security" / "index.html").read_text(encoding="utf-8")
    twin = (built.out / "security" / "index.md").read_text(encoding="utf-8")
    assert html.escape(sentence, quote=False) in page.replace("&#x27;", "'")
    assert sentence in twin


@pytest.mark.parametrize("token", ["abc", "G" * 32, "a" * 33, '"><script>x</script>'])
def test_a_bad_token_refuses_the_build(token) -> None:
    from sitegen.model import Site
    from sitegen.pageparts import PageError, web_analytics_token

    site = Site.__new__(Site)
    site.data = {"web_analytics_token": token}
    with pytest.raises(PageError):
        web_analytics_token(site)


def test_a_good_token_is_accepted() -> None:
    from sitegen.model import Site
    from sitegen.pageparts import web_analytics_token

    site = Site.__new__(Site)
    site.data = {"web_analytics_token": "0123456789abcdef" * 2}
    assert web_analytics_token(site) == "0123456789abcdef" * 2


def test_stats_scripts_read_the_token_from_the_environment() -> None:
    for name in ("stats.sh", "stats.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "CF_API_TOKEN" in text and "CF_ACCOUNT_ID" in text, name
        assert "chock_site_events" in text, name
        assert "analytics_engine/sql" in text, name
