"""The Coding agents section: its pages, Markdown twins and /api/coding/ files."""

import json
from pathlib import Path
from typing import Any

from . import authordata, clientpage, engine
from .catalog import first_sentence
from .model import Policy, SectionResult, Site, Track
from .pageparts import (
    PARTIALS,
    PageError,
    badge,
    chip,
    counts,
    data_fill,
    install_command,
    label_chips,
    policies_sorted,
    render_steps,
    write_md,
    write_page,
)
from .render import Prose, Safe, render_file, render_text_file
from .sitedata import site_dict

MD = "md"


def _home(
    site: Site, track: Track, out_dir: Path, templates: Path, counts_: dict[str, Any]
) -> tuple[str, str]:
    """The coding section home (plan 6.7): glance counts, presets, steps."""
    home = site.data["home"]["coding"]
    texts = site.data["texts"]
    subs = {"__COUNT__": str(counts_["total"])}
    stats = "".join(
        [
            render_file(
                templates / PARTIALS / "home-stat.html",
                EXTRA="",
                NUM=str(counts_["total"]),
                LABEL="policies",
            )
        ]
        + [
            render_file(
                templates / PARTIALS / "home-stat.html",
                EXTRA=" stat-block" if key == "block" else "",
                NUM=str(counts_["label"][key]),
                LABEL=f"{site.data['glyphs'][key]} {site.label_words[track.id][key]}",
            )
            for key in site.label_words[track.id]
        ]
        + [
            render_file(
                templates / PARTIALS / "home-stat.html",
                EXTRA="",
                NUM=str(counts_["presets"]),
                LABEL="presets",
            )
        ]
    )
    preset_cards = "".join(
        render_file(
            templates / PARTIALS / "home-preset-card.html",
            ID=preset.id,
            TITLE=preset.title,
            COUNT=str(len(preset.members)),
            SUMMARY=Prose(preset.summary),
        )
        for preset in site.presets
    )
    client_cards = render_file(
        templates / PARTIALS / "agent-card.html",
        URL="/coding/builder/",
        NAME="Claude Code",
        REPO=home["claude_repo"],
        HOW=home["claude_how"],
    ) + "".join(
        render_file(
            templates / PARTIALS / "agent-card.html",
            URL=client["repo"],
            NAME=client["name"],
            REPO=client["repo"].rsplit("/", 1)[-1],
            HOW=home["repo_how"],
        )
        for client in site.data["clients"]
    )
    page = site.data["pages"]["coding"]
    write_page(
        site,
        out_dir,
        templates,
        path=f"/{track.slug}/",
        title=page["title"],
        description=data_fill(page["description"], subs),
        content=Safe(
            render_file(
                templates / track.slug / "home.html",
                BADGE=badge(site, templates, "available"),
                H1=home["h1"],
                INTRO=Prose(home["intro"]),
                PRIMARY_CTA=site.data["home"]["primary_cta"],
                SECONDARY_CTA=site.data["home"]["secondary_cta"],
                GLANCE_HEADING=home["glance_heading"],
                GLANCE_LINK=home["glance_link"],
                STAT_CARDS=Safe(stats),
                COMPUTED_NOTE=texts["computed_note"],
                PRESETS_HEADING=home["presets_heading"],
                PRESETS_INTRO=Prose(home["presets_intro"]),
                PRESET_CARDS=Safe(preset_cards),
                STEPS=render_steps(site, templates),
                CLIENTS_HEADING=home["clients_heading"],
                CLIENTS_LINE=Prose(home["clients_line"]),
                CLIENT_CARDS=Safe(client_cards),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": f"{page['title']} · chock.sh",
            "description": data_fill(page["description"], subs),
        },
        nav=track.id,
        section=(track, "overview"),
    )
    twin = render_text_file(
        templates / MD / track.slug / "home.md",
        H1=home["h1"],
        INTRO=home["intro"],
        GLANCE_HEADING=home["glance_heading"],
        GLANCE_LINE=(
            f"{counts_['total']} policies — "
            + ", ".join(
                f"{site.label_words[track.id][key]} {counts_['label'][key]}"
                for key in site.label_words[track.id]
            )
            + f" — {counts_['presets']} presets."
        ),
        PRESETS_HEADING=home["presets_heading"],
        PRESETS_INTRO=home["presets_intro"],
        PRESET_LINES="".join(
            f"- {preset.title} ({len(preset.members)} policies): {preset.summary}\n"
            for preset in site.presets
        ),
        STEPS_HEADING=site.data["home"]["steps_heading"],
        STEP_LINES="".join(
            f"{i}. {step['title']} — {step['body']}\n"
            for i, step in enumerate(site.data["home"]["steps"], start=1)
        ),
        CLIENTS_HEADING=home["clients_heading"],
        CLIENTS_LINE=f"{home['clients_line']} {home['clients_link']}: /coding/clients/",
    )
    write_md(out_dir, f"/{track.slug}/", twin)
    return f"/{track.slug}/", twin


def _where_text(site: Site, policy: Policy) -> str:
    """'Shell command · file write' — the policy's where tags as one line."""
    text = " · ".join(site.data["where_names"][tag] for tag in policy.where)
    return text[:1].upper() + text[1:]


def _when_text(site: Site, policy: Policy) -> str:
    """'Before the command runs' — when the policy fires, from its where tags."""
    text = " · ".join(site.data["when_names"][tag] for tag in policy.where)
    return text[:1].upper() + text[1:]


def _dist_bar(
    site: Site, track: Track, templates: Path, counts_: dict[str, Any]
) -> tuple[str, str]:
    """The label-distribution segments (text inside) and its aria label."""
    words = site.label_words[track.id]
    segs = "".join(
        render_file(
            templates / PARTIALS / "dist-seg.html",
            KEY=key,
            NUM=str(counts_["label"][key]),
            WORD=words[key],
        )
        for key in words
    )
    label = "Label mix: " + ", ".join(
        f"{counts_['label'][key]} {words[key]}" for key in words
    )
    return label, segs


def _policies_list(
    site: Site, track: Track, out_dir: Path, templates: Path, counts_: dict[str, Any]
) -> tuple[str, str]:
    """The filterable policy list and its twin."""
    texts = site.data["texts"]
    subs = {"__COUNT__": str(counts_["total"])}
    rows = []
    for policy in policies_sorted(site):
        rows.append(
            render_file(
                templates / PARTIALS / "policy-row.html",
                ID=policy.id,
                KEYWORD=policy.keyword,
                WHERE=" ".join(policy.where),
                GROUPS=" ".join(policy.groups),
                NAME=policy.name,
                CHIP=chip(site, templates, policy, track.id),
                DESC=Prose(first_sentence(policy.description)),
                WHERE_TEXT=_where_text(site, policy),
                VERSION=policy.version,
            )
        )
    where_chips = "".join(
        render_file(
            templates / PARTIALS / "filter-chip.html",
            FACET="where",
            VALUE=tag,
            GLYPH_KEY="none",
            GLYPH="",
            WORD=site.data["where_names"][tag],
            COUNT=str(counts_["where"][tag]),
        )
        for tag in site.data["where_names"]
        if tag in counts_["where"]
    )
    options = "".join(
        render_file(
            templates / PARTIALS / "option.html",
            VALUE=preset.id,
            LABEL=f"{preset.title} · {len(preset.members)}",
        )
        for preset in site.presets
    )
    intro = data_fill(texts["policies_intro"], subs)
    dist_label, dist_segs = _dist_bar(site, track, templates, counts_)
    page = site.data["pages"]["policies"]
    path = f"/{track.slug}/policies/"
    write_page(
        site,
        out_dir,
        templates,
        path=path,
        title=page["title"],
        description=data_fill(page["description"], subs),
        content=Safe(
            render_file(
                templates / track.slug / "policies.html",
                H1=f"{counts_['total']} guardrails, each labelled with what it does.",
                INTRO=Prose(intro),
                DIST_LABEL=dist_label,
                DIST_SEGS=Safe(dist_segs),
                COMPUTED_NOTE=texts["computed_note"],
                SEARCH_PLACEHOLDER=data_fill(texts["policies_search"], subs),
                GROUP_OPTIONS=Safe(options),
                LABEL_CHIPS=Safe(label_chips(site, templates, counts_, track.id)),
                WHERE_CHIPS=Safe(where_chips),
                SHOWING=f"Showing {counts_['total']} of {counts_['total']}",
                ROWS=Safe("".join(rows)),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": "chock policies",
            "numberOfItems": counts_["total"],
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i,
                    "name": p.name,
                    "url": f"{site.data['site_url']}/{track.slug}/policies/{p.id}/",
                }
                for i, p in enumerate(policies_sorted(site), start=1)
            ],
        },
        nav=track.id,
        section=(track, "policies"),
        scripts=("common.js", "policies.js"),
    )
    twin = render_text_file(
        templates / MD / track.slug / "policies.md",
        INTRO=Prose(intro),
        ROWS="".join(
            f"- [{policy.name}](/{track.slug}/policies/{policy.id}/index.md) "
            f"(`{policy.id}`, v{policy.version}): {policy.word} — {policy.says}. "
            f"{first_sentence(policy.description)}\n"
            for policy in policies_sorted(site)
        ),
    )
    write_md(out_dir, path, twin)
    return path, twin


def _policy_pages(
    site: Site, track: Track, out_dir: Path, templates: Path
) -> tuple[list[str], list[tuple[str, str]]]:
    """One page and one Markdown twin per visible policy."""
    texts = site.data["texts"]
    presets = {p.id: p for p in site.presets}
    paths: list[str] = []
    docs: list[tuple[str, str]] = []
    for policy in policies_sorted(site):
        plugin_note = ""
        if policy.keyword == "advise" and policy.enforces == "enforced-at-commit":
            plugin_note = render_file(
                templates / PARTIALS / "plugin-note.html",
                NOTE=texts["plugin_repo_note"],
            )
        preset_chip = ""
        also_in = ""
        if policy.groups:
            first = presets[policy.groups[0]]
            preset_chip = render_file(
                templates / PARTIALS / "preset-chip.html",
                ID=first.id,
                TITLE=first.title,
            )
            others = [m for m in first.members if m != policy.id][:5]
            if others:
                also_in = render_file(
                    templates / PARTIALS / "also-in.html",
                    TITLE=first.title,
                    LINKS=Safe(
                        "".join(
                            render_file(
                                templates / PARTIALS / "also-in-link.html",
                                ID=member,
                            )
                            for member in others
                        )
                    ),
                )
        examples = ""
        examples_md = ""
        if policy.examples:
            cards = "".join(
                render_file(
                    templates / PARTIALS / "example-card.html",
                    KIND="allowed" if example.word == "Allowed" else "refused",
                    ICON=Safe(
                        render_file(
                            templates / PARTIALS / "icon-allowed.html"
                            if example.word == "Allowed"
                            else templates / PARTIALS / "icon-refused.html"
                        )
                    ),
                    WORD=example.word,
                    PROMPT=Prose(example.prompt),
                    COMMAND=Safe(
                        render_file(
                            templates / PARTIALS / "command-pre.html",
                            COMMAND=example.command,
                        )
                    )
                    if example.command
                    else Safe(""),
                )
                for example in policy.examples
            )
            examples = render_file(
                templates / PARTIALS / "examples-section.html",
                EXAMPLE_CARDS=Safe(cards),
                EXAMPLES_NOTE=Prose(texts["examples_note"]),
            )
            examples_md = "\n## Examples\n\n" + "".join(
                f"- {e.word}: {e.prompt}"
                + (f" — `{e.command}`" if e.command else "")
                + "\n"
                for e in policy.examples
            )
        content = Safe(
            render_file(
                templates / track.slug / "policy.html",
                ID=policy.id,
                KEYWORD=policy.keyword,
                WHERE=" ".join(policy.where),
                NAME=policy.name,
                VERSION=policy.version,
                CHIP=chip(site, templates, policy, track.id),
                PRESET_CHIP=Safe(preset_chip),
                SAYS=Prose(policy.says.rstrip(".") + "."),
                TIER=policy.tier,
                TIER_WORD=site.label_words["repos"][policy.tier],
                ACTS_ON=_where_text(site, policy),
                WHEN=_when_text(site, policy),
                LABEL_NOTE=Prose(texts["label_box_note"]),
                PLUGIN_NOTE=Safe(plugin_note),
                DESCRIPTION=Prose(policy.description),
                MISSES=Prose(policy.misses or texts["misses_empty"]),
                EXAMPLES_SECTION=Safe(examples),
                LATEST_VERSION=policy.latest.version,
                LATEST_DATE=policy.latest.date,
                LATEST_CHANGE=Prose(policy.latest.change),
                EVAL_EXECUTED=str(policy.eval_executed),
                EVAL_CASES=str(policy.eval_cases),
                SHA256=policy.sha256,
                CATALOG_COMMIT_URL=site.data["links"]["catalog_commit"]
                + site.catalog_ref,
                CATALOG_REF_12=site.catalog_ref[:12],
                SOURCE_URL=policy.source_url,
                PATH=policy.path,
                ALSO_IN=Safe(also_in),
            )
        )
        path = f"/{track.slug}/policies/{policy.id}/"
        alt = (
            '<link rel="alternate" type="application/json" '
            f'href="/api/{track.slug}/policies/{policy.id}.json">'
        )
        write_page(
            site,
            out_dir,
            templates,
            path=path,
            title=f"{policy.name}: {policy.word} {policy.says}",
            description=first_sentence(policy.description),
            content=content,
            jsonld_data={
                "@context": "https://schema.org",
                "@type": "SoftwareSourceCode",
                "name": policy.name,
                "version": policy.version,
                "description": first_sentence(policy.description),
                "codeRepository": policy.source_url,
                "license": "Apache-2.0",
                "programmingLanguage": "Python",
            },
            nav=track.id,
            section=(track, "policies"),
            alt_json=alt,
        )
        twin = render_text_file(
            templates / MD / track.slug / "policy.md",
            ID=policy.id,
            TRACK=policy.track,
            NAME=policy.name,
            VERSION=policy.version,
            WORD=policy.word,
            TIER_WORD=site.label_words["repos"][policy.tier],
            TIER_MEANING=site.data["label_meanings"][
                site.label_words["repos"][policy.tier]
            ],
            KEYWORD=policy.keyword,
            WHERE=" ".join(policy.where) or "none",
            SHA256=policy.sha256,
            SOURCE_URL=policy.source_url,
            CATALOG_REF=site.catalog_ref,
            SAYS=policy.says.rstrip(".") + ".",
            LABEL_NOTE=texts["label_box_note"],
            PLUGIN_NOTE=(" " + texts["plugin_repo_note"] if plugin_note else ""),
            DESCRIPTION=policy.description,
            MISSES=policy.misses or texts["misses_empty"],
            EXAMPLES_MD=examples_md,
            LATEST_VERSION=policy.latest.version,
            LATEST_DATE=policy.latest.date,
            LATEST_CHANGE=policy.latest.change,
            EVAL_EXECUTED=str(policy.eval_executed),
            EVAL_CASES=str(policy.eval_cases),
            CATALOG_COMMIT_URL=site.data["links"]["catalog_commit"] + site.catalog_ref,
            PATH=policy.path,
            GROUPS_MD=", ".join(presets[group].title for group in policy.groups)
            or "none",
        )
        write_md(out_dir, path, twin)
        paths.append(path)
        docs.append((f"{path}index.md", twin))
    return paths, docs


def _member_rows(
    site: Site, track: Track, templates: Path, members: list[Policy], group: str
) -> str:
    """Builder rows for one group's policies."""
    return "".join(
        render_file(
            templates / PARTIALS / "builder-member.html",
            ID=p.id,
            GROUP=group,
            KEYWORD=p.keyword,
            WHERE=" ".join(p.where),
            NAME=p.name,
            CHIP=chip(site, templates, p, track.id),
            SAYS=Prose(p.says),
        )
        for p in members
    )


def quiz_lines(questions: list[dict[str, Any]]) -> str:
    """The start screen's questions and answers as Markdown lines for the twin."""
    lines = []
    for number, question in enumerate(questions, start=1):
        lines.append(f"{number}. {question['title']} {question['hint']}\n")
        for option in question["options"]:
            extra = ""
            if option.get("presets"):
                extra = f" (presets: {', '.join(option['presets'])})"
            elif option.get("allow"):
                extra = f" (labels: {', '.join(option['allow'])})"
            lines.append(f"   - {option['label']}: {option['sub']}{extra}\n")
    return "".join(lines)


def _builder(
    site: Site, track: Track, out_dir: Path, templates: Path, counts_: dict[str, Any]
) -> tuple[str, str]:
    """The builder's static layout and noscript text; builder.js adds the behaviour."""
    texts = site.data["texts"]
    subs = {"__CATALOG_REF_12__": site.catalog_ref[:12]}
    options = "".join(
        render_file(
            templates / PARTIALS / "option.html",
            VALUE=preset.id,
            LABEL=f"{preset.title} · {len(preset.members)}",
        )
        for preset in site.presets
    )
    by_id = {p.id: p for p in site.policies}
    grouped = {member for preset in site.presets for member in preset.members}
    groups = "".join(
        render_file(
            templates / PARTIALS / "builder-group.html",
            ID=preset.id,
            TITLE=preset.title,
            COUNT=str(len(preset.members)),
            MEMBERS=Safe(
                _member_rows(
                    site,
                    track,
                    templates,
                    [by_id[member] for member in preset.members],
                    preset.id,
                )
            ),
        )
        for preset in site.presets
    )
    ungrouped = [p for p in policies_sorted(site) if p.id not in grouped]
    if ungrouped:
        groups += render_file(
            templates / PARTIALS / "builder-group.html",
            ID="none",
            TITLE="In no group",
            COUNT=str(len(ungrouped)),
            MEMBERS=Safe(_member_rows(site, track, templates, ungrouped, "none")),
        )
    clients = site.data["builder_clients"]
    page = site.data["pages"]["builder"]
    path = f"/{track.slug}/builder/"
    write_page(
        site,
        out_dir,
        templates,
        path=path,
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / track.slug / "builder.html",
                SUB=Prose(page["description"]),
                NOSCRIPT=Prose(texts["builder_noscript"]),
                CLIENT_PICKER=Safe(clientpage.picker(clients, templates / track.slug)),
                QUIZ=Safe(
                    render_file(
                        templates / PARTIALS / "quiz.html",
                        TOP=Safe(
                            render_file(
                                templates / PARTIALS / "quiz-top.html",
                                SKIP=site.data["quiz"]["texts"]["skip"],
                            )
                        ),
                    )
                ),
                PRESET_OPTIONS=Safe(options),
                LABEL_CHIPS=Safe(label_chips(site, templates, counts_, track.id)),
                GROUP_SECTIONS=Safe(groups),
                EMPTY=Prose(texts["builder_empty"]),
                NEED_ONE=Prose(texts["builder_need_one"]),
                UNTESTED=Safe(
                    clientpage.untested_lines(clients, templates / track.slug)
                ),
                CLIENT_STEPS=Safe(clientpage.steps(clients, templates / track.slug)),
                HINT=data_fill(texts["builder_outputs_hint"], subs),
                AUTHOR_LINK=Prose(site.data["builder_texts"]["author_link"]),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page["title"],
            "description": page["description"],
        },
        nav=track.id,
        section=(track, "builder"),
        scripts=("common.js", "builder.js"),
        body_end=render_file(templates / PARTIALS / "mobile-bar.html"),
    )
    twin = render_text_file(
        templates / MD / track.slug / "builder.md",
        SUB=Prose(page["description"]),
        NOSCRIPT=texts["builder_noscript"],
        QUIZ_LINES=quiz_lines(site.data["quiz"]["questions"]),
        PRESET_LINES="".join(
            f"- {preset.title} ({len(preset.members)} policies): {preset.summary}\n"
            for preset in site.presets
        ),
        NEED_ONE=texts["builder_need_one"],
        HINT=data_fill(texts["builder_outputs_hint"], subs),
        GRADES_NOTE=""
        if clients["graded"]
        else f"{clients['texts']['grades_pending']}\n",
        AGENT_LINES=clientpage.markdown(clients),
    )
    write_md(out_dir, path, twin)
    return path, twin


def _author(
    site: Site, track: Track, out_dir: Path, templates: Path
) -> tuple[str, str]:
    """The author page's static layout; author.js runs the interview and generators (BV-S2)."""
    author = site.data["author"]
    texts = author["texts"]
    kinds = author["kinds"]
    options = "".join(
        render_file(
            templates / PARTIALS / "author-kind.html",
            ID=kind,
            CHECKED=Safe(" checked" if i == 0 else ""),
            TITLE=spec["title"],
            BLURB=spec["blurb"],
        )
        for i, (kind, spec) in enumerate(kinds.items())
    )
    page = site.data["pages"]["author"]
    path = f"/{track.slug}/author/"
    write_page(
        site,
        out_dir,
        templates,
        path=path,
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / track.slug / "author.html",
                SUB=Prose(page["description"]),
                NOSCRIPT=Prose(texts["noscript"]),
                CLIENT_PICKER=Safe(
                    clientpage.picker(
                        site.data["builder_clients"], templates / track.slug
                    )
                ),
                KIND_LEGEND=texts["kind_legend"],
                KIND_OPTIONS=Safe(options),
                NAME_LABEL=texts["name_label"],
                NAME_HINT=texts["name_hint"],
                NAME_EXAMPLE=texts["name_example"],
                INTERVIEW_HINT=texts["interview_hint"],
                CATALOG_HEADING=texts["catalog_heading"],
                CATALOG_HINT=texts["catalog_hint"],
                SAVED_NOTE=texts["saved_note"],
                CLEAR_LABEL=texts["clear_label"],
                CLEAR_DONE=texts["clear_done"],
                ADVANCED_HEADING=texts["advanced_heading"],
                ADVANCED_HINT=texts["advanced_hint"],
                ERRORS_TITLE=texts["errors_title"],
                SELECTION_HEADING=texts["selection_heading"],
                SELECTION_HINT=texts["selection_hint"],
                SCRIPT_HEADING=texts["script_heading"],
                SCRIPT_HINT=texts["script_hint"],
                SHA_LABEL=texts["sha_label"],
                DOWNLOAD_LABEL=texts["download_label"],
                COPY_LABEL=texts["copy_label"],
                SHARE_LABEL=texts["share_label"],
                SHARE_HINT=texts["share_hint"],
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page["title"],
            "description": page["description"],
        },
        nav=track.id,
        section=(track, "author"),
        scripts=("common.js", "author.js"),
    )
    twin = render_text_file(
        templates / MD / track.slug / "author.md",
        SUB=Prose(page["description"]),
        NOSCRIPT=texts["noscript"],
        KIND_LINES="".join(
            f"- {spec['title']}: {spec['blurb']}\n  "
            + " ".join(f"Q: {field['label']}" for field in spec["fields"])
            + "\n"
            for spec in kinds.values()
        ),
        ENGINE_COMMIT_12=author["engine_commit"][:12],
        SCRIPT_HINT=texts["script_hint"],
    )
    write_md(out_dir, path, twin)
    return path, twin


def _install(
    site: Site, track: Track, out_dir: Path, templates: Path
) -> tuple[str, str]:
    """Install page: engine install, the command, update, remove, file format."""
    data = site.data
    inst = data["install"]
    install_cmd = install_command(site)
    field_rows = Safe(
        "".join(
            render_file(
                templates / PARTIALS / "field-row.html",
                FIELD=row["field"],
                MEANING=row["meaning"],
            )
            for row in inst["file_fields"]
        )
    )
    page = data["pages"]["install"]
    path = f"/{track.slug}/install/"
    write_page(
        site,
        out_dir,
        templates,
        path=path,
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / track.slug / "install.html",
                SUB=Prose(page["description"]),
                INSTALL_HEADING=inst["install_heading"],
                INSTALL_CMD=install_cmd,
                INSTALL_NOTE=Prose(inst["install_note"]),
                RUN_HEADING=inst["run_heading"],
                RUN_BODY=Prose(inst["run_body"]),
                RUN_CMD=inst["run_command"],
                UPDATE_HEADING=inst["update_heading"],
                UPDATE_BODY=Prose(inst["update_body"]),
                REMOVE_HEADING=inst["remove_heading"],
                REMOVE_CMD=inst["remove_command"],
                FILE_HEADING=inst["file_heading"],
                FILE_BODY=Prose(inst["file_body"]),
                FIELD_ROWS=field_rows,
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": page["title"],
            "description": page["description"],
        },
        nav=track.id,
        section=(track, "install"),
    )
    twin = render_text_file(
        templates / MD / track.slug / "install.md",
        SUB=Prose(page["description"]),
        INSTALL_HEADING=inst["install_heading"],
        INSTALL_CMD=install_cmd,
        INSTALL_NOTE=inst["install_note"],
        RUN_HEADING=inst["run_heading"],
        RUN_BODY=inst["run_body"],
        RUN_CMD=inst["run_command"],
        UPDATE_HEADING=inst["update_heading"],
        UPDATE_BODY=inst["update_body"],
        REMOVE_HEADING=inst["remove_heading"],
        REMOVE_CMD=inst["remove_command"],
        FILE_HEADING=inst["file_heading"],
        FILE_BODY=inst["file_body"],
        FIELD_LINES="".join(
            f"- `{row['field']}`: {row['meaning']}\n" for row in inst["file_fields"]
        ),
    )
    write_md(out_dir, path, twin)
    return path, twin


def _clients(
    site: Site, track: Track, out_dir: Path, templates: Path
) -> tuple[str, str]:
    """Other coding clients: the marketplace repo cards."""
    data = site.data
    page = data["pages"]["clients"]
    cards = "".join(
        render_file(
            templates / PARTIALS / "client-card.html",
            NAME=client["name"],
            NOTE=Prose(client["note"]),
            REPO=client["repo"],
            REPO_LABEL=client["repo"].rsplit("/", 1)[-1],
        )
        for client in data["clients"]
    )
    path = f"/{track.slug}/clients/"
    write_page(
        site,
        out_dir,
        templates,
        path=path,
        title=page["title"],
        description=page["description"],
        content=Safe(
            render_file(
                templates / track.slug / "clients.html",
                INTRO=Prose(data["clients_intro"]),
                CLIENT_CARDS=Safe(cards),
                MARKETPLACE=data["links"]["claude_marketplace"],
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page["title"],
            "description": page["description"],
        },
        nav=track.id,
        section=(track, "clients"),
    )
    twin = render_text_file(
        templates / MD / track.slug / "clients.md",
        INTRO=data["clients_intro"],
        CLIENT_LINES="".join(
            f"- [{client['name']}]({client['repo']}): {client['note']}\n"
            for client in data["clients"]
        ),
        MARKETPLACE=data["links"]["claude_marketplace"],
    )
    write_md(out_dir, path, twin)
    return path, twin


def _api(site: Site, track: Track, out_dir: Path) -> None:
    """api/<slug>/*.json: catalog, presets, per-policy records, schema."""
    api = out_dir / "api" / track.slug
    api.mkdir(parents=True, exist_ok=True)
    catalog = {"schema_version": 1, "track": track.id, **site_dict(site)}
    catalog.pop("tracks", None)
    catalog.pop("repos", None)
    catalog["label_words"] = {track.id: site.label_words.get(track.id, {})}
    catalog["policies"] = [p for p in catalog["policies"] if p.get("track") == track.id]
    (api / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (api / "presets.json").write_text(
        json.dumps(
            {"schema_version": 1, "presets": catalog["presets"]},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    policies_dir = api / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    for policy in catalog["policies"]:
        record = {"schema_version": 1, **policy}
        (policies_dir / f"{policy['id']}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    (api / "selection.schema.json").write_text(
        json.dumps(engine.selection_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(site: Site, track: Track, out_dir: Path, templates: Path) -> SectionResult:
    """Build every coding page, Markdown twin and /api/coding/ file."""
    counts_ = counts(site, track.id)
    pages: list[str] = []
    docs: list[tuple[str, str]] = []

    home_path, home_doc = _home(site, track, out_dir, templates, counts_)
    pages.append(home_path)
    docs.append((f"{home_path}index.md", home_doc))

    list_path, list_doc = _policies_list(site, track, out_dir, templates, counts_)
    pages.append(list_path)

    install_path, install_doc = _install(site, track, out_dir, templates)
    pages.append(install_path)

    policy_paths, policy_docs = _policy_pages(site, track, out_dir, templates)
    pages += policy_paths

    builder_path, builder_doc = _builder(site, track, out_dir, templates, counts_)
    author_path, author_doc = _author(site, track, out_dir, templates)
    clients_path, clients_doc = _clients(site, track, out_dir, templates)
    pages += [builder_path, author_path, clients_path]

    # docs stay in the order llms.txt lists them (plan 6.8)
    docs += [
        (f"{list_path}index.md", list_doc),
        (f"{builder_path}index.md", builder_doc),
        (f"{author_path}index.md", author_doc),
        (f"{install_path}index.md", install_doc),
        (f"{clients_path}index.md", clients_doc),
    ]
    docs += policy_docs

    _api(site, track, out_dir)
    authordata.write_author_json(site.data, out_dir)

    if len(pages) != counts_["total"] + 6:
        raise PageError(f"{track.slug}: expected {counts_['total'] + 6} pages")

    llms = f"## {track.title}\n\n"
    llms += f"- [{track.title} home](/{track.slug}/index.md): {track.summary}\n"
    llms += (
        f"- [Policies](/{track.slug}/policies/index.md): "
        "every policy shown on this site\n"
        f"- [Builder](/{track.slug}/builder/index.md): "
        "pick policies, get the command and file\n"
        f"- [Author](/{track.slug}/author/index.md): "
        "describe a safeguard, get a setup script\n"
        f"- [Install](/{track.slug}/install/index.md): "
        "the command and the selection file\n"
        f"- [Other clients](/{track.slug}/clients/index.md): "
        "the same policies for other coding agents\n"
    )
    llms += f"\n## {track.title}: policies\n\n"
    for policy in policies_sorted(site):
        llms += (
            f"- [{policy.name}](/{track.slug}/policies/{policy.id}/index.md): "
            f"{policy.word}, {policy.says}\n"
        )
    llms += f"\n## {track.title}: presets\n\n"
    for preset in site.presets:
        llms += (
            f"- [{preset.title}](/{track.slug}/builder/#preset={preset.id}): "
            f"{preset.summary}\n"
        )
    return SectionResult(pages=pages, llms=llms, docs=docs)
