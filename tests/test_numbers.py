"""LN-3: every policy, tier, eval and agent count on the site is derived, and says what it leaves out.

The rule (orchestrator decision, 2026-11-11): a count covers registry.yaml at .catalog-ref minus
the policies the site does not show (data/hidden.yaml, and a manifest whose lifecycle status is
deprecated or retired). Tested and untested agents are the engine's own.
"""

import html
import re
from collections import Counter
from pathlib import Path

import yaml

from sitegen import engine

ROOT = Path(__file__).resolve().parents[1]
# chock's docs/assets/readme/derive.py reads a tier from the first word of `enforces`.
README_TIER = {
    "enforced-at-commit": "commit",
    "best-effort": "agent",
    "advisory": "advise",
}
NOT_COUNTED = {"deprecated", "retired"}
TAGS = re.compile(r"<[^>]+>")
COUNTED_PAGES = ("index.html", "coding/index.html", "repos/index.html")


def _registry(catalog_path: Path) -> list[dict]:
    text = (catalog_path / "registry.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)["policies"]


def _counted(catalog_path: Path) -> list[dict]:
    """The registry rows a count covers, read without sitegen."""
    hidden = yaml.safe_load((ROOT / "data" / "hidden.yaml").read_text("utf-8"))
    rows = []
    for row in _registry(catalog_path):
        manifest = yaml.safe_load(
            (catalog_path / row["path"] / "manifest.yaml").read_text("utf-8")
        )
        status = (manifest.get("lifecycle") or {}).get("status")
        if row["id"] not in hidden["hidden"] and status not in NOT_COUNTED:
            rows.append(row)
    return rows


def _tiers(rows: list[dict]) -> Counter:
    return Counter(README_TIER[row["enforces"].split(" ")[0]] for row in rows)


def _text(path: Path) -> str:
    """A page's visible text on one line."""
    page = TAGS.sub(" ", path.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", html.unescape(page))


def test_the_site_shows_the_registry_minus_hidden_and_deprecated(
    built, catalog_path
) -> None:
    site = built.site
    counted = {row["id"] for row in _counted(catalog_path)}
    every = {row["id"] for row in _registry(catalog_path)}
    assert {p.id for p in site.policies} == counted
    assert set(site.data["not_shown"]) == every - counted


def test_pages_state_the_derived_policy_tier_and_eval_counts(
    built, catalog_path
) -> None:
    rows = _counted(catalog_path)
    total, tiers = len(rows), _tiers(rows)
    executed = sum(row["eval_executed"] for row in rows)
    home = _text(built.out / "index.html")
    assert f"{total} POLICIES · {executed:,} TESTS" in home
    assert f"Policies {total} " in home
    assert (
        f"At commit {tiers['commit']} In agent {tiers['agent']} Advisory {tiers['advise']}"
        in home
    )
    assert f"See all {total} policies" in home
    assert f"{total} Policies" in _text(built.out / "coding" / "index.html")
    assert f"{total} guardrails" in _text(
        built.out / "coding" / "policies" / "index.html"
    )
    repos = _text(built.out / "repos" / "index.html")
    assert f"{tiers['commit']} ■ At commit" in repos
    assert f"{tiers['agent']} ◆ In agent" in repos
    assert f"{tiers['advise']} ○ Advisory" in repos
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    assert f"holds {total} policies" in llms
    twin = (built.out / "index.md").read_text(encoding="utf-8")
    assert f"{total} policies · {executed:,} tests" in twin


def test_each_policy_page_states_its_registry_eval_counts(built, catalog_path) -> None:
    for row in _counted(catalog_path):
        page = _text(built.out / "coding" / "policies" / row["id"] / "index.html")
        assert f"{row['eval_executed']} of {row['eval_cases']}" in page, row["id"]


def test_a_page_with_counts_says_what_they_leave_out(built, catalog_path) -> None:
    counted = _counted(catalog_path)
    every = _registry(catalog_path)
    left_out = sorted({r["id"] for r in every} - {r["id"] for r in counted})
    assert left_out, (
        "the pinned catalog has no deprecated policy; this rule shows nowhere"
    )
    rule = (
        "Counts leave out deprecated policies, so they cover "
        f"{len(counted)} of the {len(every)} in the catalog's registry.yaml "
        f"(not counted: {', '.join(left_out)})."
    )
    for page in COUNTED_PAGES:
        assert rule in _text(built.out / page), page
    for twin in ("coding/index.md", "repos/index.md"):
        assert rule in (built.out / twin).read_text(encoding="utf-8"), twin
    listed = _text(built.out / "coding" / "policies" / "index.html")
    assert f"The catalog has {len(every)} policies." in listed
    for policy_id in left_out:
        assert policy_id in listed


def test_tested_and_untested_agents_are_the_engines(built) -> None:
    """chock's README counts a client untested when the engine's own warning says so."""
    clients = built.site.data["builder_clients"]["clients"]
    untested = [c for c, about in clients.items() if about["witness"] == "untested"]
    assert sorted(untested) == sorted(engine.untested_clients())
    assert sorted(clients) == sorted(engine.client_ids())
    assert f"Agents {len(clients)} " in _text(built.out / "index.html")
