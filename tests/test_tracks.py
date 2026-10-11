"""Plan 0.1 checks: tracks.yaml fields, track on records, top-level paths, additivity."""

import dataclasses
import json
import re
from pathlib import Path

import pytest
import yaml

from sitegen import pages as pages_mod
from sitegen.__main__ import TEMPLATES
from sitegen.model import SectionResult, Site, Track
from sitegen.pageparts import write_md, write_page
from sitegen.render import Safe

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = {"id", "slug", "title", "status", "summary"}
STATUSES = {"available", "in_design"}
# Plan 0.1 rule 5: the root holds only section slugs and these shared paths.
SHARED_TOP_LEVEL = {
    "index.html",
    "index.md",
    "404.html",
    "404.md",
    "faq",
    "security",
    "for-agents",
    "report",
    "llms.txt",
    "llms-full.txt",
    "sitemap.xml",
    "robots.txt",
    "favicon.svg",
    "api",
    "css",
    "js",
    "img",
    "fonts",
    "video",
    "data",
    # The plan-4 output-safety marker; a build artefact, not a page.
    ".sitegen-output",
    # Cloudflare Pages response headers (DEPLOY-1); read by the host, not a page.
    "_headers",
    # The release version marker (REL-3), read by the release check.
    "version.json",
}
EXAMPLE = Track(
    id="example",
    slug="example",
    title="Example agents",
    status="in_design",
    summary="A stub section that exists only in this test fixture.",
)


def _site_json(built) -> dict:
    return json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))


def test_tracks_yaml_has_every_field() -> None:
    rows = yaml.safe_load((ROOT / "data" / "tracks.yaml").read_text(encoding="utf-8"))
    assert rows["tracks"], "tracks.yaml is empty"
    ids = set()
    for row in rows["tracks"]:
        missing = REQUIRED_FIELDS - set(row)
        assert not missing, f"track {row.get('id')}: missing {missing}"
        assert all(str(row[f]).strip() for f in REQUIRED_FIELDS), row["id"]
        assert row["id"] not in ids, f"duplicate track id {row['id']}"
        ids.add(row["id"])
        assert row["id"] != "common", "common is the shared FAQ group, not a track"
        assert row["status"] in STATUSES, row


def test_tracks_carried_into_site_json_and_api_index(built) -> None:
    data = _site_json(built)
    assert [t["id"] for t in data["tracks"]] == ["coding", "general", "repos"]
    assert data["tracks"][0]["status"] == "available"
    assert data["tracks"][1]["status"] == "in_design"
    assert data["tracks"][2]["status"] == "available"
    index = json.loads((built.out / "api" / "index.json").read_text(encoding="utf-8"))
    assert [t["id"] for t in index["tracks"]] == ["coding", "general", "repos"]
    assert index["tracks"][0] == {
        "id": "coding",
        "title": "Coding agents",
        "home": "/coding/",
        "status": "available",
        "api": "/api/coding/",
    }
    assert index["tracks"][1] == {
        "id": "general",
        "title": "General agents",
        "home": "/general/",
        "status": "in_design",
    }


def test_general_page_is_the_fixed_placeholder(built) -> None:
    page = (built.out / "general" / "index.html").read_text(encoding="utf-8")
    main = re.search(r'<main id="content">(.*?)</main>', page, re.DOTALL).group(1)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", main)).strip()
    assert text == (
        "DESIGN IN PROGRESS General agents Guardrails for agents that act "
        "for a person or a business. Design in progress. There is nothing "
        "to install yet. Follow open-coder-ai on GitHub"
    )
    banned = ("deny", "step_up", "modify", "profile", "approval", "specification")
    for word in banned:
        assert word not in main.lower(), word
    assert not (built.out / "api" / "general").exists()
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    assert "General agents](/general/index.md): design in progress" in llms
    twin = (built.out / "general" / "index.md").read_text(encoding="utf-8")
    assert "design in progress" in twin.lower()


def test_every_record_carries_track(built) -> None:
    data = _site_json(built)
    for policy in data["policies"]:
        assert policy["track"] == "coding", policy["id"]
    catalog = json.loads(
        (built.out / "api" / "coding" / "catalog.json").read_text(encoding="utf-8")
    )
    assert catalog["track"] == "coding"
    for policy in catalog["policies"]:
        assert policy["track"] == "coding", policy["id"]
    for single in (built.out / "api" / "coding" / "policies").glob("*.json"):
        record = json.loads(single.read_text(encoding="utf-8"))
        assert record["track"] == "coding", single.name
    for twin in (built.out / "coding" / "policies").glob("*/index.md"):
        front = twin.read_text(encoding="utf-8").split("---", 2)[1]
        assert re.search(r"^track: coding$", front, re.MULTILINE), twin


def test_label_words_keyed_by_section(built) -> None:
    data = _site_json(built)
    assert set(data["label_words"]) == {"coding", "repos"}
    assert data["label_words"]["coding"]["block"] == "blocks"
    assert data["label_words"]["repos"] == {
        "commit": "at commit",
        "agent": "in agent",
        "advise": "advisory",
    }
    catalog = json.loads(
        (built.out / "api" / "coding" / "catalog.json").read_text(encoding="utf-8")
    )
    assert set(catalog["label_words"]) == {"coding"}


def test_top_level_paths_are_sections_or_shared(built) -> None:
    slugs = {t.slug for t in built.site.tracks}
    for entry in built.out.iterdir():
        assert entry.name in SHARED_TOP_LEVEL | slugs, f"unexpected {entry.name}"


def _stub_build(site: Site, track: Track, out_dir: Path, templates: Path):
    """A one-page stub section, only ever registered inside this fixture."""
    write_page(
        site,
        out_dir,
        templates,
        path=f"/{track.slug}/",
        title=track.title,
        description=track.summary,
        content=Safe(f"<h1>{track.title}</h1>"),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": track.title,
            "description": track.summary,
        },
    )
    twin = f"# {track.title}\n\n{track.summary}\n"
    write_md(out_dir, f"/{track.slug}/", twin)
    return SectionResult(
        pages=[f"/{track.slug}/"],
        llms=(
            f"## {track.title}\n\n"
            f"- [{track.title} home](/{track.slug}/index.md): {track.summary}\n"
        ),
        docs=[(f"/{track.slug}/index.md", twin)],
    )


def _strip_shell(text: str) -> str:
    """Remove the shared header and footer, the chrome a second section changes."""
    text = re.sub(r"<header>.*?</header>\n", "", text, flags=re.DOTALL)
    return re.sub(r"<footer>.*?</footer>", "", text, flags=re.DOTALL)


@pytest.fixture()
def two_section_build(built, tmp_path, monkeypatch) -> Path:
    """The same site plus one stub section, built into a scratch directory."""
    site = dataclasses.replace(built.site, tracks=[*built.site.tracks, EXAMPLE])
    monkeypatch.setitem(pages_mod.SECTION_BUILDERS, "example", _stub_build)
    out = tmp_path / "two-sections"
    out.mkdir()
    pages_mod.write_pages(site, out, TEMPLATES)
    return out


def test_stub_section_appears_in_shared_outputs(built, two_section_build) -> None:
    out = two_section_build
    index = json.loads((out / "api" / "index.json").read_text(encoding="utf-8"))
    assert [t["id"] for t in index["tracks"]] == [
        "coding",
        "general",
        "repos",
        "example",
    ]
    assert index["tracks"][3]["home"] == "/example/"
    llms = (out / "llms.txt").read_text(encoding="utf-8")
    assert "## Example agents" in llms
    assert (
        llms.index("## Coding agents: policies")
        < llms.index("## Example agents")
        < llms.index("## Data")
    )
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://chock.sh/example/" in sitemap
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="/example/"' in home
    assert "Example agents" in home
    nav = re.search(r'<nav id="nav-links".*?</nav>', home, re.DOTALL).group(0)
    assert 'href="/example/"' in nav


def test_coding_pages_do_not_move_or_change(built, two_section_build) -> None:
    out = two_section_build
    for sub in ("coding", "api/coding"):
        base = built.out / sub
        files1 = {str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()}
        files2 = {
            str(p.relative_to(out / sub)) for p in (out / sub).rglob("*") if p.is_file()
        }
        assert files1 == files2, f"{sub}: paths changed"
        for rel in files1:
            old = (base / rel).read_bytes()
            new = (out / sub / rel).read_bytes()
            if rel.endswith(".html"):
                # The shared header and footer legitimately gain the stub link
                # on every page; the section-owned body stays byte-identical.
                assert _strip_shell(old.decode()) == _strip_shell(new.decode()), rel
            else:
                assert old == new, rel


def test_shared_docs_unchanged_apart_from_stub(built, two_section_build) -> None:
    out = two_section_build
    for name in ("security", "faq", "for-agents", "report"):
        old = (built.out / name / "index.html").read_text(encoding="utf-8")
        new = (out / name / "index.html").read_text(encoding="utf-8")
        assert _strip_shell(old) == _strip_shell(new), name
