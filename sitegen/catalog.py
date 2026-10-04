"""Read registry.yaml and each manifest into Policy records."""

import re
import subprocess
from pathlib import Path

import yaml

from .model import Latest, Policy

REGISTRY = "registry.yaml"
MANIFEST = "manifest.yaml"
LIFECYCLE_HIDDEN = {"deprecated", "retired"}
MISSES_MARKERS = ("Misses:", "Not caught here:")
WHERE_MAP = (
    ("shell command", "command"),
    ("file writes", "write"),
    ("turn end", "turn-end"),
    ("advisory", "text"),
)
CATALOG_TREE = "https://github.com/open-coder-ai/chock-catalog/tree/"


class CatalogError(Exception):
    """A catalog checkout that cannot be read or is at the wrong commit."""


def catalog_head(catalog: Path) -> str:
    """The HEAD sha of the catalog checkout."""
    result = subprocess.run(
        ["git", "-C", str(catalog), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"{catalog}: not a git checkout ({result.stderr.strip()})"
        raise CatalogError(msg)
    return result.stdout.strip()


def load_hidden(data_dir: Path) -> set[str]:
    """Policy ids from data/hidden.yaml that are never shown."""
    data = yaml.safe_load((data_dir / "hidden.yaml").read_text(encoding="utf-8")) or {}
    return set(data.get("hidden") or [])


def _collapse(text: object) -> str:
    return " ".join(str(text or "").split())


def extract_misses(description: str) -> str | None:
    """Text after the first misses marker, through the next period that ends a sentence."""
    starts = [
        (i, len(marker))
        for marker in MISSES_MARKERS
        if (i := description.find(marker)) != -1
    ]
    if not starts:
        return None
    start, width = min(starts)
    rest = description[start + width :]
    end = re.search(r"\.(?=\s|$)", rest)
    return rest[: end.end() if end else len(rest)].strip()


def where_tags(says: str) -> list[str]:
    """Tags derived from a label's `says` text (plan 5.4)."""
    return [tag for needle, tag in WHERE_MAP if needle in says]


def load_policies(catalog: Path, hidden: set[str], catalog_ref: str) -> list[Policy]:
    """Every registry policy that is not hidden or retired, sorted by id."""
    registry = yaml.safe_load((catalog / REGISTRY).read_text(encoding="utf-8")) or {}
    policies = []
    for row in registry.get("policies", []):
        policy_id = str(row["id"])
        if policy_id in hidden:
            continue
        manifest = yaml.safe_load(
            (catalog / row["path"] / MANIFEST).read_text(encoding="utf-8")
        )
        status = (manifest.get("lifecycle") or {}).get("status")
        if status in LIFECYCLE_HIDDEN:
            continue
        first = (manifest.get("changelog") or [{}])[0]
        changes = first.get("changes") or [""]
        policies.append(
            Policy(
                id=policy_id,
                path=str(row["path"]),
                name=_collapse(manifest.get("name") or policy_id),
                version=str(row["version"]),
                description=_collapse(
                    manifest.get("description") or row.get("description")
                ),
                eval_cases=int(row.get("eval_cases") or 0),
                eval_executed=int(row.get("eval_executed") or 0),
                latest=Latest(
                    version=str(first.get("version", "")),
                    date=str(first.get("date", "")),
                    change=_collapse(changes[0]),
                ),
                source_url=f"{CATALOG_TREE}{catalog_ref}/{row['path']}",
            )
        )
    return sorted(policies, key=lambda p: p.id)


def apply_labels(policies: list[Policy], labels: dict, words: dict[str, str]) -> None:
    """Set each policy's keyword, displayed word, `says` and `where` from engine labels."""
    for policy in policies:
        label = labels[policy.id]
        policy.keyword = label.keyword
        policy.word = words[label.keyword]
        policy.says = label.says
        policy.where = where_tags(label.says)


def apply_groups(policies: list[Policy], presets: list) -> None:
    """Set each policy's `groups` to the preset ids that list it, in presets.yaml order."""
    for policy in policies:
        policy.groups = [preset.id for preset in presets if policy.id in preset.members]
