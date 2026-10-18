"""The Coding agents section: its pages, Markdown twins and /api/coding/ files."""

import json
from pathlib import Path
from typing import Any

from . import authordata, clientdata, clientpage, engine, report, routes
from .catalog import first_sentence, lead_sentences
from .model import Policy, SectionResult, Site, Track
from .pageparts import (
    PARTIALS,
    PageError,
    badge,
    chip,
    counts,
    data_fill,
    install_command,
    keyword_chip,
    label_chips,
    policies_sorted,
    render_steps,
    status_badge,
    write_md,
    write_page,
)
from .render import (
    Prose,
    Safe,
    md,
    md_code,
    render_file,
    render_text_file,
    sentence_start,
)
from .sitedata import site_dict

MD = "md"
# A policy page's meta description runs on past a short first sentence to this length.
META_MIN = 50


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
                LABEL=home["glance_policies"],
            )
        ]
        + [
            render_file(
                templates / PARTIALS / "home-stat.html",
                EXTRA=" stat-block" if key == "block" else "",
                NUM=str(counts_["label"][key]),
                LABEL=f"{site.data['glyphs'][key]} {sentence_start(site.label_words[track.id][key])}",
            )
            for key in site.label_words[track.id]
        ]
        + [
            render_file(
                templates / PARTIALS / "home-stat.html",
                EXTRA="",
                NUM=str(counts_["presets"]),
                LABEL=home["glance_presets"],
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
    clients = site.data["builder_clients"]
    client_cards = "".join(
        render_file(
            templates / PARTIALS / "agent-card.html",
            URL=f"/coding/builder/#client={client}",
            NAME=about["name"],
            REPO=clients["texts"][about["witness"]],
            HOW=about["build_link"],
        )
        for client in clients["order"]
        if (about := clients["clients"][client])
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
                COMPUTED_NOTE=f"{texts['computed_note']} {grades_note(site)}",
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


def engine_client_name(site: Site) -> str:
    """The agent whose grades the build-time labels and counts show."""
    return site.data["builder_clients"]["clients"][clientdata.ENGINE_CLIENT]["name"]


def grades_note(site: Site) -> str:
    """The sentence naming the agent behind the labels and counts."""
    return data_fill(
        site.data["texts"]["grades_agent_note"],
        {"__AGENT__": engine_client_name(site)},
    )


def _where_text(site: Site, policy: Policy) -> str:
    """'Shell command · file write' — the policy's where tags as one line."""
    return sentence_start(
        " · ".join(site.data["where_names"][tag] for tag in policy.where)
    )


def _when_text(site: Site, policy: Policy) -> str:
    """'Before the command runs' — when the policy fires, from its where tags."""
    return sentence_start(
        " · ".join(site.data["when_names"][tag] for tag in policy.where)
    )


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
            WORD=sentence_start(words[key]),
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
                STATUS=status_badge(site, templates, policy),
                DESC=Prose(sentence_start(first_sentence(policy.description))),
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
            WORD=sentence_start(site.data["where_names"][tag]),
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
    hidden = site.data["not_shown"]
    if hidden:
        intro += " " + data_fill(
            texts["not_shown"],
            {
                "__TOTAL__": str(counts_["total"] + len(hidden)),
                "__HIDDEN_COUNT__": str(len(hidden)),
                "__HIDDEN_VERB__": "is" if len(hidden) == 1 else "are",
                "__HIDDEN_IDS__": ", ".join(hidden),
            },
        )
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
                COMPUTED_NOTE=f"{texts['computed_note']} {grades_note(site)}",
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
        INTRO=Prose(f"{intro} {grades_note(site)}"),
        ROWS="".join(
            f"- [{md(policy.name)}](/{track.slug}/policies/{policy.id}/index.md) "
            f"({md_code(policy.id)}, v{md(policy.version)}): {policy.word} — "
            f"{md(policy.says)}. {md(sentence_start(first_sentence(policy.description)))}\n"
            for policy in policies_sorted(site)
        ),
    )
    write_md(out_dir, path, twin)
    return path, twin


def _agent_labels(site: Site, policy: Policy) -> list[dict[str, Any]]:
    """The policy's label on each agent in picker order; `word` is empty where it is not graded."""
    clients = site.data["builder_clients"]
    rows = []
    for client in clients["order"]:
        about = clients["clients"][client]
        label = about["labels"][policy.id]
        graded = label["keyword"] != clients["ungraded"]
        rows.append(
            {
                "client": client,
                "name": about["name"],
                "state": about["witness"],
                "state_word": clients["texts"][about["witness"]],
                "build": about["build_link"],
                "keyword": label["keyword"] if graded else None,
                "word": site.label_words["coding"][label["keyword"]] if graded else "",
                "says": label["says"].rstrip("."),
            }
        )
    return rows


def _agent_rows(site: Site, templates: Path, policy: Policy) -> Safe:
    """The policy page's "on each agent" list: grade, witness state and a builder link per agent."""
    return Safe(
        "".join(
            render_file(
                templates / PARTIALS / "agent-label-row.html",
                NAME=row["name"],
                STATE=row["state"],
                STATE_WORD=sentence_start(row["state_word"]),
                CHIP=Safe("")
                if row["keyword"] is None
                else keyword_chip(site, templates, row["keyword"], "coding"),
                SAYS=sentence_start(row["says"]),
                CLIENT=row["client"],
                ID=policy.id,
                BUILD=site.data["builder_clients"]["texts"]["build_short"],
                BUILD_LABEL=row["build"],
            )
            for row in _agent_labels(site, policy)
        )
    )


def _policy_report(policy: Policy, track: Track) -> str:
    """The /report/ link for one policy: its id and version, and its page."""
    return report.report_link(
        policy=policy.id,
        version=policy.version,
        page=f"/{track.slug}/policies/{policy.id}/",
    )


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
                f"- {e.word}: {md(e.prompt)}"
                + (f" — {md_code(e.command)}" if e.command else "")
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
                STATUS=status_badge(site, templates, policy),
                PRESET_CHIP=Safe(preset_chip),
                SAYS=Prose(sentence_start(policy.says.rstrip(".") + ".")),
                TIER=policy.tier,
                TIER_WORD=sentence_start(site.label_words["repos"][policy.tier]),
                ACTS_ON=_where_text(site, policy),
                WHEN=_when_text(site, policy),
                LABEL_NOTE=Prose(texts["label_box_note"]),
                PLUGIN_NOTE=Safe(plugin_note),
                BY_AGENT_HEADING=texts["by_agent_heading"],
                BY_AGENT_INTRO=texts["by_agent_intro"],
                AGENT_ROWS=_agent_rows(site, templates, policy),
                DESCRIPTION=Prose(sentence_start(policy.description)),
                MISSES=Prose(sentence_start(policy.misses or texts["misses_empty"])),
                EXAMPLES_SECTION=Safe(examples),
                LATEST_VERSION=policy.latest.version,
                LATEST_DATE=policy.latest.date,
                LATEST_CHANGE=Prose(sentence_start(policy.latest.change)),
                EVAL_EXECUTED=str(policy.eval_executed),
                EVAL_CASES=str(policy.eval_cases),
                SHA256=policy.sha256,
                CATALOG_COMMIT_URL=site.data["links"]["catalog_commit"]
                + site.catalog_ref,
                CATALOG_REF_12=site.catalog_ref[:12],
                SOURCE_URL=policy.source_url,
                PATH=policy.path,
                ALSO_IN=Safe(also_in),
                REPORT_HREF=_policy_report(policy, track),
                REPORT_TEXT=report.link_text(site, "policy"),
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
            description=lead_sentences(policy.description, META_MIN),
            content=content,
            jsonld_data={
                "@context": "https://schema.org",
                "@type": "SoftwareSourceCode",
                "name": policy.name,
                "version": policy.version,
                "description": lead_sentences(policy.description, META_MIN),
                "codeRepository": policy.source_url,
                "license": "Apache-2.0",
                "programmingLanguage": "Python",
            },
            nav=track.id,
            section=(track, "policies"),
            alt_json=alt,
            scripts=("common.js", "policy.js"),
        )
        twin = render_text_file(
            templates / MD / track.slug / "policy.md",
            ID=policy.id,
            TRACK=policy.track,
            NAME=md(policy.name),
            VERSION=md(policy.version),
            LABEL=policy.word,
            WORD=sentence_start(policy.word),
            TIER_WORD=site.label_words["repos"][policy.tier],
            TIER_MEANING=site.data["label_meanings"][
                site.label_words["repos"][policy.tier]
            ],
            KEYWORD=policy.keyword,
            WHERE=" ".join(policy.where) or "none",
            SHA256=policy.sha256,
            SOURCE_URL=policy.source_url,
            CATALOG_REF=site.catalog_ref,
            SAYS=md(policy.says.rstrip(".") + "."),
            LABEL_NOTE=texts["label_box_note"],
            STATUS_MD=(
                f"Status: {policy.status}."
                if policy.status in texts["status_badges"]
                else ""
            ),
            BY_AGENT_HEADING=texts["by_agent_heading"],
            AGENT_LINES="".join(
                f"- {row['name']} ({row['state_word']}): "
                + (f"{sentence_start(row['word'])} — " if row["word"] else "")
                + f"{md(sentence_start(row['says']))}. Builder: /coding/builder/#client={row['client']}&p={policy.id}\n"
                for row in _agent_labels(site, policy)
            ),
            PLUGIN_NOTE=(" " + texts["plugin_repo_note"] if plugin_note else ""),
            DESCRIPTION=md(sentence_start(policy.description)),
            MISSES=md(sentence_start(policy.misses))
            if policy.misses
            else texts["misses_empty"],
            EXAMPLES_MD=examples_md,
            LATEST_VERSION=md(policy.latest.version),
            LATEST_DATE=md(policy.latest.date),
            LATEST_CHANGE=md(sentence_start(policy.latest.change)),
            EVAL_EXECUTED=str(policy.eval_executed),
            EVAL_CASES=str(policy.eval_cases),
            CATALOG_COMMIT_URL=site.data["links"]["catalog_commit"] + site.catalog_ref,
            PATH=policy.path,
            REPORT_URL=site.data["site_url"] + _policy_report(policy, track),
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
            STATUS=status_badge(site, templates, p),
            SAYS=Prose(sentence_start(p.says)),
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
            NOTE=Safe(""),
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
            NOTE=Safe(
                render_file(
                    templates / PARTIALS / "builder-group-note.html",
                    NOTE=texts["builder_no_group"],
                )
            ),
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
                ROUTES_LINE=Safe(
                    routes.builder_line(
                        site.data["agent_routes"], templates / track.slug
                    )
                ),
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
                GRADES_AGENT=data_fill(
                    site.data["builder_texts"]["grades_for"],
                    {"{name}": engine_client_name(site)},
                ),
                GROUP_SECTIONS=Safe(groups),
                EMPTY=Prose(texts["builder_empty"]),
                NEED_ONE=Prose(texts["builder_need_one"]),
                UNTESTED=Safe(
                    clientpage.untested_lines(clients, templates / track.slug)
                ),
                EVIDENCE=Safe(
                    clientpage.evidence_lines(clients, templates / track.slug)
                ),
                CLIENT_STEPS=Safe(clientpage.steps(clients, templates / track.slug)),
                HINT=data_fill(texts["builder_outputs_hint"], subs),
                AUTHOR_LINK=Prose(site.data["builder_texts"]["author_link"]),
                REPORT_HREF=report.report_link(page=f"/{track.slug}/builder/"),
                REPORT_TEXT=report.link_text(site, "builder"),
                DOWNLOAD_NAME=site.data["builder_texts"]["download_name"],
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
        DEFAULT_NAME=clients["clients"][clients["default"]]["name"],
        AGENT_LINES=clientpage.markdown(clients),
        ROUTES_LINE=_routes_line_md(site.data["agent_routes"]),
    )
    write_md(out_dir, path, twin)
    return path, twin


def _routes_line_md(block: dict[str, Any]) -> str:
    """The builder twin's pointer to the install page's "Every agent" section."""
    texts = block["texts"]
    return f"{texts['builder_line']} [{texts['builder_link']}](/coding/install/#every-agent).\n\n"


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
                UNDO_LABEL=texts["undo_label"],
                ADVANCED_HEADING=texts["advanced_heading"],
                REPORT_HREF=report.report_link(page=path),
                REPORT_TEXT=report.link_text(site, "author"),
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


def _step_items(templates: Path, steps: list[dict[str, str]]) -> Safe:
    """Apply or remove steps as the builder shows them: numbered commands, unnumbered notes."""
    return Safe(clientpage.step_blocks(templates, steps))


def _remove_items(templates: Path, about: dict[str, Any]) -> Safe:
    """An agent's remove steps, or the "not verified" line with its evidence link."""
    unverified = about["remove_unverified"]
    if unverified is None:
        return _step_items(templates, about["remove"])
    return Safe(
        render_file(
            templates / "remove-unverified.html",
            TEXT=unverified["text"],
            URL=unverified["url"],
            LINK=unverified["link"],
        )
    )


def _client_command(clients: dict[str, Any], client: str) -> str:
    """The install command form for one agent, with "…" for the selection code."""
    state = clients["clients"][client]["witness"]
    return data_fill(
        clients["commands"][state], {"__CODE__": "…", "__CLIENT__": client}
    )


def _install(
    site: Site, track: Track, out_dir: Path, templates: Path
) -> tuple[str, str]:
    """Install page: engine install, the command per agent with its steps, update, remove, file format."""
    data = site.data
    inst = data["install"]
    clients = data["builder_clients"]
    install_cmd = install_command(site)
    field_subs = {
        "__SCHEMA__": str(engine.SCHEMA2),
        "__CLIENTS__": ", ".join(clients["order"]),
        "__BUNDLE_VERSION__": clients["bundle_version"],
    }
    fields = [
        {"field": row["field"], "meaning": data_fill(row["meaning"], field_subs)}
        for row in inst["file_fields"]
    ]
    field_rows = Safe(
        "".join(
            render_file(
                templates / PARTIALS / "field-row.html",
                FIELD=row["field"],
                MEANING=row["meaning"],
            )
            for row in fields
        )
    )
    agents = "".join(
        render_file(
            templates / track.slug / "install-agent.html",
            ID=client,
            NAME=about["name"],
            STATE=about["witness"],
            STATE_WORD=sentence_start(clients["texts"][about["witness"]]),
            EVIDENCE=Safe(
                clientpage.evidence_line(clients, templates / track.slug, client)
            ),
            COMMAND_LABEL=inst["agent_command"],
            COMMAND=_client_command(clients, client),
            STEPS_HEADING=about["steps_heading"],
            STEPS=_step_items(templates / track.slug, about["steps"]),
            REMOVE_LABEL=inst["agent_remove"],
            REMOVE=_remove_items(templates / track.slug, about),
            CLAUDE_PLUGIN=Safe(
                clientpage.claude_plugin(clients, templates / track.slug, client)
            ),
            REPORT_HREF=report.report_link(
                agent=client, page=f"/{track.slug}/install/"
            ),
            REPORT_TEXT=report.link_text(site, "install", name=about["name"]),
        )
        for client in clients["order"]
        if (about := clients["clients"][client])
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
                AGENTS_HEADING=inst["agents_heading"],
                AGENTS=Safe(agents),
                ROUTES=Safe(
                    routes.section(data["agent_routes"], templates / track.slug)
                ),
                UPDATE_HEADING=inst["update_heading"],
                UPDATE_BODY=Prose(inst["update_body"]),
                REMOVE_HEADING=inst["remove_heading"],
                REMOVE_BODY=Prose(inst["remove_body"]),
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
        AGENTS_HEADING=inst["agents_heading"],
        AGENT_LINES=clientpage.markdown(clients),
        ROUTES=routes.markdown(data["agent_routes"]),
        UPDATE_HEADING=inst["update_heading"],
        UPDATE_BODY=inst["update_body"],
        REMOVE_HEADING=inst["remove_heading"],
        REMOVE_BODY=inst["remove_body"],
        FILE_HEADING=inst["file_heading"],
        FILE_BODY=inst["file_body"],
        FIELD_LINES="".join(
            f"- `{row['field']}`: {row['meaning']}\n" for row in fields
        ),
    )
    write_md(out_dir, path, twin)
    return path, twin


def _client_notes(site: Site, clients: dict[str, Any], client: str) -> str:
    """One agent's card text: its witness state, then the engine's warnings for that agent."""
    about = clients["clients"][client]
    lead = data_fill(
        clients["texts"][f"card_{about['witness']}"], {"__NAME__": about["name"]}
    )
    notes = [
        rule["says"]
        for rule in site.warning_rules
        if rule["kind"] == "client" and client in rule["clients"]
    ]
    return " ".join([lead, *notes])


def _repo_line(templates: Path, texts: dict[str, str], repo: str | None) -> str:
    """An agent card's plugin-repository line, or "" for an agent without one."""
    if repo is None:
        return ""
    return render_file(
        templates / PARTIALS / "client-repo.html",
        REPO_LINE=texts["repo_line"],
        REPO=repo,
        REPO_LABEL=repo.rsplit("/", 1)[-1],
    )


def _clients(
    site: Site, track: Track, out_dir: Path, templates: Path
) -> tuple[str, str]:
    """The agents page: every agent the builder builds for, its state, and its plugin repo."""
    data = site.data
    clients = data["builder_clients"]
    page = data["pages"]["clients"]
    names = [clients["clients"][c]["name"] for c in clients["order"]]
    description = data_fill(
        page["description"], {"__NAMES__": ", ".join(names[:-1]) + " and " + names[-1]}
    )
    texts = clients["texts"]
    cards = "".join(
        render_file(
            templates / PARTIALS / "client-card.html",
            ID=client,
            NAME=about["name"],
            STATE=about["witness"],
            STATE_WORD=sentence_start(texts[about["witness"]]),
            NOTE=Prose(_client_notes(site, clients, client)),
            BUILD=about["build_link"],
            REPO=Safe(_repo_line(templates, texts, about["plugin_repo"])),
        )
        for client in clients["order"]
        if (about := clients["clients"][client])
    )
    intro = f"{description} {texts['page_intro']}"
    path = f"/{track.slug}/clients/"
    write_page(
        site,
        out_dir,
        templates,
        path=path,
        title=page["title"],
        description=description,
        content=Safe(
            render_file(
                templates / track.slug / "clients.html",
                INTRO=Prose(intro),
                CLIENT_CARDS=Safe(cards),
            )
        ),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page["title"],
            "description": description,
        },
        nav=track.id,
        section=(track, "clients"),
    )
    twin = render_text_file(
        templates / MD / track.slug / "clients.md",
        INTRO=intro,
        CLIENT_LINES="".join(
            f"- {about['name']} (`{client}`, {texts[about['witness']]}): "
            f"{_client_notes(site, clients, client)} "
            f"Builder: /coding/builder/#client={client}."
            + (
                f" {texts['repo_line']} {about['plugin_repo']}."
                if about["plugin_repo"]
                else ""
            )
            + "\n"
            for client in clients["order"]
            if (about := clients["clients"][client])
        ),
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
        f"- [Agents](/{track.slug}/clients/index.md): "
        "every agent the builder builds for, and its plugin repository\n"
    )
    llms += f"\n## {track.title}: policies\n\n"
    for policy in policies_sorted(site):
        llms += (
            f"- [{md(policy.name)}](/{track.slug}/policies/{policy.id}/index.md): "
            f"{policy.word}, {md(policy.says)}\n"
        )
    llms += f"\n## {track.title}: presets\n\n"
    for preset in site.presets:
        llms += (
            f"- [{preset.title}](/{track.slug}/builder/#preset={preset.id}): "
            f"{preset.summary}\n"
        )
    return SectionResult(pages=pages, llms=llms, docs=docs)
