"""Site events (plan AN-1): the allowlist module and the Security page's "What this site counts"."""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .pageparts import PARTIALS, slug
from .render import Prose, Safe, render_file

DATA_FILE = "analytics.yaml"
# The generated module both the browser (dist/js/) and the Pages Function (functions/api/) import.
ALLOWLIST = Path("functions") / "api" / "_allowlist.js"
DIST_ALLOWLIST = Path("js") / "allowlist.js"
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
KEY_RE = re.compile(r"^[a-z]{1,32}$")
HEADER = "// Generated from data/analytics.yaml by `python -m sitegen allowlist`. Do not edit.\n"


class AnalyticsError(ValueError):
    """analytics.yaml names a bad event, key or pattern, or the generated module is stale."""


def load(data_dir: Path) -> dict[str, Any]:
    """analytics.yaml, checked: event names, their props and the value pattern."""
    data = yaml.safe_load((data_dir / DATA_FILE).read_text(encoding="utf-8"))
    keys = data["keys"]
    if len(set(keys)) != len(keys) or not all(KEY_RE.fullmatch(k) for k in keys):
        raise AnalyticsError(f"{DATA_FILE}: keys must be unique lowercase words")
    try:
        re.compile(data["value"])
    except re.error as exc:
        raise AnalyticsError(f"{DATA_FILE}: value is not a pattern: {exc}") from exc
    if not (data["value"].startswith("^") and data["value"].endswith("$")):
        raise AnalyticsError(f"{DATA_FILE}: value must be anchored with ^ and $")
    if not isinstance(data["max_body"], int) or not 0 < data["max_body"] <= 1024:
        raise AnalyticsError(f"{DATA_FILE}: max_body must be 1 to 1024 bytes")
    if not data["events"]:
        raise AnalyticsError(f"{DATA_FILE}: no events")
    for name, event in data["events"].items():
        if not NAME_RE.fullmatch(name):
            raise AnalyticsError(f"{DATA_FILE}: event name {name!r} is not an id")
        props = event["props"]
        if len(set(props)) != len(props) or not set(props) <= set(keys):
            raise AnalyticsError(
                f"{DATA_FILE}: event {name}: props {props} not in keys"
            )
        if not event.get("what"):
            raise AnalyticsError(f"{DATA_FILE}: event {name}: missing what")
    return data


def module_text(data: dict[str, Any]) -> str:
    """The allowlist as an ES module: KEYS, VALUE, MAX_BODY and EVENTS (name -> allowed keys)."""
    events = "".join(
        f"  {json.dumps(name)}: Object.freeze({json.dumps(e['props'])}),\n"
        for name, e in data["events"].items()
    )
    return (
        HEADER
        + f"export const KEYS = Object.freeze({json.dumps(data['keys'])});\n"
        + f"export const VALUE = new RegExp({json.dumps(data['value'])});\n"
        + f"export const MAX_BODY = {data['max_body']};\n"
        + "export const EVENTS = Object.freeze({\n"
        + events
        + "});\n"
    )


def check_module(data: dict[str, Any], root: Path) -> None:
    """Refuse a build whose committed functions/api/_allowlist.js no longer matches the data."""
    path = root / ALLOWLIST
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    if current != module_text(data):
        raise AnalyticsError(
            f"{ALLOWLIST} does not match data/{DATA_FILE}; "
            "run: python -m sitegen allowlist"
        )


def write_module(data: dict[str, Any], path: Path) -> None:
    """Write the allowlist module to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(module_text(data), encoding="utf-8", newline="\n")


def security_html(data: dict[str, Any], templates: Path) -> str:
    """The Security page section that lists every counted action."""
    section = data["security"]
    items = "".join(
        render_file(templates / PARTIALS / "plain-li.html", TEXT=event["what"])
        for event in data["events"].values()
    )
    return render_file(
        templates / PARTIALS / "counted-section.html",
        ID=slug(section["heading"]),
        HEADING=section["heading"],
        BODY=Prose(section["body"]),
        LIST_LABEL=section["list_label"],
        ITEMS=Safe(items),
    )


def security_md(data: dict[str, Any]) -> str:
    """The same section for the Markdown twin."""
    section = data["security"]
    lines = "".join(f"- {event['what']}\n" for event in data["events"].values())
    return (
        f"## {section['heading']}\n\n{section['body']}\n\n"
        f"{section['list_label']}\n\n{lines}\n"
    )
