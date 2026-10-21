"""Tiers, counts and command lines for the Git repositories section (data/repos.yaml)."""

import re
import shlex
from typing import Any

from .model import Policy
from .pageparts import PageError

TIER_FIELDS = ("key", "word", "heading", "glyph", "meaning")
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def check_tiers(tiers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The tiers from repos.yaml; each has display fields and one match rule, keys are unique."""
    seen: set[str] = set()
    for tier in tiers:
        missing = [f for f in TIER_FIELDS if not tier.get(f)]
        rules = [r for r in ("equals", "starts_with") if tier.get(r)]
        if missing or len(rules) != 1:
            raise PageError(
                f"repos.yaml tier {tier.get('key')}: needs {TIER_FIELDS} and one rule"
            )
        if tier["key"] in seen:
            raise PageError(f"repos.yaml repeats tier {tier['key']}")
        seen.add(tier["key"])
    return tiers


def tier_for(enforces: str, tiers: list[dict[str, Any]]) -> str:
    """The tier key for a registry `enforces` value; an unknown value fails the build."""
    for tier in tiers:
        if tier.get("equals") == enforces or (
            tier.get("starts_with") and enforces.startswith(tier["starts_with"])
        ):
            return tier["key"]
    raise PageError(f"registry enforces {enforces!r} matches no tier in repos.yaml")


def apply_tiers(policies: list[Policy], tiers: list[dict[str, Any]]) -> None:
    """Set each policy's repository tier from its registry `enforces` value."""
    for policy in policies:
        policy.tier = tier_for(policy.enforces, tiers)


def merge_display(
    tiers: list[dict[str, Any]], glyphs: dict[str, str], meanings: dict[str, str]
) -> None:
    """Add the tiers' glyphs and meanings to the shared maps; a clash with another value fails."""
    for tier in tiers:
        for table, key, value in (
            (glyphs, tier["key"], tier["glyph"]),
            (meanings, tier["word"], tier["meaning"]),
        ):
            if table.get(key, value) != value:
                raise PageError(f"repos.yaml tier {tier['key']} clashes on {key!r}")
            table[key] = value


def counts(policies: list[Policy], tiers: list[dict[str, Any]]) -> dict[str, int]:
    """Policies per tier key, in tier order."""
    return {t["key"]: sum(1 for p in policies if p.tier == t["key"]) for t in tiers}


def fill(template: str, values: dict[str, str]) -> str:
    """One pass over `{name}` placeholders; a name without a value is an error."""

    def lookup(match: re.Match) -> str:
        if match.group(1) not in values:
            raise PageError(f"no value for {{{match.group(1)}}} in {template!r}")
        return values[match.group(1)]

    return PLACEHOLDER.sub(lookup, template)


def shell_arg(value: str) -> str:
    """One value as a single POSIX sh argument (shlex.quote); `shellArg` in static/js/repos.js is its twin."""
    return shlex.quote(value)


def shell_line(template: str, values: dict[str, str]) -> str:
    """A command line: `fill` with every value quoted by `shell_arg`, so no value is read as shell syntax."""
    return fill(template, {name: shell_arg(value) for name, value in values.items()})


def command_lines(
    commands: dict[str, Any], picks: list[Policy], ref: str, ci: bool
) -> list[str]:
    """The setup commands: init, one add per policy sorted by id, sync, then the review note; every value shell-quoted."""
    lines = [commands["init"]]
    for policy in sorted(picks, key=lambda p: p.id):
        values = {"id": policy.id, "ref": ref, "sha256": policy.sha256}
        lines.append(shell_line(commands["add"], values))
    lines.append(commands["sync_ci"] if ci else commands["sync"])
    lines.append(commands["review"])
    return lines


def script_text(commands: dict[str, Any], lines: list[str]) -> str:
    """The downloaded chock-setup.sh: the header lines, then the same commands."""
    return "\n".join([*commands["script_header"], *lines]) + "\n"
