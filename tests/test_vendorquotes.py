"""The vendor-quote checker: normalising, matching, reporting and recording, with no network."""

import datetime as dt
import json
import shutil
from pathlib import Path

import pytest

from sitegen import vendorquotes as vq
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PAGE = """<html><head><title>Agents</title><style>p { color: red }</style>
<script>var s = "Agents can act on their own.";</script></head><body>
<h1>What agents do</h1>
<p>Agents can <strong>act</strong>&nbsp;on   their
own &mdash; within the <a href="/p">policy&#8217;s</a> limits.</p>
<ul><li>One</li><li>Two</li></ul>
</body></html>"""


def _quote(**fields: str) -> dict[str, str]:
    return {
        "id": "acme",
        "product": "Acme Agents",
        "vendor": "Acme",
        "url": "https://acme.example/agents",
        "quote": "Agents can act on their own - within the policy's limits.",
        "checked": "2026-10-01",
    } | fields


def test_normalize_drops_tags_scripts_and_folds_entities_and_spaces() -> None:
    text = vq.normalize(PAGE)
    assert "Agents can act on their own - within the policy's limits." in text
    assert "var s" not in text and "color" not in text
    assert "One Two" in text


def test_found_matches_across_markup_but_not_changed_wording() -> None:
    assert vq.found(PAGE, "Agents can act on their own — within the policy’s limits.")
    assert not vq.found(PAGE, "Agents can act on their own.")
    assert not vq.found(
        PAGE, "Agents may act on their own - within the policy's limits."
    )


def test_check_fetches_each_page_once_and_reports_every_kind_of_miss() -> None:
    calls: list[str] = []
    pages = {"https://acme.example/agents": PAGE}

    def fetch(url: str) -> str:
        calls.append(url)
        if url not in pages:
            raise OSError("HTTP Error 404: Not Found")
        return pages[url]

    quotes = [
        _quote(),
        _quote(id="acme-2", quote="Agents can act on their own."),
        _quote(id="gone", url="https://acme.example/moved"),
    ]
    results = vq.check(quotes, fetch)
    assert calls == ["https://acme.example/agents", "https://acme.example/moved"]
    assert [(r.id, r.ok) for r in results] == [
        ("acme", True),
        ("acme-2", False),
        ("gone", False),
    ]
    assert results[1].reason == "quote not found on the page"
    assert results[2].reason == "fetch error: OSError: HTTP Error 404: Not Found"
    assert vq.report(results) == {
        "verified": ["acme"],
        "broken": [
            {"id": "acme-2", "reason": "quote not found on the page"},
            {"id": "gone", "reason": "fetch error: OSError: HTTP Error 404: Not Found"},
        ],
    }


def test_issue_body_lists_exactly_the_broken_quotes_with_links() -> None:
    quotes = [_quote(), _quote(id="gone", url="https://acme.example/moved")]
    results = [vq.Result("acme", True), vq.Result("gone", False, "quote not found")]
    body = vq.issue_body(quotes, results, "https://github.com/o/r/actions/runs/1")
    assert "found 1 of 2 quotes" in body
    assert "(`gone`)" in body and "https://acme.example/moved" in body
    assert "(`acme`)" not in body
    assert body.endswith("Run: https://github.com/o/r/actions/runs/1\n")


def test_record_sets_today_on_verified_quotes_only(tmp_path: Path) -> None:
    shutil.copy(DATA / vq.QUOTES_JSON, tmp_path / vq.QUOTES_JSON)
    before = vq.load(tmp_path)
    first = before[0]["id"]
    assert vq.record(tmp_path, [first], "2027-01-05") == [first]
    after = vq.load(tmp_path)
    assert after[0]["checked"] == "2027-01-05"
    assert after[1:] == before[1:]
    assert vq.record(tmp_path, [first], "2027-01-05") == []
    with pytest.raises(PageError, match="no quote with id"):
        vq.record(tmp_path, ["nobody"], "2027-01-05")
    with pytest.raises(PageError, match="YYYY-MM-DD"):
        vq.record(tmp_path, [first], "5 Jan 2027")


def test_is_stale_after_183_days() -> None:
    assert not vq.is_stale("2026-01-01", dt.date(2026, 7, 3))
    assert vq.is_stale("2026-01-01", dt.date(2026, 7, 4))


def test_load_refuses_incomplete_duplicate_insecure_or_undated_quotes(
    tmp_path: Path,
) -> None:
    def write(quotes: list[dict[str, str]]) -> None:
        (tmp_path / vq.QUOTES_JSON).write_text(json.dumps({"quotes": quotes}))

    for quotes, message in [
        ([_quote() | {"extra": "x"}], "needs exactly"),
        ([_quote(), _quote()], "appears twice"),
        ([_quote(url="http://acme.example")], "https"),
        ([_quote(quote=" ")], "empty quote"),
        ([_quote(checked="2026-1-1")], "YYYY-MM-DD"),
    ]:
        write(quotes)
        with pytest.raises(PageError, match=message):
            vq.load(tmp_path)


def test_cli_check_then_record_with_a_stub_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / vq.QUOTES_JSON).write_text(
        json.dumps({"quotes": [_quote(), _quote(id="gone", url="https://x.example/")]})
    )
    monkeypatch.setattr(
        vq, "fetch_url", lambda url: PAGE if "acme" in url else "<p>moved</p>"
    )
    report, body = tmp_path / "report.json", tmp_path / "issue.md"
    args = ["--data", str(tmp_path), "check", "--report", str(report)]
    assert vq.main([*args, "--issue-body", str(body)]) == 0
    assert json.loads(report.read_text())["verified"] == ["acme"]
    assert "(`gone`)" in body.read_text()
    record = ["--data", str(tmp_path), "record", "--verified", "acme"]
    assert vq.main([*record, "--date", "2026-10-20"]) == 0
    assert vq.main([*record[:-1], "acme nobody", "--date", "2026-10-20"]) == 2
    checked = {q["id"]: q["checked"] for q in vq.load(tmp_path)}
    assert checked == {"acme": "2026-10-20", "gone": "2026-10-01"}
