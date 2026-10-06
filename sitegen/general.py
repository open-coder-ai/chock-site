"""The General agents section: one fixed 'design in progress' page."""

from pathlib import Path

from .model import SectionResult, Site, Track
from .pageparts import badge, write_md, write_page
from .render import Prose, Safe, render_file, render_text_file

MD = "md"

_NAV = [{"key": "overview", "label": "Overview"}]


def build(site: Site, track: Track, out_dir: Path, templates: Path) -> SectionResult:
    """The section's one page, its Markdown twin and its llms.txt block."""
    page = site.data["pages"]["general"]
    gen = site.data["general"]
    write_page(
        site,
        out_dir,
        templates,
        path=f"/{track.slug}/",
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / "general.html",
                TITLE=track.title,
                BADGE=badge(site, templates, "in_design"),
                SUMMARY=Prose(track.summary),
                NOTHING=gen["nothing"],
                FOLLOW_LABEL=gen["follow_label"],
                FOLLOW_URL=gen["follow_url"],
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": track.title,
            "description": track.summary,
        },
        nav=track.id,
        section=(track, "overview", _NAV),
    )
    twin = render_text_file(
        templates / MD / "general.md",
        TITLE=track.title,
        BADGE=site.data["texts"]["design_badge"],
        SUMMARY=track.summary,
        NOTHING=gen["nothing"],
        FOLLOW_LABEL=gen["follow_label"],
        FOLLOW_URL=gen["follow_url"],
    )
    write_md(out_dir, f"/{track.slug}/", twin)
    llms = (
        f"## {track.title}\n\n"
        f"- [{track.title}](/{track.slug}/index.md): design in progress\n"
    )
    return SectionResult(
        pages=[f"/{track.slug}/"],
        llms=llms,
        docs=[(f"/{track.slug}/index.md", twin)],
    )
