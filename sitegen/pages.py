"""Shared pages and orchestration: sections build themselves via SECTION_BUILDERS."""

import json
from pathlib import Path
from typing import Any

from . import coding, engine
from .model import SectionResult, Site
from .pageparts import (
    PARTIALS,
    PageError,
    chip,
    counts,
    data_fill,
    md_sections,
    render_steps,
    text_sections,
    write_md,
    write_page,
)
from .render import Prose, Safe, render_file, render_text_file

MD = "md"
DEMO_MARKS = {"You": "›", "Claude Code": "●", "guard": "⎿"}

# Plan 0.1 rule 2: a section id maps to the function that builds its pages.
SECTION_BUILDERS = {"coding": coding.build}


def _home(site: Site, out_dir: Path, templates: Path) -> tuple[str, str, str]:
    """The landing page (plan 6.7) and its Markdown twin."""
    home = site.data["home"]
    texts = site.data["texts"]
    coding_counts = counts(site, "coding")
    subs = {
        "__CATALOG_REF_12__": site.catalog_ref[:12],
        "__COUNT__": str(coding_counts["total"]),
        "__TESTED__": f"{coding_counts['tested']:,}",
    }
    by_id = {p.id: p for p in site.policies}
    for card in home["examples"]:
        if card["policy"] not in by_id:
            msg = f"home.yaml examples: policy {card['policy']} is not visible"
            raise PageError(msg)

    sections_block = ""
    if len(site.tracks) >= 2:
        cards = "".join(
            render_file(
                templates / PARTIALS / "track-card.html",
                ID=track.id,
                SLUG=track.slug,
                TITLE=track.title,
                SUMMARY=Prose(track.summary),
                LINK=track.title,
            )
            for track in site.tracks
        )
        sections_block = render_file(
            templates / PARTIALS / "sections-block.html",
            HEADING=home["sections_heading"],
            CARDS=Safe(cards),
        )
    demo_lines = "\n".join(
        render_file(
            templates / PARTIALS / "demo-line.html",
            KIND=line["actor"].lower().replace(" ", "-"),
            MARK=DEMO_MARKS.get(line["actor"], ""),
            TEXT=line["text"],
        )
        for line in home["demo"]["lines"]
    )
    stop_cards = "".join(
        render_file(
            templates / PARTIALS / "home-stop-card.html",
            ID=card["policy"],
            KEYWORD=by_id[card["policy"]].keyword,
            WHERE=" ".join(by_id[card["policy"]].where),
            CHIP=chip(site, templates, by_id[card["policy"]], "coding"),
            TITLE=card["title"],
            SAYS=Prose(by_id[card["policy"]].says),
        )
        for card in home["examples"]
    )
    why = "".join(
        render_file(
            templates / PARTIALS / "home-card.html",
            TITLE=point["title"],
            BODY=Prose(data_fill(point["body"], subs)),
        )
        for point in home["why"]
    )
    faq_teaser = [
        item for item in site.data["faq"]["questions"] if item["group"] == "common"
    ][:4]
    questions = "".join(
        render_file(
            templates / PARTIALS / "question-card.html", Q=item["q"], A=Prose(item["a"])
        )
        for item in faq_teaser
    )

    page = site.data["pages"]["home"]
    write_page(
        site,
        out_dir,
        templates,
        path="/",
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / "index.html",
                EYEBROW=home["eyebrow"],
                HERO_HEADLINE=texts["hero_headline"],
                HERO_SUB=Prose(texts["hero_sub"]),
                HERO_NOTE=Prose(texts["hero_note"]),
                PRIMARY_CTA=home["primary_cta"],
                SECONDARY_CTA=home["secondary_cta"],
                DEMO_TOOL=home["demo"]["tool"],
                DEMO_POLICY=home["demo"]["policy"],
                DEMO_LINES=Safe(demo_lines),
                DEMO_FOOTER=data_fill(home["demo"]["footer"], subs),
                SECTIONS_BLOCK=Safe(sections_block),
                STOPS_HEADING=home["stops_heading"],
                STOPS_INTRO=Prose(home["stops_intro"]),
                STOP_CARDS=Safe(stop_cards),
                STEPS=render_steps(site, templates),
                WHY_HEADING=home["why_heading"],
                WHY_CARDS=Safe(why),
                QUESTIONS_HEADING=home["questions_heading"],
                QUESTIONS_LINK=home["questions_link"],
                QUESTION_CARDS=Safe(questions),
                CTA_HEADING=home["cta_heading"],
                CTA_SUB=Prose(home["cta_sub"]),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": site.data["wordmark"],
            "url": site.data["site_url"] + "/",
        },
    )
    twin = render_text_file(
        templates / MD / "index.md",
        HERO_SUB=texts["hero_sub"],
        HERO_NOTE=texts["hero_note"],
        STOPS_HEADING=home["stops_heading"],
        STOPS_INTRO=home["stops_intro"],
        STOP_LINES="".join(
            f"- [{card['title']}](/coding/policies/{card['policy']}/index.md): "
            f"{by_id[card['policy']].word} — {by_id[card['policy']].says}\n"
            for card in home["examples"]
        ),
        STEPS_HEADING=home["steps_heading"],
        STEP_LINES="".join(
            f"{i}. {step['title']} — {step['body']}\n"
            for i, step in enumerate(home["steps"], start=1)
        ),
        WHY_HEADING=home["why_heading"],
        WHY_LINES="".join(
            f"- {point['title']}: {data_fill(point['body'], subs)}\n"
            for point in home["why"]
        ),
        QUESTIONS_HEADING=home["questions_heading"],
        QUESTION_LINES="".join(f"- {item['q']} {item['a']}\n" for item in faq_teaser),
        CTA_HEADING=home["cta_heading"],
        CTA_SUB=home["cta_sub"],
    )
    write_md(out_dir, "/", twin)
    return "/", "/index.md", twin


def _security(site: Site, out_dir: Path, templates: Path) -> tuple[str, str, str]:
    """The security page and its twin."""
    data = site.data
    page = data["pages"]["security"]
    write_page(
        site,
        out_dir,
        templates,
        path="/security/",
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / "security.html",
                SUB=Prose(page["description"]),
                SECTIONS=Safe(text_sections(site, templates, data["security"])),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page["title"],
            "description": page["description"],
        },
        nav="security",
    )
    twin = render_text_file(
        templates / MD / "security.md",
        SUB=Prose(page["description"]),
        SECTIONS=md_sections(data["security"], data["links"]),
    )
    write_md(out_dir, "/security/", twin)
    return "/security/", "/security/index.md", twin


def _faq(site: Site, out_dir: Path, templates: Path) -> tuple[str, str, str]:
    """The FAQ page, grouped per faq.yaml (plan 6.7), and its twin."""
    data = site.data
    page = data["pages"]["faq"]
    groups = "".join(
        render_file(
            templates / PARTIALS / "faq-group.html",
            ID=group["id"],
            TITLE=group["title"],
            ITEMS=Safe(
                "".join(
                    render_file(
                        templates / PARTIALS / "faq-item.html",
                        ID=item["id"],
                        Q=item["q"],
                        A=Prose(item["a"]),
                    )
                    for item in data["faq"]["questions"]
                    if item["group"] == group["id"]
                )
            ),
        )
        for group in data["faq"]["groups"]
    )
    write_page(
        site,
        out_dir,
        templates,
        path="/faq/",
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / "faq.html",
                SUB=Prose(page["description"]),
                FAQ_GROUPS=Safe(groups),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["q"],
                    "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
                }
                for item in data["faq"]["questions"]
            ],
        },
        nav="faq",
    )
    twin = render_text_file(
        templates / MD / "faq.md",
        SUB=Prose(page["description"]),
        FAQ_LINES="".join(
            f"## {group['title']}\n\n"
            + "".join(
                f"### {item['q']}\n\n{item['a']}\n\n"
                for item in data["faq"]["questions"]
                if item["group"] == group["id"]
            )
            for group in data["faq"]["groups"]
        ),
    )
    write_md(out_dir, "/faq/", twin)
    return "/faq/", "/faq/index.md", twin


def _worked_example(site: Site, section: dict[str, Any]) -> dict[str, Any]:
    """The guide section with its preset's selection object, code and command filled in."""
    preset = next(p for p in site.presets if p.id == section["worked_example"])
    by_id = {p.id: p for p in site.policies}
    picks = [
        {"id": pid, "version": by_id[pid].version, "sha256": by_id[pid].sha256}
        for pid in preset.members
    ]
    selection = engine.build_selection(
        picks, site.catalog_source, site.catalog_ref, site.release, preset.id
    )
    code = engine.encode_selection(selection)
    command = data_fill(site.command, {"__CODE__": code})
    return {
        **section,
        "code_json": json.dumps(selection, indent=2, ensure_ascii=False),
        "code_bash": f"# Share code\n{code}\n\n# Ask the user first: it installs hooks\n{command}",
    }


def _for_agents(site: Site, out_dir: Path, templates: Path) -> tuple[str, str, str]:
    """The agent guide (plan 6.8), with the git-hygiene worked example."""
    data = site.data
    page = data["pages"]["agents"]
    sections = [
        _worked_example(site, s) if s.get("worked_example") else s
        for s in data["agents"]["sections"]
    ]
    write_page(
        site,
        out_dir,
        templates,
        path="/for-agents/",
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / "for-agents.html",
                SUB=Prose(page["description"]),
                SECTIONS=Safe(text_sections(site, templates, sections)),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": page["title"],
            "description": page["description"],
        },
    )
    twin = render_text_file(
        templates / MD / "for-agents.md",
        SUB=Prose(page["description"]),
        SECTIONS=md_sections(sections, data["links"]),
    )
    write_md(out_dir, "/for-agents/", twin)
    return "/for-agents/", "/for-agents/index.md", twin


def _not_found(site: Site, out_dir: Path, templates: Path) -> str:
    """404.html and its twin."""
    data = site.data
    page = data["pages"]["notfound"]
    write_page(
        site,
        out_dir,
        templates,
        path="/404.html",
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / "404.html", SUB=Prose(data["texts"]["notfound_sub"])
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page["title"],
            "description": page["description"],
        },
        md_href="404.md",
    )
    write_md(
        out_dir,
        "/404.md",
        render_text_file(templates / MD / "404.md", SUB=data["texts"]["notfound_sub"]),
    )
    return "/404.md"


def _api_index(site: Site, out_dir: Path) -> None:
    """api/index.json: the entry point listing every section (plan 6.8)."""
    api = out_dir / "api"
    api.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "site": site.data["wordmark"],
        "tracks": [
            {
                "id": track.id,
                "title": track.title,
                "home": f"/{track.slug}/",
                "api": f"/api/{track.slug}/",
            }
            for track in site.tracks
        ],
    }
    (api / "index.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _llms(
    site: Site,
    out_dir: Path,
    sections: list[SectionResult],
    shared_docs: list[tuple[str, str]],
) -> None:
    """llms.txt (frozen headings) and llms-full.txt (twins in llms order)."""
    docs = [
        ("Site home", "/index.md", "what chock is and who it is for"),
        ("Security", "/security/index.md", "what chock is and is not"),
        ("FAQ", "/faq/index.md", "common questions"),
        ("For AI agents", "/for-agents/index.md", "how to read this site and its data"),
    ]
    total = sum(len([p for p in site.policies if p.track == t.id]) for t in site.tracks)
    blockquote = (
        "> chock turns a picked set of guardrail policies into plugins for AI "
        f"agents. The coding section holds {total} policies, each "
        "labelled blocks, asks, warns or advisory, on a catalog pinned at "
        f"{site.catalog_ref[:12]}. Ask the user before picking or installing "
        "anything.\n"
    )
    lines = [
        "# chock.sh\n",
        blockquote,
        "## Docs\n",
    ]
    lines += [f"- [{name}]({path}): {note}\n" for name, path, note in docs]
    for section in sections:
        lines.append("\n" + section.llms)
    lines.append("\n## Data\n\n")
    lines.append(
        "- [/api/index.json](/api/index.json): every section, "
        "with its home and api paths\n"
    )
    for track in site.tracks:
        lines.append(
            f"- [/api/{track.slug}/catalog.json](/api/{track.slug}/catalog.json): "
            "every policy and preset (schema_version 1)\n"
            f"- `/api/{track.slug}/policies/<id>.json`: one policy record\n"
            f"- [/api/{track.slug}/presets.json](/api/{track.slug}/presets.json): "
            "the presets\n"
            f"- [/api/{track.slug}/selection.schema.json]"
            f"(/api/{track.slug}/selection.schema.json): the schema a "
            "selection file is checked against\n"
        )
    lines.append("- [/data/site.json](/data/site.json): the generated site data\n")
    (out_dir / "llms.txt").write_text("".join(lines), encoding="utf-8", newline="\n")

    ordered: list[tuple[str, str]] = [
        next((p, t) for p, t in shared_docs if p == path) for _, path, _ in docs
    ]
    for section in sections:
        ordered += section.docs
    parts = [f"---\n# {path}\n\n{text}\n" for path, text in ordered]
    (out_dir / "llms-full.txt").write_text(
        "".join(parts), encoding="utf-8", newline="\n"
    )


def _sitemap(site: Site, out_dir: Path, paths: list[str]) -> None:
    """sitemap.xml with every page but 404; robots disallowing all pre-launch."""
    body = "".join(
        f"<url><loc>{site.data['site_url']}{path}</loc></url>\n" for path in paths
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}</urlset>\n"
    )
    (out_dir / "sitemap.xml").write_text(xml, encoding="utf-8", newline="\n")
    robots = (
        "User-agent: *\nDisallow: /\n"
        if not site.data.get("launched")
        else "User-agent: *\nAllow: /\n"
        f"# llms.txt: {site.data['site_url']}/llms.txt\n"
        f"Sitemap: {site.data['site_url']}/sitemap.xml\n"
    )
    (out_dir / "robots.txt").write_text(robots, encoding="utf-8", newline="\n")


def write_pages(site: Site, out_dir: Path, templates_dir: Path) -> None:
    """Every page, twin, index and API file described in plan 6.3 and 6.8."""
    home_path, home_md, home_twin = _home(site, out_dir, templates_dir)
    paths = [home_path]
    sections: list[SectionResult] = []
    for track in site.tracks:
        builder = SECTION_BUILDERS.get(track.id)
        if builder is None:
            raise PageError(f"no builder for section {track.id!r}")
        result = builder(site, track, out_dir, templates_dir)
        sections.append(result)
        paths += result.pages
    shared_docs: list[tuple[str, str]] = [(home_md, home_twin)]
    for build in (_security, _faq, _for_agents):
        page_path, md_path, twin = build(site, out_dir, templates_dir)
        paths.append(page_path)
        shared_docs.append((md_path, twin))
    _not_found(site, out_dir, templates_dir)
    _api_index(site, out_dir)
    _llms(site, out_dir, sections, shared_docs)
    _sitemap(site, out_dir, sorted(set(paths)))
