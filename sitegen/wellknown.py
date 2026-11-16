"""/.well-known/security.txt (RFC 9116) and the IndexNow key file, from data/well-known.yaml."""

import datetime as dt
import re
from pathlib import Path
from typing import Any

import yaml

from .docsmd import sections
from .pageparts import PageError
from .paths import safe_join
from .render import render_text_file

SOURCE = "well-known.yaml"
TEMPLATE = Path("well-known") / "security.txt"
# A URL in a Markdown autolink, <https://...>, with nothing that could end a field line.
AUTOLINK = re.compile(r"<(https://[^\s<>]+)>")
FIELD_VALUE = re.compile(r"[^\s]+")
# IndexNow keys: 8 to 128 characters of a-z, A-Z, 0-9 and dash.
INDEXNOW_KEY = re.compile(r"[a-zA-Z0-9-]{8,128}")


def load(data_dir: Path) -> dict[str, Any]:
    """data/well-known.yaml."""
    return yaml.safe_load((data_dir / SOURCE).read_text(encoding="utf-8"))


def contact(security_md: str, section: str) -> str:
    """The one https autolink in `section` of chock's SECURITY.md; none or several fails."""
    urls = AUTOLINK.findall(sections(security_md, [section]))
    if len(urls) != 1:
        raise PageError(
            f"SECURITY.md section {section!r}: {len(urls)} <https://...> links, need 1"
        )
    return urls[0]


def expires(today: dt.date, days: int) -> str:
    """00:00Z on `today` plus `days` days, as an RFC 3339 UTC timestamp."""
    if not 1 <= days <= 365:
        raise PageError(f"{SOURCE}: expires_days must be 1 to 365, got {days}")
    return (today + dt.timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")


def security_txt(
    conf: dict[str, Any],
    docs_source: dict[str, str | None],
    site_url: str,
    engine_repo: str,
    engine_ref: str,
    today: dt.date,
    templates: Path,
) -> str:
    """The security.txt text: every field one line, each value a single token."""
    text = docs_source.get(conf["source_file"])
    if text is None:
        raise PageError(f"{SOURCE}: {conf['source_file']} is not in the docs snapshot")
    fields = {
        "CONTACT": contact(text, conf["source_section"]),
        "EXPIRES": expires(today, conf["expires_days"]),
        "POLICY": f"{engine_repo}/blob/{engine_ref}/{conf['policy_path']}",
        "CANONICAL": f"{site_url}/{conf['path']}",
        "LANGUAGES": conf["preferred_languages"],
    }
    for name, value in fields.items():
        if not FIELD_VALUE.fullmatch(value):
            raise PageError(f"security.txt {name}: {value!r} is not one token")
    return render_text_file(templates / TEMPLATE, **fields)


def indexnow_key(conf: dict[str, Any]) -> str:
    """The IndexNow key from data, checked against the protocol's character rules."""
    key = conf["key"]
    if not isinstance(key, str) or not INDEXNOW_KEY.fullmatch(key):
        raise PageError(f"{SOURCE}: indexnow.key must match {INDEXNOW_KEY.pattern}")
    return key


def write(
    out_dir: Path,
    data_dir: Path,
    templates: Path,
    docs_source: dict[str, str | None],
    site_url: str,
    engine_repo: str,
    engine_ref: str,
    today: dt.date | None = None,
) -> None:
    """Write dist/.well-known/security.txt and dist/<key>.txt."""
    conf = load(data_dir)
    day = today or dt.datetime.now(dt.UTC).date()
    sec = conf["security_txt"]
    text = security_txt(
        sec, docs_source, site_url, engine_repo, engine_ref, day, templates
    )
    path = safe_join(out_dir, sec["path"], f"{SOURCE} security_txt.path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    key = indexnow_key(conf["indexnow"])
    # The file holds the key and nothing else, as IndexNow reads it.
    (out_dir / f"{key}.txt").write_text(key, encoding="utf-8", newline="\n")
