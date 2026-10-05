"""Shared page helpers: one-pass rendering glue used by every section."""

import json
import re
from pathlib import Path
from typing import Any

from .model import Policy, Site, Track
from .render import Safe, render_file

PARTIALS = "partials"
BASE = "base.html"


class PageError(ValueError):
    """Page copy or data that cannot be rendered into a page."""


def slug(text: str) -> str:
    """A lower-case heading slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def data_fill(text: str, subs: dict[str, str]) -> str:
    """Substitute placeholders inside a data string (not an HTML template)."""
    for token, value in subs.items():
        text = text.replace(token, value)
    return text


def chip(site: Site, templates: Path, policy: Policy, section: str) -> Safe:
    """The label chip for one policy (plan 6.4); the section picks the words."""
    return Safe(
        render_file(
            templates / PARTIALS / "label-chip.html",
            KEYWORD=policy.keyword,
            WORD=site.label_words[section][policy.keyword],
            MEANING=site.data["label_meanings"][
                site.label_words[section][policy.keyword]
            ],
            GLYPH=site.data["glyphs"][policy.keyword],
        )
    )


def label_chips(
    site: Site, templates: Path, counts: dict[str, Any], section: str
) -> str:
    """One filter button per label keyword, with its build-time count."""
    words = site.label_words[section]
    return "".join(
        render_file(
            templates / PARTIALS / "filter-chip.html",
            FACET="label",
            VALUE=key,
            GLYPH_KEY=key,
            GLYPH=site.data["glyphs"][key],
            WORD=words[key],
            COUNT=str(counts["label"][key]),
        )
        for key in words
    )


def jsonld(kind: dict[str, Any]) -> Safe:
    """A JSON-LD script element; `</` is neutralised so it cannot close the tag."""
    body = json.dumps(kind, ensure_ascii=False).replace("</", "<\\/")
    return Safe(f'<script type="application/ld+json">\n{body}\n</script>')


def nav_items(templates: Path, items: list[tuple[str, str]], current: str) -> Safe:
    """One nav-item link per (href, label); `current` is the href marked."""
    return Safe(
        "".join(
            render_file(
                templates / PARTIALS / "nav-item.html",
                HREF=href,
                LABEL=label,
                EXTRA=Safe(' aria-current="page"') if href == current else "",
            )
            for href, label in items
        )
    )


def section_nav(site: Site, track: Track, templates: Path, current: str) -> Safe:
    """The section nav below the header on a section's pages (plan 6.1)."""
    hrefs = {
        item["key"]: (
            f"/{track.slug}/"
            if item["key"] == "overview"
            else f"/{track.slug}/{item['key']}/"
        )
        for item in site.data["section_nav"]
    }
    items = [(hrefs[item["key"]], item["label"]) for item in site.data["section_nav"]]
    return Safe(
        render_file(
            templates / PARTIALS / "section-nav.html",
            TITLE=track.title,
            ITEMS=nav_items(templates, items, hrefs.get(current, "")),
        )
    )


def write_page(
    site: Site,
    out_dir: Path,
    templates: Path,
    *,
    path: str,
    title: str,
    description: str,
    content: Safe,
    jsonld_data: dict[str, Any],
    nav: str = "",
    section: tuple[Track, str] | None = None,
    scripts: tuple[str, ...] = ("common.js",),
    alt_json: str = "",
    md_href: str = "index.md",
) -> None:
    """Render base.html around one page's content and write it under out_dir."""
    track_links = nav_items(
        templates,
        [(f"/{t.slug}/", t.title) for t in site.tracks],
        next((f"/{t.slug}/" for t in site.tracks if t.id == nav), ""),
    )
    nav_html = ""
    if section is not None:
        nav_html = str(section_nav(site, section[0], templates, section[1]))
    script_tags = Safe(
        "".join(
            render_file(templates / PARTIALS / "script-tag.html", SRC=name)
            for name in scripts
        )
    )
    html = render_file(
        templates / BASE,
        TITLE=title,
        DESCRIPTION=description,
        CANONICAL=site.data["site_url"] + path,
        OG_IMAGE=site.data["og_image"],
        MD_HREF=md_href,
        ALT_JSON=Safe(alt_json),
        JSONLD=jsonld(jsonld_data),
        TRACK_LINKS=track_links,
        SECTION_NAV=Safe(nav_html),
        CONTENT=content,
        FOOTER_LINE=site.data["texts"]["footer_line"],
        CATALOG_REF=site.catalog_ref,
        CATALOG_REF_12=site.catalog_ref[:12],
        SCRIPTS=script_tags,
        ARIA_FAQ=Safe(' aria-current="page"') if nav == "faq" else "",
        ARIA_SECURITY=Safe(' aria-current="page"') if nav == "security" else "",
    )
    if path.endswith("/"):
        target = out_dir / path.strip("/") / "index.html"
    else:
        target = out_dir / path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8", newline="\n")


def write_md(out_dir: Path, path: str, text: str) -> Path:
    """Write one Markdown twin next to its page."""
    if path.endswith("/"):
        target = out_dir / path.strip("/") / "index.md"
    else:
        target = out_dir / path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def policies_sorted(site: Site) -> list[Policy]:
    """Policies in display order: name, case-insensitively."""
    return sorted(site.policies, key=lambda p: p.name.casefold())


def counts(site: Site, section: str) -> dict[str, Any]:
    """Build-time counts: per label keyword, per where tag, presets, eval cases."""
    label = {key: 0 for key in site.label_words[section]}
    where: dict[str, int] = {}
    policies = [p for p in site.policies if p.track == section]
    for policy in policies:
        label[policy.keyword] += 1
        for tag in policy.where:
            where[tag] = where.get(tag, 0) + 1
    return {
        "label": label,
        "where": where,
        "total": len(policies),
        "presets": len(site.presets),
        "tested": sum(p.eval_executed for p in policies),
    }


def render_steps(site: Site, templates: Path) -> Safe:
    """The shared 'How it works' section, used on the home and section home."""
    home = site.data["home"]
    return Safe(
        render_file(
            templates / PARTIALS / "steps.html",
            STEPS_HEADING=home["steps_heading"],
            STEP_ITEMS=Safe(
                "".join(
                    render_file(
                        templates / PARTIALS / "home-step.html",
                        NUM=str(i),
                        TITLE=step["title"],
                        BODY=step["body"],
                    )
                    for i, step in enumerate(home["steps"], start=1)
                )
            ),
        )
    )


def text_sections(site: Site, templates: Path, sections: list[dict[str, Any]]) -> str:
    """Heading + body + optional code blocks and link (security, agent guide)."""
    rendered = []
    for section in sections:
        link = ""
        if section.get("link"):
            link = render_file(
                templates / PARTIALS / "link-line.html",
                URL=site.data["links"][section["link"]],
                LABEL=section["link_label"],
            )
        code = ""
        if section.get("code_label"):
            code = render_file(
                templates / PARTIALS / "code-label.html",
                LABEL=section["code_label"],
            ) + "".join(
                render_file(
                    templates / PARTIALS / "code-pre.html",
                    LANG=lang,
                    CODE=section[key].rstrip(),
                )
                for key, lang in (("code_python", "python"), ("code_js", "js"))
                if section.get(key)
            )
        rendered.append(
            render_file(
                templates / PARTIALS / "text-section.html",
                ID=slug(section["heading"]),
                HEADING=section["heading"],
                BODY=section["body"],
                CODE=Safe(code),
                LINK=Safe(link),
            )
        )
    return "".join(rendered)


def md_sections(sections: list[dict[str, Any]], links: dict[str, str]) -> str:
    """The same sections as Markdown, including code blocks."""
    out = []
    for s in sections:
        out.append(f"## {s['heading']}\n\n{s['body']}\n")
        if s.get("code_label"):
            out.append(f"\n{s['code_label']}\n")
            for key, lang in (("code_python", "python"), ("code_js", "js")):
                if s.get(key):
                    out.append(f"\n```{lang}\n{s[key].rstrip()}\n```\n")
        if s.get("link"):
            out.append(f"\n{links[s['link']]}\n")
        out.append("\n")
    return "".join(out)
