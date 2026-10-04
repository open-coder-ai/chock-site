"""Dataclasses for the site build: Policy, Preset and Site."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Latest:
    """A policy's newest changelog entry."""

    version: str
    date: str
    change: str


@dataclass
class Policy:
    """One visible catalog policy, ready for pages and JSON."""

    id: str
    path: str
    name: str
    version: str
    description: str
    eval_cases: int
    eval_executed: int
    latest: Latest
    source_url: str
    sha256: str = ""
    keyword: str = ""
    word: str = ""
    says: str = ""
    misses: str | None = None
    where: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)


@dataclass
class Preset:
    """A named starting selection from data/presets.yaml."""

    id: str
    title: str
    summary: str
    members: list[str]


@dataclass
class Site:
    """Everything the generated site.json carries."""

    catalog_source: str
    catalog_ref: str
    release: str | None
    label_words: dict[str, str]
    policies: list[Policy]
    presets: list[Preset]
    warning_rules: list[dict[str, Any]]
    warning_texts: dict[str, str]
    command: str
    data: dict[str, Any] = field(default_factory=dict)
