"""The Report an issue page (plan IS-1b): GitHub issue-form links pre-filled from context."""

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .model import Site
from .pageparts import PARTIALS, data_fill, write_md, write_page
from .render import Prose, Safe, md, render_file, render_text_file

PATH = "/report/"
# SR-1's id pattern: a crafted /report/ link cannot plant text in an issue.
ID_RE = re.compile(r"^[a-z0-9.-]{1,64}$")
# A site page path: up to four id-shaped segments, each ending in "/", none of them "..".
PAGE_RE = re.compile(r"^/(?:[a-z0-9][a-z0-9.-]{0,63}/){0,4}$")
# A context key inside a kind's issue title, e.g. {policy}.
TITLE_KEY_RE = re.compile(r"\{([a-z_]+)\}")
# Context the browser reads from the /report/ query; the rest is fixed at build time.
QUERY_KEYS = ("policy", "version", "agent", "page")
BUILD_KEYS = ("catalog_ref", "engine_ref")
REPOS = ("chock", "chock-catalog", "chock-site")
KIND_KEYS = (
    "id",
    "heading",
    "body",
    "include",
    "repo",
    "template",
    "button",
    "fields",
)


class ReportError(ValueError):
    """report.yaml names an unknown repo, context key or title token."""


def check_report(report: dict[str, Any]) -> None:
    """Fail the build when report.yaml would produce a link to the wrong form or field."""
    ids = set()
    for kind in report["kinds"]:
        missing = [key for key in KIND_KEYS if key not in kind]
        if missing:
            raise ReportError(
                f"report.yaml kind {kind.get('id', '?')}: missing {missing}"
            )
        if kind["id"] in ids or not ID_RE.fullmatch(kind["id"]):
            raise ReportError(
                f"report.yaml kind id {kind['id']!r} is repeated or not an id"
            )
        ids.add(kind["id"])
        if kind["repo"] not in REPOS:
            raise ReportError(
                f"report.yaml kind {kind['id']}: unknown repo {kind['repo']!r}"
            )
        if not re.fullmatch(r"[a-z0-9-]+\.yml", kind["template"]):
            raise ReportError(f"report.yaml kind {kind['id']}: bad template name")
        for field, key in kind["fields"].items():
            if not ID_RE.fullmatch(field) or key not in QUERY_KEYS + BUILD_KEYS:
                raise ReportError(
                    f"report.yaml kind {kind['id']}: bad field {field}={key}"
                )
        for key in TITLE_KEY_RE.findall(kind.get("title", "")):
            if key not in QUERY_KEYS:
                raise ReportError(f"report.yaml kind {kind['id']}: bad title key {key}")


def clean_context(
    context: dict[str, str], agents: list[str], site_url: str
) -> dict[str, str]:
    """Only known keys with id-shaped values; a page becomes a full URL on this site."""
    clean = {}
    for key, value in context.items():
        if key not in QUERY_KEYS + BUILD_KEYS or not isinstance(value, str):
            continue
        if key == "page":
            if PAGE_RE.fullmatch(value):
                clean[key] = site_url + value
        elif ID_RE.fullmatch(value) and (key != "agent" or value in agents):
            clean[key] = value
    return clean


def issue_url(
    report: dict[str, Any],
    kind: dict[str, Any],
    context: dict[str, str],
    agents: list[str],
    site_url: str,
) -> str:
    """The new-issue URL for one kind: its form, plus every field the context can fill."""
    clean = clean_context(context, agents, site_url)
    params = {"template": kind["template"]}
    title = kind.get("title", "")
    if title and set(TITLE_KEY_RE.findall(title)) <= set(clean):
        params["title"] = TITLE_KEY_RE.sub(lambda m: clean[m.group(1)], title)
    for field, key in kind["fields"].items():
        if key in clean:
            params[field] = clean[key]
    return f"{report['github']}{kind['repo']}/issues/new?{urlencode(params)}"


def report_link(**context: str) -> str:
    """A link to /report/ carrying page context; values that are not id-shaped are left out."""
    query = {
        key: value
        for key, value in context.items()
        if key in QUERY_KEYS and (PAGE_RE if key == "page" else ID_RE).fullmatch(value)
    }
    return PATH + (f"?{urlencode(query)}" if query else "")


def build_context(site: Site) -> dict[str, str]:
    """The refs this site was built from: known for every report, whatever page sent you."""
    return {"catalog_ref": site.catalog_ref, "engine_ref": site.framework_ref}


def build(site: Site, out_dir: Path, templates: Path) -> tuple[str, str, str]:
    """The report page, one card per kind after the security card, and its twin."""
    report = site.data["report"]
    agents = site.data["builder_clients"]["order"]
    site_url = site.data["site_url"]
    fixed = build_context(site)
    urls = {
        kind["id"]: issue_url(report, kind, fixed, agents, site_url)
        for kind in report["kinds"]
    }
    security = report["security"]
    links = Safe(
        "".join(
            render_file(
                templates / PARTIALS / "report-link.html",
                URL=link["url"],
                LABEL=link["label"],
            )
            for link in security["links"]
        )
    )
    cards = Safe(
        "".join(
            render_file(
                templates / PARTIALS / "report-card.html",
                ID=kind["id"],
                HEADING=kind["heading"],
                BODY=Prose(kind["body"]),
                INCLUDE_HEADING=report["include_heading"],
                INCLUDE=Safe(
                    "".join(
                        render_file(
                            templates / PARTIALS / "plain-li.html", TEXT=Prose(item)
                        )
                        for item in kind["include"]
                    )
                ),
                HREF=urls[kind["id"]],
                FIELDS=" ".join(
                    f"{field}={key}"
                    for field, key in kind["fields"].items()
                    if key in QUERY_KEYS
                ),
                TITLE=kind.get("title", ""),
                BUTTON=kind["button"],
            )
            for kind in report["kinds"]
        )
    )
    write_page(
        site,
        out_dir,
        templates,
        path=PATH,
        title=report["title"],
        description=report["description"],
        content=Safe(
            render_file(
                templates / "report.html",
                TITLE=report["title"],
                SUB=Prose(report["description"]),
                SEC_ID=security["id"],
                SEC_HEADING=security["heading"],
                SEC_BODY=Prose(security["body"]),
                SEC_LINKS=links,
                SITE_URL=site_url,
                AGENTS=" ".join(agents),
                CARDS=cards,
                NOTE=Prose(report["note"]),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": report["title"],
            "description": report["description"],
        },
        nav="report",
        scripts=("common.js", "report.js"),
    )
    twin = render_text_file(
        templates / "md" / "report.md",
        TITLE=report["title"],
        SUB=report["description"],
        AGENT_NOTE=report["agent_note"],
        SEC_HEADING=security["heading"],
        SEC_BODY=security["body"],
        SEC_LINKS="".join(
            f"- [{md(link['label'])}]({link['url']})\n" for link in security["links"]
        ),
        KINDS="".join(
            f"## {md(kind['heading'])}\n\n{kind['body']}\n\n"
            f"{report['include_heading']}:\n\n"
            + "".join(f"- {item}\n" for item in kind["include"])
            + f"\nForm: {urls[kind['id']]}\n\n"
            for kind in report["kinds"]
        ),
        NOTE=report["note"],
    )
    write_md(out_dir, PATH, twin)
    return PATH, PATH + "index.md", twin


def link_text(site: Site, key: str, **subs: str) -> str:
    """The text of a link to /report/ on another page, from report.yaml."""
    return data_fill(
        site.data["report"]["links"][key],
        {f"__{name.upper()}__": value for name, value in subs.items()},
    )
