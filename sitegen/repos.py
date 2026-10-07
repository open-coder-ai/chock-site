"""The Git repositories section: its home, its builder page, and /api/repos/policies.json."""

import json
from pathlib import Path
from typing import Any

from . import repodata
from .coding import quiz_lines
from .model import SectionResult, Site, Track
from .pageparts import (
    PARTIALS,
    badge,
    install_command,
    keyword_chip,
    policies_sorted,
    write_md,
    write_page,
)
from .render import Prose, Safe, md, md_code, render_file, render_text_file

MD = "md"
SECTION = "repos"
_NAV = [
    {"key": "overview", "label": "Overview"},
    {"key": "builder", "label": "Builder"},
]


def _chip(site: Site, templates: Path, key: str) -> Safe:
    """The tier chip for a tier key, with the section's own word and meaning."""
    return keyword_chip(site, templates, key, SECTION)


def _install_block(templates: Path, command: str) -> Safe:
    """The install line as a code block."""
    return Safe(render_file(templates / PARTIALS / "command-pre.html", COMMAND=command))


def _steps(templates: Path, heading: str, steps: list[dict[str, str]]) -> Safe:
    """The three-step block, in the shared steps markup."""
    items = "".join(
        render_file(
            templates / PARTIALS / "home-step.html",
            NUM=str(i),
            TITLE=step["title"],
            BODY=Prose(step["body"]),
        )
        for i, step in enumerate(steps, start=1)
    )
    return Safe(
        render_file(
            templates / PARTIALS / "steps.html",
            STEPS_HEADING=heading,
            STEP_ITEMS=Safe(items),
        )
    )


def _home(site: Site, track: Track, out_dir: Path, templates: Path) -> tuple[str, str]:
    """The section home: tier counts, three steps, install line, policies by tier."""
    data = site.data["repos"]
    home = data["home"]
    page = data["pages"]["home"]
    tiers = data["tiers"]
    numbers = repodata.counts(site.policies, tiers)
    cards = "".join(
        render_file(
            templates / PARTIALS / "repos-tier.html",
            KEY=tier["key"],
            NUM=str(numbers[tier["key"]]),
            CHIP=_chip(site, templates, tier["key"]),
            MEANING=tier["meaning"],
        )
        for tier in tiers
    )
    groups = "".join(
        render_file(
            templates / PARTIALS / "repos-group.html",
            KEY=tier["key"],
            CHIP=_chip(site, templates, tier["key"]),
            NUM=str(numbers[tier["key"]]),
            ITEMS=Safe(
                "".join(
                    render_file(
                        templates / PARTIALS / "repos-policy.html",
                        ID=policy.id,
                        NAME=policy.name,
                    )
                    for policy in policies_sorted(site)
                    if policy.tier == tier["key"]
                )
            ),
        )
        for tier in tiers
    )
    command = install_command(site)
    path = f"/{track.slug}/"
    write_page(
        site,
        out_dir,
        templates,
        path=path,
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / track.slug / "home.html",
                BADGE=badge(site, templates, track.status),
                H1=home["h1"],
                SUMMARY=Prose(track.summary),
                CTA=home["cta"],
                TIERS_HEADING=home["tiers_heading"],
                TIER_CARDS=Safe(cards),
                COMPUTED_NOTE=home["computed_note"],
                STEPS=_steps(templates, home["steps_heading"], home["steps"]),
                INSTALL_HEADING=home["install_heading"],
                INSTALL_NOTE=Prose(home["install_note"]),
                INSTALL_CMD=_install_block(templates, command),
                INSTALL_LINK=home["install_link"],
                LIST_HEADING=home["list_heading"],
                LIST_INTRO=Prose(home["list_intro"]),
                GROUPS=Safe(groups),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": f"{page['title']} · chock.sh",
            "description": page["description"],
        },
        nav=track.id,
        section=(track, "overview", _NAV),
    )
    twin = render_text_file(
        templates / MD / track.slug / "home.md",
        H1=home["h1"],
        BADGE=site.data["texts"]["available_badge"],
        SUMMARY=track.summary,
        TIERS_HEADING=home["tiers_heading"],
        TIER_LINES="".join(
            f"- {numbers[t['key']]} {t['word']}: {t['meaning']}\n" for t in tiers
        ),
        STEPS_HEADING=home["steps_heading"],
        STEP_LINES="".join(
            f"{i}. {step['title']} — {step['body']}\n"
            for i, step in enumerate(home["steps"], start=1)
        ),
        INSTALL_HEADING=home["install_heading"],
        INSTALL_NOTE=home["install_note"],
        INSTALL_CMD=command,
        BUILDER_LABEL=home["cta"],
        LIST_HEADING=home["list_heading"],
        LIST_INTRO=home["list_intro"],
        GROUP_LINES="".join(
            f"### {t['word']}\n\n"
            + "".join(
                f"- [{md(p.name)}](/coding/policies/{p.id}/index.md) ({md_code(p.id)})\n"
                for p in policies_sorted(site)
                if p.tier == t["key"]
            )
            + "\n"
            for t in tiers
        ),
        CATALOG_REF=site.catalog_ref,
    )
    write_md(out_dir, path, twin)
    return path, twin


def _template_block(site: Site) -> str:
    """The command template with the catalog commit filled in and the rest as placeholders."""
    commands = site.data["repos"]["commands"]
    return "\n".join(
        [
            commands["init"],
            repodata.fill(
                commands["add"],
                {"id": "<id>", "ref": site.catalog_ref, "sha256": "<sha256>"},
            ),
            commands["sync"] + "   # or: " + commands["sync_ci"],
            commands["commit"],
        ]
    )


def _builder(
    site: Site, track: Track, out_dir: Path, templates: Path
) -> tuple[str, str]:
    """The repository builder page: the shared quiz, its install note and the command template."""
    data = site.data["repos"]
    page = data["pages"]["builder"]
    texts = data["builder"]
    command = install_command(site)
    template = _template_block(site)
    path = f"/{track.slug}/builder/"
    write_page(
        site,
        out_dir,
        templates,
        path=path,
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / track.slug / "builder.html",
                H1=texts["h1"],
                SUB=Prose(page["description"]),
                NOSCRIPT=Prose(texts["noscript"]),
                QUIZ=Safe(
                    render_file(
                        templates / PARTIALS / "quiz.html",
                        TOP=Safe(""),
                    )
                ),
                INSTALL_HEADING=texts["install_heading"],
                INSTALL_NOTE=Prose(texts["install_note"]),
                INSTALL_CMD=_install_block(templates, command),
                INSTALL_LINK=texts["install_link"],
                TEMPLATE_HEADING=texts["template_heading"],
                TEMPLATE_NOTE=Prose(texts["template_note"]),
                TEMPLATE=_install_block(templates, template),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page["title"],
            "description": page["description"],
        },
        nav=track.id,
        section=(track, "builder", _NAV),
        scripts=("common.js", "repos.js"),
    )
    twin = render_text_file(
        templates / MD / track.slug / "builder.md",
        H1=texts["h1"],
        SUB=page["description"],
        NOSCRIPT=texts["noscript"],
        QUIZ_LINES=quiz_lines(site.data["repos_quiz"]["questions"]),
        INSTALL_HEADING=texts["install_heading"],
        INSTALL_NOTE=texts["install_note"],
        INSTALL_CMD=command,
        TEMPLATE_HEADING=texts["template_heading"],
        TEMPLATE_NOTE=texts["template_note"],
        TEMPLATE=template,
    )
    write_md(out_dir, path, twin)
    return path, twin


def _api(site: Site, out_dir: Path) -> None:
    """api/repos/policies.json: the catalog commit and each policy's version, sha256 and tier."""
    api = out_dir / "api" / SECTION
    api.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "schema_version": 1,
        "catalog_ref": site.catalog_ref,
        "policies": [
            {"id": p.id, "version": p.version, "sha256": p.sha256, "tier": p.tier}
            for p in sorted(site.policies, key=lambda p: p.id)
        ],
    }
    (api / "policies.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(site: Site, track: Track, out_dir: Path, templates: Path) -> SectionResult:
    """Build the section's two pages, their twins and its API file."""
    home_path, home_doc = _home(site, track, out_dir, templates)
    builder_path, builder_doc = _builder(site, track, out_dir, templates)
    _api(site, out_dir)
    llms = (
        f"## {track.title}\n\n"
        f"- [{track.title}](/{track.slug}/index.md): {track.summary}\n"
        f"- [Set up your repository](/{track.slug}/builder/index.md): "
        "pick policies, get the commands that install them\n"
    )
    data_lines = (
        f"- [/api/{track.slug}/policies.json](/api/{track.slug}/policies.json): "
        "each policy's version, sha256 and repository tier, and the catalog commit "
        "(schema_version 1)\n"
    )
    return SectionResult(
        pages=[home_path, builder_path],
        llms=llms,
        docs=[
            (f"{home_path}index.md", home_doc),
            (f"{builder_path}index.md", builder_doc),
        ],
        data_lines=data_lines,
    )
