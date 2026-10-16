"""Vendor quotes on "Where Chock sits": data/vendor-quotes.json, checked against their pages.

Each quote is one sentence from a vendor's own page, with that page's URL and the date
the sentence was last found there (`checked`). The weekly workflow
(.github/workflows/vendor-quotes.yml) runs:

    python -m sitegen.vendorquotes check --report report.json --issue-body issue.md
    python -m sitegen.vendorquotes record --verified "id id ..." --date YYYY-MM-DD

`check` fetches every page and reports which quotes still appear, after normalising
HTML and whitespace; `record` sets `checked` on the quotes that did. Tests pass their
own fetch function, so nothing here touches the network under test.
"""

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .pageparts import PageError

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
QUOTES_JSON = "vendor-quotes.json"
FIELDS = {"id", "product", "vendor", "url", "quote", "checked"}
# A quote last found longer ago than this renders with an out-of-date note.
STALE_DAYS = 183
MAX_BYTES = 5_000_000
USER_AGENT = "chock-site-vendor-quotes/1 (+https://github.com/open-coder-ai/chock-site)"

_DROP_RE = re.compile(
    r"<!--.*?-->|<(script|style|noscript|template)\b.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_BLOCK_RE = re.compile(
    r"</?(?:p|div|li|ul|ol|br|hr|h[1-6]|tr|td|th|table|section|article|header|footer"
    r"|nav|main|aside|blockquote|figure|figcaption|dt|dd|dl|pre)\b[^>]*>",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]*>")
_FOLD = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
        "\u200b": "",
        "\u00ad": "",
    }
)

Fetch = Callable[[str], str]


@dataclass(frozen=True)
class Result:
    """One quote's outcome: found on its page, or why not."""

    id: str
    ok: bool
    reason: str = ""


def load(data_dir: Path = DATA) -> list[dict[str, str]]:
    """data/vendor-quotes.json, refused unless every quote is complete, https and dated."""
    quotes = json.loads((data_dir / QUOTES_JSON).read_text(encoding="utf-8"))["quotes"]
    seen: set[str] = set()
    for q in quotes:
        name = q.get("id", "?")
        if set(q) != FIELDS:
            raise PageError(f"{QUOTES_JSON}: {name!r} needs exactly {sorted(FIELDS)}")
        if name in seen:
            raise PageError(f"{QUOTES_JSON}: {name!r} appears twice")
        seen.add(name)
        if not q["url"].startswith("https://"):
            raise PageError(f"{QUOTES_JSON}: {name!r} needs an https source")
        if not q["quote"].strip():
            raise PageError(f"{QUOTES_JSON}: {name!r} has an empty quote")
        parse_date(q["checked"], name)
    return quotes


def parse_date(value: str, name: str) -> dt.date:
    """A YYYY-MM-DD date, or a PageError naming the quote."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise PageError(f"{QUOTES_JSON}: {name!r} checked must be YYYY-MM-DD")
    return dt.date.fromisoformat(value)


def is_stale(checked: str, today: dt.date) -> bool:
    """True when a quote was last found more than STALE_DAYS days before today."""
    return (today - dt.date.fromisoformat(checked)).days > STALE_DAYS


def normalize(text: str) -> str:
    """Page or quote text with tags dropped, entities decoded, punctuation and spaces folded."""
    text = _DROP_RE.sub(" ", text)
    text = _BLOCK_RE.sub(" ", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text).translate(_FOLD)
    return " ".join(text.split())


def found(page: str, quote: str) -> bool:
    """True when the quote appears in the page, both normalised."""
    return normalize(quote) in normalize(page)


def fetch_url(url: str) -> str:
    """The page at an https URL, as text."""
    if not url.startswith("https://"):
        raise ValueError(f"not https: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(MAX_BYTES + 1)
        charset = response.headers.get_content_charset() or "utf-8"
    if len(body) > MAX_BYTES:
        raise ValueError(f"page larger than {MAX_BYTES} bytes")
    return body.decode(charset, errors="replace")


def check(quotes: list[dict[str, str]], fetch: Fetch | None = None) -> list[Result]:
    """Each quote's result, fetching every distinct page once."""
    fetch = fetch or fetch_url
    pages: dict[str, str | Exception] = {}
    results = []
    for q in quotes:
        if q["url"] not in pages:
            try:
                pages[q["url"]] = fetch(q["url"])
            except Exception as exc:  # noqa: BLE001 (any fetch failure is a broken quote)
                pages[q["url"]] = exc
        page = pages[q["url"]]
        if isinstance(page, Exception):
            reason = f"fetch error: {type(page).__name__}: {page}"
            results.append(Result(q["id"], False, reason))
        elif found(page, q["quote"]):
            results.append(Result(q["id"], True))
        else:
            results.append(Result(q["id"], False, "quote not found on the page"))
    return results


def issue_body(
    quotes: list[dict[str, str]], results: list[Result], run_url: str = ""
) -> str:
    """The Markdown body of the one tracking issue: every broken quote, with its link."""
    by_id = {q["id"]: q for q in quotes}
    broken = [r for r in results if not r.ok]
    intro = (
        f"The weekly vendor-quote check found {len(broken)} of {len(results)} quotes "
        "no longer on their pages. Each one needs a new sentence from the vendor's "
        f"current page, or removing, in `data/{QUOTES_JSON}`."
    )
    lines = [intro, ""]
    for r in broken:
        q = by_id[r.id]
        lines += [
            f"- **{q['product']}** (`{r.id}`), last found {q['checked']}: {r.reason}",
            f"  - Page: {q['url']}",
            f"  - Quote: {json.dumps(q['quote'], ensure_ascii=False)}",
        ]
    if run_url:
        lines += ["", f"Run: {run_url}"]
    return "\n".join(lines) + "\n"


def record(data_dir: Path, ids: list[str], date: str) -> list[str]:
    """Set `checked` to date on the given quotes; return the ids whose date changed."""
    parse_date(date, "--date")
    path = data_dir / QUOTES_JSON
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {q["id"] for q in data["quotes"]}
    unknown = sorted(set(ids) - known)
    if unknown:
        raise PageError(f"{QUOTES_JSON}: no quote with id {unknown}")
    changed = []
    for q in data["quotes"]:
        if q["id"] in ids and q["checked"] != date:
            q["checked"] = date
            changed.append(q["id"])
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return changed


def report(results: list[Result]) -> dict[str, Any]:
    """The check's results as JSON: verified ids and broken ids with reasons."""
    return {
        "verified": [r.id for r in results if r.ok],
        "broken": [{"id": r.id, "reason": r.reason} for r in results if not r.ok],
    }


def main(argv: list[str] | None = None) -> int:
    """`check` the quotes against their pages, or `record` the dates of those verified."""
    parser = argparse.ArgumentParser(prog="python -m sitegen.vendorquotes")
    parser.add_argument("--data", type=Path, default=DATA)
    sub = parser.add_subparsers(dest="command", required=True)
    check_cmd = sub.add_parser("check")
    check_cmd.add_argument("--report", type=Path, required=True)
    check_cmd.add_argument("--issue-body", type=Path, required=True)
    check_cmd.add_argument("--run-url", default="")
    record_cmd = sub.add_parser("record")
    record_cmd.add_argument("--verified", required=True, help="space-separated ids")
    record_cmd.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    try:
        quotes = load(args.data)
        if args.command == "check":
            results = check(quotes)
            args.report.write_text(json.dumps(report(results), indent=2) + "\n")
            args.issue_body.write_text(issue_body(quotes, results, args.run_url))
            for r in results:
                print(f"{'ok    ' if r.ok else 'BROKEN'} {r.id} {r.reason}".rstrip())
            return 0
        changed = record(args.data, args.verified.split(), args.date)
        print(f"checked set to {args.date} on: {', '.join(changed) or 'none'}")
        return 0
    except (PageError, OSError, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
