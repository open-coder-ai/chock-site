"""Assemble the Site model and write dist/data/site.json."""

import json
from pathlib import Path
from typing import Any

from . import catalog as catalog_mod
from . import engine
from . import presets as presets_mod
from .model import Site

SITE_JSON = "data/site.json"


def load_site_data(data_dir: Path) -> dict[str, Any]:
    """The repo's data/site.json: nav, texts, links, command template and warning texts."""
    return json.loads((data_dir / "site.json").read_text(encoding="utf-8"))


def build_site(
    catalog: Path,
    catalog_ref: str,
    catalog_source: str,
    release: str | None,
    data_dir: Path,
) -> Site:
    """Every input the generated site needs, computed from the pinned catalog."""
    site_data = load_site_data(data_dir)
    hidden = catalog_mod.load_hidden(data_dir)
    presets = presets_mod.load_presets(data_dir / "presets.yaml")
    policies = catalog_mod.load_policies(catalog, hidden, catalog_ref)
    presets_mod.validate_presets(presets, {p.id for p in policies}, hidden)

    for policy in policies:
        policy.sha256 = engine.pack_hash(catalog / policy.path)
    picks = [{"id": p.id, "version": p.version, "sha256": p.sha256} for p in policies]
    selection = engine.build_selection(picks, catalog_source, catalog_ref, release)
    labels = engine.policy_labels(catalog, selection)
    catalog_mod.apply_labels(policies, labels, engine.label_words())
    catalog_mod.apply_groups(policies, presets)

    visible = {p.id for p in policies}
    rules = [
        rule
        for rule in engine.warning_rules()
        if all(pid in visible for pid in rule.get("policies", []))
    ]
    return Site(
        catalog_source=catalog_source,
        catalog_ref=catalog_ref,
        release=release,
        label_words=engine.label_words(),
        policies=policies,
        presets=presets,
        warning_rules=rules,
        warning_texts=dict(site_data["warning_texts"]),
        command=str(site_data["command"]),
        data=site_data,
    )


def site_dict(site: Site) -> dict[str, Any]:
    """The generated site.json shape (plan, PR 1)."""
    catalog: dict[str, Any] = {"source": site.catalog_source, "ref": site.catalog_ref}
    if site.release is not None:
        catalog["release"] = site.release
    return {
        "catalog": catalog,
        "label_words": site.label_words,
        "policies": [
            {
                "id": p.id,
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
                "source_url": p.source_url,
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
    }


def write_site_json(site: Site, out_dir: Path) -> Path:
    """dist/data/site.json, pretty JSON with a trailing newline."""
    path = out_dir / SITE_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(site_dict(site), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
