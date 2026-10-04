"""Write the generated HTML pages into the output dir (PR 1: placeholder index only)."""

from pathlib import Path

from .model import Site
from .render import Safe, render_file

BASE = "base.html"
INDEX = "index.html"


def write_pages(site: Site, out_dir: Path, templates_dir: Path) -> None:
    """A placeholder index.html: base.html carrying the hero text only."""
    texts = site.data["texts"]
    content = render_file(
        templates_dir / INDEX,
        HERO_HEADLINE=texts["hero_headline"],
        HERO_SUB=texts["hero_sub"],
        HERO_NOTE=texts["hero_note"],
    )
    html = render_file(
        templates_dir / BASE,
        TITLE="Home",
        DESCRIPTION=texts["hero_sub"],
        CONTENT=Safe(content),
        FOOTER_LINE=texts["footer_line"],
        CATALOG_REF=site.catalog_ref,
        CATALOG_REF_12=site.catalog_ref[:12],
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8", newline="\n")
