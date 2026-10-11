"""Playwright fixtures: build the site once and serve it on a free local port."""

import json
import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from sitegen.__main__ import build, make_server

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / ".catalog"
SCREENSHOTS = ROOT / "test-results" / "screenshots"
NON_REQUEST_SCHEMES = ("data", "about", "blob")


@pytest.fixture(scope="session")
def site_url(tmp_path_factory: pytest.TempPathFactory):
    """The URL of the once-built site, served on 127.0.0.1 for the session."""
    assert CATALOG.is_dir(), "clone chock-catalog into .catalog (see README)"
    out = tmp_path_factory.mktemp("site")
    build(CATALOG, out, str(CATALOG.resolve()), None)
    server = make_server(out, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=10)


_PROBLEMS: dict[int, list[str]] = {}


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def collect(page: Any, site_url: str) -> None:
    """Attach listeners that record console errors, failed and foreign requests."""
    problems: list[str] = []
    allowed = _origin(site_url)

    def _is_foreign(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme in NON_REQUEST_SCHEMES:
            return False
        return _origin(url) != allowed

    page.on(
        "console",
        lambda msg: (
            problems.append(f"console error: {msg.text}")
            if msg.type == "error"
            else None
        ),
    )
    page.on(
        "requestfailed",
        lambda req: problems.append(f"request failed: {req.url} {req.failure}"),
    )
    page.on(
        "request",
        lambda req: (
            problems.append(f"foreign request: {req.url}")
            if _is_foreign(req.url)
            else None
        ),
    )
    _PROBLEMS[id(page)] = problems


@pytest.fixture(autouse=True)
def _watch(page, site_url) -> None:
    collect(page, site_url)


def assert_clean(page: Any) -> None:
    """Fail on any recorded console error, failed request or non-local request."""
    problems = _PROBLEMS.get(id(page))
    assert problems is not None, "call collect(page) before assert_clean"
    assert not problems, "\n".join(problems)


def screenshot(page: Any, name: str) -> None:
    """A full-page screenshot under test-results/screenshots/<name>.png."""
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENSHOTS / f"{name}.png"), full_page=True)


POLICY_PAGE = re.compile(r"^/coding/policies/[^/]+/$")


def walk_paths(page: Any, site_url: str) -> list[str]:
    """Pages a site-wide walk visits: every sitemap page, with policy pages sampled.

    The policy pages share one template, so the walk takes one per label kind
    plus the one with the longest says text, then adds the 404 page and the
    full builder with a preset.
    """
    xml = page.request.get(site_url + "/sitemap.xml").text()
    paths = [
        loc[len("https://chock.sh") :] for loc in re.findall(r"<loc>([^<]+)</loc>", xml)
    ]
    policies = json.loads(page.request.get(site_url + "/data/site.json").text())[
        "policies"
    ]
    sample: list[str] = []
    for keyword in ("block", "ask", "warn", "advise"):
        sample.append(next(p["id"] for p in policies if p["keyword"] == keyword))
    sample.append(max(policies, key=lambda p: len(p["says"]))["id"])
    kept = [path for path in paths if not POLICY_PAGE.match(path)]
    kept += [f"/coding/policies/{pid}/" for pid in dict.fromkeys(sample)]
    return kept + ["/404.html", "/coding/builder/#preset=git-hygiene"]
