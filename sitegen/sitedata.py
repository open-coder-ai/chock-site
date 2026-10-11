"""Assemble the Site model and write dist/data/site.json."""

import json
from pathlib import Path
from typing import Any

import yaml

from . import (
    analytics,
    authordata,
    clientdata,
    engine,
    homedata,
    quiz,
    repodata,
    report,
)
from . import catalog as catalog_mod
from . import presets as presets_mod
from .model import Site, Track
from .pageparts import data_fill

SITE_JSON = "data/site.json"
YAML_DATA = ("home", "faq", "agents", "repos", "report")
TRACK_FIELDS = ("id", "slug", "title", "status", "summary")
TRACK_STATUSES = ("available", "in_design")


def load_site_data(data_dir: Path) -> dict[str, Any]:
    """site.json plus the YAML page copy (home, faq, agents, repos and report)."""
    data = json.loads((data_dir / "site.json").read_text(encoding="utf-8"))
    for name in YAML_DATA:
        data[name] = yaml.safe_load(
            (data_dir / f"{name}.yaml").read_text(encoding="utf-8")
        )
    return data


def load_tracks(data_dir: Path) -> list[Track]:
    """The site sections from tracks.yaml; a missing field is a build error."""
    raw = yaml.safe_load((data_dir / "tracks.yaml").read_text(encoding="utf-8"))
    tracks = []
    for row in raw["tracks"]:
        missing = [key for key in TRACK_FIELDS if key not in row]
        if missing:
            msg = f"tracks.yaml row {row.get('id', '?')}: missing {missing}"
            raise ValueError(msg)
        if row["status"] not in TRACK_STATUSES:
            msg = f"tracks.yaml row {row['id']}: status {row['status']!r} not in {TRACK_STATUSES}"
            raise ValueError(msg)
        tracks.append(
            Track(
                id=row["id"],
                slug=row["slug"],
                title=row["title"],
                status=row["status"],
                summary=row["summary"],
            )
        )
    return tracks


def build_site(
    catalog: Path,
    catalog_ref: str,
    framework_ref: str,
    catalog_source: str,
    release: str | None,
    data_dir: Path,
) -> Site:
    """Every input the generated site needs, computed from the pinned catalog."""
    site_data = load_site_data(data_dir)
    report.check_report(site_data["report"])
    site_data["analytics"] = analytics.load(data_dir)
    tracks = load_tracks(data_dir)
    hidden = catalog_mod.load_hidden(data_dir)
    presets = presets_mod.load_presets(data_dir / "presets.yaml")
    policies = catalog_mod.load_policies(catalog, hidden, catalog_ref)
    presets_mod.validate_presets(presets, {p.id for p in policies}, hidden)
    shown = {p.id for p in policies}
    site_data["not_shown"] = sorted(
        pid for pid in catalog_mod.registry_ids(catalog) if pid not in shown
    )

    for policy in policies:
        policy.sha256 = engine.pack_hash(catalog / policy.path)
        policy.latest.change = catalog_mod.plain_change(
            policy.latest.change, site_data["texts"]["change_rewrites"]
        )
    picks = [{"id": p.id, "version": p.version, "sha256": p.sha256} for p in policies]
    selection = engine.build_selection_v2(
        picks,
        catalog_source,
        catalog_ref,
        clientdata.ENGINE_CLIENT,
        site_data["builder_clients"]["bundle_version"],
        release,
    )
    labels = engine.policy_labels(catalog, selection)
    catalog_mod.apply_labels(policies, labels, engine.label_words())
    catalog_mod.apply_groups(policies, presets)
    # label_meanings name the agent as __AGENT__: "The agent" on shared pages, its name in the builder.
    site_data["label_meanings_raw"] = site_data["label_meanings"]
    site_data["label_meanings"] = {
        word: data_fill(text, {"__AGENT__": site_data["texts"]["the_agent"]})
        for word, text in site_data["label_meanings_raw"].items()
    }
    site_data["builder_clients"] = clientdata.builder_clients(
        data_dir, site_data, policies, engine.label_words()
    )

    names = [c["name"] for c in site_data["builder_clients"]["clients"].values()]
    for item in site_data["faq"]["questions"]:
        item["a"] = data_fill(item["a"], {"__AGENTS__": ", ".join(names)})

    site_data["author"] = authordata.load_author(data_dir)

    demo = homedata.load_demo(catalog, data_dir, policies)
    incident_copy, incidents = homedata.load_incidents(data_dir, policies)
    site_data["incidents"] = incident_copy
    site_data["quiz"] = quiz.load_quiz(
        data_dir, presets, set(engine.label_words()), site_data["builder_clients"]
    )

    tiers = repodata.check_tiers(site_data["repos"]["tiers"])
    repodata.apply_tiers(policies, tiers)
    repodata.merge_display(tiers, site_data["glyphs"], site_data["label_meanings"])
    site_data["repos_quiz"] = quiz.load_repos_quiz(
        data_dir,
        presets,
        set(engine.label_words()),
        {t["key"] for t in tiers},
        site_data["builder_clients"],
    )

    visible = {p.id for p in policies}
    rules = [
        rule
        for rule in engine.warning_rules()
        if all(pid in visible for pid in rule.get("policies", []))
    ]
    rules = clientdata.drop_engine_untested(rules, site_data["builder_clients"])
    return Site(
        catalog_source=catalog_source,
        catalog_ref=catalog_ref,
        framework_ref=framework_ref,
        release=release,
        tracks=tracks,
        label_words={
            "coding": engine.label_words(),
            "repos": {t["key"]: t["word"] for t in tiers},
        },
        policies=policies,
        presets=presets,
        warning_rules=rules,
        warning_texts=dict(site_data["warning_texts"]),
        command=str(site_data["builder_clients"]["commands"]["witnessed"]),
        data=site_data,
        demo=demo,
        incidents=incidents,
    )


def site_dict(site: Site) -> dict[str, Any]:
    """The generated site.json shape (plan, PR 1)."""
    catalog: dict[str, Any] = {"source": site.catalog_source, "ref": site.catalog_ref}
    if site.release is not None:
        catalog["release"] = site.release
    return {
        "catalog": catalog,
        "tracks": [
            {
                "id": t.id,
                "slug": t.slug,
                "title": t.title,
                "status": t.status,
                "summary": t.summary,
            }
            for t in site.tracks
        ],
        "label_words": site.label_words,
        "policies": [
            {
                "id": p.id,
                "track": p.track,
                "name": p.name,
                "version": p.version,
                "sha256": p.sha256,
                "keyword": p.keyword,
                "word": p.word,
                "says": p.says,
                "description": p.description,
                "misses": p.misses,
                "where": p.where,
                "groups": p.groups,
                "eval_cases": p.eval_cases,
                "eval_executed": p.eval_executed,
                "latest": {
                    "version": p.latest.version,
                    "date": p.latest.date,
                    "change": p.latest.change,
                },
                "agent_labels": {
                    client: about["labels"][p.id]
                    for client, about in site.data["builder_clients"]["clients"].items()
                },
                **({"status": p.status} if p.status else {}),
                "source_url": p.source_url,
                "enforces": p.enforces,
                "examples": [
                    {"word": e.word, "prompt": e.prompt, "command": e.command}
                    for e in p.examples
                ],
            }
            for p in site.policies
        ],
        "presets": [
            {
                "id": p.id,
                "title": p.title,
                "summary": p.summary,
                "members": list(p.members),
            }
            for p in site.presets
        ],
        "warning_rules": site.warning_rules,
        "warning_texts": site.warning_texts,
        "command": site.command,
        "builder_texts": site.data["builder_texts"],
        "builder_clients": site.data["builder_clients"],
        "quiz": site.data["quiz"],
        "repos": {
            "tiers": [
                {k: t[k] for k in ("key", "word", "glyph", "meaning")}
                for t in site.data["repos"]["tiers"]
            ],
            "tier_of": {p.id: p.tier for p in site.policies},
            "commands": site.data["repos"]["commands"],
            "quiz": site.data["repos_quiz"],
        },
    }


def write_site_json(site: Site, out_dir: Path) -> Path:
    """dist/data/site.json, pretty JSON with a trailing newline."""
    path = out_dir / SITE_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(site_dict(site), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path
