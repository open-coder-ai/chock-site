"""The Cloudflare Pages _headers file and the workflow hardening."""

import re
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ROOT / "deploy" / "_headers"
WORKFLOWS = ROOT / ".github" / "workflows"
PINNED = re.compile(r"^\s*(?:- )?uses: [\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d")


class _MetaCsp(HTMLParser):
    """Reads the CSP <meta> tag from one HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.csp = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            self.csp = attrs.get("content", "")


def _rules(text: str) -> dict[str, dict[str, str]]:
    """Parse a _headers file into {url pattern: {header name: value}}."""
    rules: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            current = rules.setdefault(line.strip(), {})
            continue
        assert current is not None, line
        name, _, value = line.strip().partition(":")
        assert name not in current, name
        current[name] = value.strip()
    return rules


def test_dist_has_headers(built) -> None:
    assert (built.out / "_headers").read_bytes() == HEADERS.read_bytes()


def test_headers_csp_is_meta_csp_plus_frame_ancestors(built) -> None:
    parser = _MetaCsp()
    parser.feed((built.out / "index.html").read_text(encoding="utf-8"))
    assert parser.csp
    csp = _rules(HEADERS.read_text(encoding="utf-8"))["/*"]["Content-Security-Policy"]
    assert csp == parser.csp + "; frame-ancestors 'none'"


def test_headers_hardening_and_noindex() -> None:
    text = HEADERS.read_text(encoding="utf-8")
    rules = _rules(text)
    every = rules["/*"]
    assert every["X-Content-Type-Options"] == "nosniff"
    assert every["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert every["Cross-Origin-Opener-Policy"] == "same-origin"
    for feature in ("camera", "microphone", "geolocation", "payment"):
        assert f"{feature}=()" in every["Permissions-Policy"]
    assert rules["https://:project.pages.dev/*"] == {"X-Robots-Tag": "noindex"}
    assert rules["https://:version.:project.pages.dev/*"] == {"X-Robots-Tag": "noindex"}
    assert rules["https://staging.chock.sh/*"] == {"X-Robots-Tag": "noindex"}
    assert "Strict-Transport-Security" not in text
    for folder in ("css", "js", "img", "fonts"):
        assert rules[f"/{folder}/*"] == {"Cache-Control": "public, max-age=300"}
    # Cloudflare Pages limits: 100 rules, 2000 characters per line.
    assert len(rules) <= 100
    assert max(len(line) for line in text.splitlines()) <= 2000


def test_noindex_covers_pages_dev_and_staging_only() -> None:
    """Only the pages.dev and staging hosts get noindex; the production hosts never do."""
    rules = _rules(HEADERS.read_text(encoding="utf-8"))
    noindex = {
        pattern for pattern, headers in rules.items() if "X-Robots-Tag" in headers
    }
    assert noindex == {
        "https://:project.pages.dev/*",
        "https://:version.:project.pages.dev/*",
        "https://staging.chock.sh/*",
    }
    for pattern in rules:
        assert not pattern.startswith(("https://chock.sh", "https://www.chock.sh")), (
            pattern
        )


ALLOWED_JOB_PERMISSIONS = {
    "ci.yml": {},
    "vendor-quotes.yml": {
        "check": {"contents": "read", "issues": "write"},
        "record": {"contents": "write", "pull-requests": "write"},
    },
}


def test_workflows_are_pinned_and_least_privilege() -> None:
    """Every workflow is read-only at the top and SHA-pinned; write permissions exist only in the
    jobs the allowlist names, with exactly what they declare. A new workflow, job or permission fails here."""
    paths = sorted(WORKFLOWS.glob("*.yml"))
    assert [p.name for p in paths] == sorted(ALLOWED_JOB_PERMISSIONS)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        flow = yaml.safe_load(text)
        assert flow["permissions"] in ({"contents": "read"}, {}), path.name
        allowed = ALLOWED_JOB_PERMISSIONS[path.name]
        assert set(allowed) <= set(flow["jobs"]), path.name
        for name, job in flow["jobs"].items():
            assert job.get("permissions", {}) == allowed.get(name, {}), (
                path.name,
                name,
            )
            assert "environment" not in job, path.name
        assert "pull_request_target" not in text, path.name
        assert "secrets." not in text, path.name
        for line in text.splitlines():
            if "uses:" in line:
                assert PINNED.match(line), line


def test_every_checkout_drops_credentials() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        flow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in flow["jobs"].values():
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] is False, path.name
