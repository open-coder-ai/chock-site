"""Shared page helpers: one-pass rendering glue used by every section."""

import html
import json
import re
from pathlib import Path
from typing import Any

from .model import Policy, Site, Track
from .render import Prose, Safe, render_file, sentence_start

PARTIALS = "partials"
BASE = "base.html"


class PageError(ValueError):
    """Page copy or data that cannot be rendered into a page."""


def slug(text: str) -> str:
    """A lower-case heading slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


CODE_KEYS = (
    ("code_python", "python"),
    ("code_js", "js"),
    ("code_json", "json"),
    ("code_bash", "bash"),
)


# The install command as prose shows it: the code elided, the agent named by its placeholder.
COMMAND_FORM = {"__CODE__": "…", "__CLIENT__": "<agent>"}


def data_fill(text: str, subs: dict[str, str]) -> str:
    """Substitute placeholders inside a data string (not an HTML template)."""
    if not subs:
        return text
    pattern = re.compile("|".join(re.escape(token) for token in subs))
    return pattern.sub(lambda match: subs[match.group(0)], text)


def keyword_chip(site: Site, templates: Path, keyword: str, section: str) -> Safe:
    """The label chip for a label keyword (plan 6.4); the section picks the words."""
    word = site.label_words[section][keyword]
    return Safe(
        render_file(
            templates / PARTIALS / "label-chip.html",
            KEYWORD=keyword,
            WORD=sentence_start(word),
            MEANING=site.data["label_meanings"][word],
            GLYPH=site.data["glyphs"][keyword],
        )
    )


def chip(site: Site, templates: Path, policy: Policy, section: str) -> Safe:
    """The label chip for one policy (plan 6.4); the section picks the words."""
    return keyword_chip(site, templates, policy.keyword, section)


def status_badge(site: Site, templates: Path, policy: Policy) -> Safe:
    """The policy's status badge, only for a status texts.status_badges names (BV-C3: deprecated)."""
    word = site.data["texts"]["status_badges"].get(policy.status or "")
    if word is None:
        return Safe("")
    return Safe(
        render_file(
            templates / PARTIALS / "status-badge.html",
            STATUS=policy.status,
            WORD=sentence_start(word),
        )
    )


def install_command(site: Site) -> str:
    """The engine install line the Install page shows, chosen by `released`."""
    inst = site.data["install"]
    if site.data.get("released"):
        return inst["install_command_released"]
    return data_fill(inst["install_command"], {"__FRAMEWORK_REF__": site.framework_ref})


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
            WORD=sentence_start(words[key]),
            COUNT=str(counts["label"][key]),
        )
        for key in words
    )


def jsonld(kind: dict[str, Any]) -> Safe:
    """A JSON-LD script element; `<`, `>` and `&` are \\u-escaped so catalog text cannot break out."""
    body = (
        json.dumps(kind, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return Safe(f'<script type="application/ld+json">\n{body}\n</script>')


_BADGES = {
    "available": ("available_badge", "ok"),
    "in_design": ("design_badge", "design"),
}


def badge(site: Site, templates: Path, status: str) -> Safe:
    """The small mono badge a track status shows (AVAILABLE NOW, DESIGN IN PROGRESS)."""
    key, kind = _BADGES[status]
    return Safe(
        render_file(
            templates / PARTIALS / "badge.html",
            KIND=kind,
            TEXT=site.data["texts"][key],
        )
    )


def nav_items(templates: Path, items: list[tuple], current: str) -> Safe:
    """One nav-item link per (href, label[, badge]); `current` is the href marked."""
    links = []
    for item in items:
        content = html.escape(item[1])
        if len(item) > 2 and item[2]:
            content += " " + str(item[2])
        links.append(
            render_file(
                templates / PARTIALS / "nav-item.html",
                HREF=item[0],
                LABEL=Safe(content),
                EXTRA=Safe(' aria-current="page"') if item[0] == current else "",
            )
        )
    return Safe("".join(links))


def section_nav(
    site: Site, track: Track, templates: Path, current: str, rows: list | None = None
) -> Safe:
    """The section nav below the header on a section's pages (plan 6.1)."""
    rows = rows if rows is not None else site.data["section_nav"]
    hrefs = {
        item["key"]: (
            f"/{track.slug}/"
            if item["key"] == "overview"
            else f"/{track.slug}/{item['key']}/"
        )
        for item in rows
    }
    items = [(hrefs[item["key"]], item["label"]) for item in rows]
    title = html.escape(track.title)
    if track.status == "in_design":
        title += " " + str(badge(site, templates, track.status))
    return Safe(
        render_file(
            templates / PARTIALS / "section-nav.html",
            TITLE=Safe(title),
            NAV_LABEL=track.title,
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
    section: tuple | None = None,
    scripts: tuple[str, ...] = ("common.js",),
    alt_json: str = "",
    md_href: str = "index.md",
    body_end: str = "",
) -> None:
    """Render base.html around one page's content and write it under out_dir."""
    track_links = nav_items(
        templates,
        [
            (
                f"/{t.slug}/",
                t.title,
                str(badge(site, templates, t.status))
                if t.status == "in_design"
                else "",
            )
            for t in site.tracks
        ],
        next((f"/{t.slug}/" for t in site.tracks if t.id == nav), ""),
    )
    footer = _footer_links(site, templates)
    nav_html = ""
    if section is not None:
        nav_rows = section[2] if len(section) > 2 else None
        nav_html = str(section_nav(site, section[0], templates, section[1], nav_rows))
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
        FOOTER_TAGLINE=site.data["texts"]["footer_tagline"],
        PRODUCT_LINKS=footer["product"],
        AGENT_LINKS=footer["agents"],
        PROJECT_LINKS=footer["project"],
        FOOTER_LINE=site.data["texts"]["footer_line"],
        CATALOG_REF=site.catalog_ref,
        CATALOG_REF_12=site.catalog_ref[:12],
        SCRIPTS=script_tags,
        BODY_END=Safe(body_end),
        ARIA_DOCS=Safe(' aria-current="page"') if nav == "docs" else "",
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


def _footer_links(site: Site, templates: Path) -> dict[str, Safe]:
    """The three footer link columns: sections, agents and project."""
    links = site.data["links"]
    product = [(f"/{t.slug}/", t.title) for t in site.tracks]
    product += [
        ("/coding/policies/", "Policies"),
        ("/coding/builder/", "Builder"),
    ]
    clients = site.data["builder_clients"]
    repos = [
        repo
        for c in clients["order"]
        if (repo := clients["clients"][c]["plugin_repo"]) is not None
    ]
    agents = [(url, url.rstrip("/").rsplit("/", 1)[-1]) for url in repos]
    project = [
        (links["engine_repo"], "GitHub"),
        ("/faq/", "FAQ"),
        ("/security/", "Security"),
        ("/report/", site.data["report"]["links"]["footer"]),
        ("/for-agents/", "For AI agents"),
        ("/llms.txt", "llms.txt"),
    ]
    return {
        "product": nav_items(templates, product, ""),
        "agents": nav_items(templates, agents, ""),
        "project": nav_items(templates, project, ""),
    }


def css_tokens(site: Site) -> dict[str, str]:
    """The data-driven placeholders inside static/css/site.css."""
    label = counts(site, "coding")["label"]
    return {
        "SEG_BLOCK": str(label["block"]),
        "SEG_ASK": str(label["ask"]),
        "SEG_WARN": str(label["warn"]),
        "SEG_ADVISE": str(label["advise"]),
    }


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
                        BODY=Prose(step["body"]),
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
        items = ""
        if section.get("items"):
            items = render_file(
                templates / PARTIALS / "text-items.html",
                ITEMS=Safe(
                    "".join(
                        render_file(
                            templates / PARTIALS / "plain-li.html", TEXT=Prose(t)
                        )
                        for t in section["items"]
                    )
                ),
                AFTER=Prose(section["after"]),
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
                for key, lang in CODE_KEYS
                if section.get(key)
            )
        rendered.append(
            render_file(
                templates / PARTIALS / "text-section.html",
                ID=slug(section["heading"]),
                HEADING=section["heading"],
                BODY=Prose(section["body"]),
                ITEMS=Safe(items),
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
        if s.get("items"):
            out.append("\n" + "".join(f"- {t}\n" for t in s["items"]))
            out.append(f"\n{s['after']}\n")
        if s.get("code_label"):
            out.append(f"\n{s['code_label']}\n")
            for key, lang in CODE_KEYS:
                if s.get(key):
                    out.append(f"\n```{lang}\n{s[key].rstrip()}\n```\n")
        if s.get("link"):
            out.append(f"\n{links[s['link']]}\n")
        out.append("\n")
    return "".join(out)
