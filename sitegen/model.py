"""Dataclasses for the site build: Track, Policy, Preset, Site, SectionResult."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Track:
    """One site section from data/tracks.yaml (plan 0.1)."""

    id: str
    slug: str
    title: str
    status: str
    summary: str


@dataclass
class Latest:
    """A policy's newest changelog entry."""

    version: str
    date: str
    change: str


@dataclass
class Example:
    """One eval-suite case shown on a policy page (plan 5.5)."""

    word: str
    prompt: str
    command: str | None = None


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
    track: str = "coding"
    enforces: str = ""
    sha256: str = ""
    keyword: str = ""
    tier: str = ""
    word: str = ""
    says: str = ""
    misses: str | None = None
    where: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    examples: list[Example] = field(default_factory=list)
    client_labels: dict[str, dict[str, str]] = field(default_factory=dict)
    status: str | None = None


@dataclass
class DemoCase:
    """One home-page terminal tab: a blocking eval case taken from a policy's suite."""

    policy: str
    case: str
    command: str | None
    files: dict[str, str]


@dataclass
class Incident:
    """One row of the home incident table; every policy id is a visible policy."""

    incident: str
    flaw: str
    policies: list[str]


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
    framework_ref: str
    release: str | None
    tracks: list[Track]
    label_words: dict[str, dict[str, str]]
    policies: list[Policy]
    presets: list[Preset]
    warning_rules: list[dict[str, Any]]
    warning_texts: dict[str, str]
    command: str
    data: dict[str, Any] = field(default_factory=dict)
    demo: list[DemoCase] = field(default_factory=list)
    incidents: list[Incident] = field(default_factory=list)


@dataclass
class SectionResult:
    """What a section builder hands back: sitemap paths, llms block, twins."""

    pages: list[str]
    llms: str
    docs: list[tuple[str, str]]
    data_lines: str = ""
