"""The landing page (R-2): sections filled from home.yaml, the catalog and the engine's labels."""

from pathlib import Path
from typing import Any

from . import homedata, repodata
from .catalog import first_sentence
from .model import Policy, Site
from .pageparts import (
    COMMAND_FORM,
    PARTIALS,
    PageError,
    badge,
    chip,
    counts,
    data_fill,
    install_command,
    keyword_chip,
    slug,
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

HOME = "home"
MD = "md"
COUNTED = "coding"  # the home page's catalog numbers describe the coding catalog


DESC_LIMIT = 150


def _one_line(text: str) -> str:
    """The first sentence, cut at a word boundary under DESC_LIMIT characters."""
    line = first_sentence(text)
    if len(line) <= DESC_LIMIT:
        return line
    cut = line[:DESC_LIMIT].rsplit(" ", 1)[0]
    if cut.count("`") % 2:
        cut = cut[: cut.rindex("`")]
    return cut.rstrip(" ,;:-") + "…"


def _each(templates: Path, partial: str, rows: list[dict[str, Any]]) -> Safe:
    """One partial per row of token values, joined."""
    path = templates / PARTIALS / f"{partial}.html"
    return Safe("".join(render_file(path, **row) for row in rows))


def _sub(site: Site) -> dict[str, str]:
    """The numbers every section's data strings may use, all computed."""
    c = counts(site, COUNTED)
    return {
        "__CATALOG_REF_12__": site.catalog_ref[:12],
        "__COUNT__": str(c["total"]),
        "__TESTED__": f"{c['tested']:,}",
        "__PRESETS__": str(c["presets"]),
    }


def _policy(site: Site, policy_id: str) -> Policy:
    by_id = {p.id: p for p in site.policies}
    if policy_id not in by_id:
        raise PageError(f"home.yaml: {policy_id} is not a visible policy")
    return by_id[policy_id]


def _demo_input(land: dict[str, Any], case: Any) -> str:
    """The case's own input: its command, or the staged files the suite names."""
    if case.command:
        return case.command
    return "\n".join(
        f"{land['demo_staged']} {name}: {text.rstrip()}"
        for name, text in case.files.items()
    )


def _hero(site: Site, templates: Path, land: dict[str, Any], subs: dict) -> Safe:
    cases = []
    for case in site.demo:
        policy = _policy(site, case.policy)
        cases.append(
            {
                "ID": policy.id,
                "INPUT": _demo_input(land, case),
                "REFUSAL": f"{land['demo_refused']} {policy.id}: {policy.says}",
                "LINK": land["demo_policy_link"],
            }
        )
    return Safe(
        render_file(
            templates / HOME / "hero.html",
            EYEBROW=land["eyebrow"],
            STATS=data_fill(land["stats_line"], subs),
            HEADLINE_LEAD=land["headline_lead"],
            HEADLINE_ACCENT=land["headline_accent"],
            SUB=Prose(land["sub"]),
            PRIMARY_CTA=land["primary_cta"],
            SECONDARY_CTA=land["secondary_cta"],
            INSTALL=install_command(site),
            COPY_ARIA=land["install_aria"],
            COPY_LABEL=land["copy_label"],
            TICKS=_each(templates, "tick", [{"TEXT": text} for text in land["ticks"]]),
            DEMO_LABEL=land["demo_label"],
            DEMO_TITLE=land["demo_title"],
            DEMO_CASES=_each(templates, "demo-case", cases),
            DEMO_NOTE=data_fill(land["demo_note"], subs),
        )
    )


def _works(site: Site, templates: Path, land: dict[str, Any]) -> Safe:
    clients = site.data["builder_clients"]
    items = [
        {
            "HREF": f"/coding/builder/#client={client}",
            "NAME": clients["clients"][client]["name"],
            "HOW": clients["texts"][clients["clients"][client]["witness"]],
        }
        for client in clients["order"]
    ]
    return Safe(
        render_file(
            templates / HOME / "works.html",
            LABEL=land["works_label"],
            ITEMS=_each(templates, "works-item", items),
        )
    )


def _track_cards(site: Site, templates: Path, land: dict[str, Any]) -> Safe:
    """The sections block: one card per track in tracks.yaml, its copy from there."""
    agents = len(site.data["builder_clients"]["order"])
    cards = []
    for track in site.tracks:
        conf = land["track_cards"].get(track.id, {})
        has_catalog = track.id == COUNTED
        c = counts(site, track.id) if has_catalog else {}
        numbers = {
            "policies": c.get("total"),
            "presets": c.get("presets"),
            "agents": agents,
        }
        labels = dict(land["stat_labels"])
        if track.id in site.label_words and not has_catalog:
            numbers |= repodata.counts(site.policies, site.data["repos"]["tiers"])
            labels |= site.label_words[track.id]
        stats = "".join(
            render_file(
                templates / PARTIALS / "track-stat.html",
                LABEL=sentence_start(labels[key]),
                NUM=f"{numbers[key]:,}",
            )
            for key in conf.get("stats", [])
        )
        buttons = conf.get("buttons") or [
            {"label": conf.get("link", track.title), "href": f"/{track.slug}/"}
        ]
        cards.append(
            render_file(
                templates / PARTIALS / "track-card.html",
                STATUS=track.status.replace("_", "-"),
                ID=track.id,
                SLUG=track.slug,
                TITLE=track.title,
                BADGE=badge(site, templates, track.status),
                SUMMARY=Prose(track.summary),
                STATS=Safe(
                    render_file(
                        templates / PARTIALS / "track-stats.html", ITEMS=Safe(stats)
                    )
                    if stats
                    else ""
                ),
                NOTE=Safe(
                    render_file(
                        templates / PARTIALS / "track-note.html", TEXT=conf["note"]
                    )
                    if conf.get("note")
                    else ""
                ),
                ACTIONS=_each(
                    templates,
                    "track-button",
                    [
                        {
                            "CLASS": "button-primary"
                            if b.get("primary")
                            else "button-secondary",
                            "HREF": b["href"],
                            "LABEL": b["label"],
                        }
                        for b in buttons
                    ],
                ),
            )
        )
    return Safe(
        render_file(
            templates / PARTIALS / "sections-block.html",
            EYEBROW=land["sections_eyebrow"],
            HEADING=land["sections_heading"],
            INTRO=Prose(land["sections_intro"]),
            COLUMNS=str(min(len(cards), 3)),
            CARDS=Safe("".join(cards)),
        )
    )


def how_command(site: Site) -> str:
    """The home page's command form: the untested one, since --apply is only for tested agents."""
    return data_fill(site.data["builder_clients"]["commands"]["untested"], COMMAND_FORM)


def _how(site: Site, templates: Path, land: dict[str, Any]) -> Safe:
    command = how_command(site)
    steps = []
    for i, step in enumerate(land["how"], start=1):
        extra = ""
        if i == 2:
            extra = render_file(
                templates / PARTIALS / "how-code.html", CODE=command
            ) + render_file(
                templates / PARTIALS / "how-note.html", NOTE=land["how_apply_note"]
            )
        steps.append(
            {
                "NUM": str(i),
                "TITLE": step["title"],
                "BODY": Prose(step["body"]),
                "EXTRA": Safe(extra),
            }
        )
    return Safe(
        render_file(
            templates / HOME / "how.html",
            EYEBROW=land["how_eyebrow"],
            HEADING=land["how_heading"],
            STEPS=_each(templates, "how-step", steps),
        )
    )


def _surface_rows(site: Site, policy: Policy) -> list[dict[str, Any]]:
    """The policy's catalog label on each agent, with the agent's witness state; None when ungraded."""
    clients = site.data["builder_clients"]
    rows = []
    for client in clients["order"]:
        about = clients["clients"][client]
        label = policy.client_labels.get(client)
        rows.append(
            {
                "name": about["name"],
                "state": about["witness"],
                "state_word": clients["texts"][about["witness"]],
                "keyword": label and label["keyword"],
                "says": label["says"]
                if label
                else data_fill(
                    clients["texts"]["ungraded_says"], {"__NAME__": about["name"]}
                ),
            }
        )
    return rows


def _surface(site: Site, templates: Path, land: dict[str, Any], subs: dict) -> Safe:
    policy = _policy(site, land["surface_policy"])
    rows = [
        {
            "NAME": row["name"],
            "STATE": row["state"],
            "STATE_WORD": sentence_start(row["state_word"]),
            "CHIP": Safe("")
            if row["keyword"] is None
            else keyword_chip(site, templates, row["keyword"], COUNTED),
            "SAYS": row["says"],
        }
        for row in _surface_rows(site, policy)
    ]
    tests = data_fill(
        land["surface_tests"],
        {
            "__TESTED__": str(policy.eval_executed),
            "__TOTAL__": str(policy.eval_cases),
        },
    )
    return Safe(
        render_file(
            templates / HOME / "surface.html",
            EYEBROW=land["surface_eyebrow"],
            HEADING=land["surface_heading"],
            BODY=data_fill(land["surface_body"], {"__POLICY__": policy.id}),
            POLICY_LINK=Safe(
                render_file(templates / PARTIALS / "policy-link.html", ID=policy.id)
            ),
            TESTS=tests,
            ROWS=_each(templates, "surface-row", rows),
        )
    )


def _usecases(site: Site, templates: Path, land: dict[str, Any]) -> Safe:
    presets = {p.id: p for p in site.presets}
    tabs, panels = [], []
    for case in land["usecases"]:
        preset = presets.get(case["preset"])
        if preset is None:
            raise PageError(f"home.yaml usecases: {case['preset']} is not a preset")
        if len(case["policies"]) > 4:
            raise PageError(f"home.yaml usecases: {case['tab']} lists more than four")
        for pid in case["policies"]:
            if pid not in preset.members:
                raise PageError(f"home.yaml usecases: {pid} is not in {preset.id}")
        case_id = slug(case["tab"])
        policies = []
        for pid in case["policies"]:
            policy = _policy(site, pid)
            policies.append(
                {
                    "ID": pid,
                    "DESC": Prose(_one_line(policy.description)),
                    "CHIP": chip(site, templates, policy, COUNTED),
                }
            )
        tabs.append({"ID": case_id, "TAB": case["tab"]})
        panels.append(
            render_file(
                templates / PARTIALS / "usecase-panel.html",
                ID=case_id,
                TAB=case["tab"],
                HEADLINE=case["headline"],
                BODY=Prose(case["body"]),
                POINTS=_each(
                    templates, "plain-li", [{"TEXT": t} for t in case["points"]]
                ),
                PRESET=preset.id,
                PRESET_TITLE=preset.title,
                CTA=land["usecases_cta"],
                PANEL=data_fill(
                    land["usecases_panel"], {"__PRESET__": preset.title.upper()}
                ),
                POLICIES=_each(templates, "usecase-policy", policies),
            )
        )
    return Safe(
        render_file(
            templates / HOME / "usecases.html",
            EYEBROW=land["usecases_eyebrow"],
            HEADING=land["usecases_heading"],
            TABS_LABEL=land["usecases_label"],
            TABS=_each(templates, "usecase-tab", tabs),
            PANELS=Safe("".join(panels)),
        )
    )


def _honest(site: Site, templates: Path, land: dict[str, Any], subs: dict) -> Safe:
    words = site.label_words[COUNTED]
    label_counts = counts(site, COUNTED)["label"]
    segs = _each(
        templates,
        "dist-seg",
        [
            {"KEY": key, "NUM": str(label_counts[key]), "WORD": words[key]}
            for key in words
        ],
    )
    dist_label = "Label mix: " + ", ".join(
        f"{label_counts[key]} {words[key]}" for key in words
    )
    cards = _each(
        templates,
        "label-card",
        [
            {
                "CHIP": keyword_chip(site, templates, key, COUNTED),
                "WORD": sentence_start(words[key]),
                "MEANING": site.data["label_meanings"][words[key]],
            }
            for key in words
        ],
    )
    return Safe(
        render_file(
            templates / HOME / "honest.html",
            EYEBROW=land["honest_eyebrow"],
            HEADING=land["honest_heading"],
            BODY=land["honest_body"],
            LINK=data_fill(land["honest_link"], subs),
            DIST_LABEL=dist_label,
            DIST_SEGS=segs,
            NOTE=land["honest_note"],
            LABEL_CARDS=cards,
            FRICTION=land["honest_friction"],
            FRICTION_BODY=land["honest_friction_body"],
            FRICTION_LINK=land["honest_friction_link"],
        )
    )


def _example_values(land: dict[str, Any]) -> dict[str, float]:
    return {item["id"]: item["value"] for item in land["calc_inputs"]}


def _shift(site: Site, templates: Path, land: dict[str, Any]) -> Safe:
    values = _example_values(land)
    hours, money, days = homedata.savings(
        values["findings"],
        values["share"],
        values["minutes"],
        values["rate"],
        values["days"],
    )
    fields = "".join(
        render_file(
            templates
            / PARTIALS
            / ("calc-field-max.html" if "max" in item else "calc-field.html"),
            ID=item["id"],
            LABEL=item["label"],
            VALUE=f"{item['value']:g}",
            MIN=f"{item['min']:g}",
            STEP=f"{item['step']:g}",
            **({"MAX": f"{item['max']:g}"} if "max" in item else {}),
        )
        for item in land["calc_inputs"]
    )
    example = data_fill(
        land["calc_example_text"],
        {
            "__FINDINGS__": f"{values['findings']:g}",
            "__SHARE__": f"{values['share']:g}",
            "__MINUTES__": f"{values['minutes']:g}",
            "__RATE__": f"{values['rate']:g}",
            "__DAYS__": f"{values['days']:g}",
            "__HOURS__": homedata.fmt_hours(hours),
            "__MONEY__": homedata.fmt_money(money),
            "__SAVED_DAYS__": homedata.fmt_hours(days),
        },
    )
    return Safe(
        render_file(
            templates / HOME / "shift.html",
            EYEBROW=land["shift_eyebrow"],
            HEADING=land["shift_heading"],
            INTRO=Prose(land["shift_intro"]),
            TODAY_TITLE=land["shift_today_title"],
            TODAY_STEPS=_each(
                templates, "plain-li", [{"TEXT": t} for t in land["shift_today"]]
            ),
            TODAY_NOTE=land["shift_today_note"],
            WITH_TITLE=land["shift_with_title"],
            WITH_STEPS=_each(
                templates, "plain-li", [{"TEXT": t} for t in land["shift_with"]]
            ),
            WITH_NOTE=land["shift_with_note"],
            CALC_HEADING=land["calc_heading"],
            EXAMPLE_LABEL=land["calc_example_label"],
            FIELDS=Safe(fields),
            OUT_HOURS=land["calc_out_hours"],
            OUT_MONEY=land["calc_out_money"],
            OUT_DAYS=land["calc_out_days"],
            HOURS=homedata.fmt_hours(hours),
            MONEY=homedata.fmt_money(money),
            DAYS=homedata.fmt_hours(days),
            INVALID=land["calc_invalid"],
            FORMULA_HEADING=land["calc_formula_heading"],
            FORMULA=_each(
                templates, "plain-li", [{"TEXT": t} for t in land["calc_formula"]]
            ),
            EXAMPLE_TEXT=example,
        )
    )


def _incidents(site: Site, templates: Path) -> Safe:
    copy = site.data["incidents"]
    rows = []
    for row in site.incidents:
        links = " ".join(
            render_file(templates / PARTIALS / "policy-link.html", ID=pid)
            for pid in row.policies
        )
        rows.append(
            {"INCIDENT": row.incident, "FLAW": row.flaw, "POLICIES": Safe(links)}
        )
    return Safe(
        render_file(
            templates / HOME / "incidents.html",
            HEADING=copy["heading"],
            INTRO=Prose(copy["intro"]),
            COL_INCIDENT=copy["columns"]["incident"],
            COL_FLAW=copy["columns"]["flaw"],
            COL_POLICY=copy["columns"]["policy"],
            ROWS=_each(templates, "incident-row", rows),
            FRAMEWORK=copy["framework"],
            HONESTY=copy["honesty"],
        )
    )


def _trust(site: Site, templates: Path, land: dict[str, Any]) -> Safe:
    policy = _policy(site, land["trust_policy"])
    subs = {
        "__CATALOG_REF_12__": site.catalog_ref[:12],
        "__CATALOG_URL__": site.data["links"]["catalog_tree"] + site.catalog_ref,
        "__POLICY__": policy.id,
        "__EXECUTED__": str(policy.eval_executed),
        "__TOTAL__": str(policy.eval_cases),
    }
    rows = [
        {
            "TITLE": item["title"],
            "BODY": item["body"],
            "PROOF": data_fill(item["proof"], subs),
            "HREF": data_fill(item["href"], subs),
        }
        for item in land["trust"]
    ]
    return Safe(
        render_file(
            templates / HOME / "trust.html",
            EYEBROW=land["trust_eyebrow"],
            HEADING=land["trust_heading"],
            CARDS=_each(templates, "trust-card", rows),
        )
    )


def _faq(site: Site, templates: Path, land: dict[str, Any]) -> tuple[Safe, list[dict]]:
    by_id = {q["id"]: q for q in site.data["faq"]["questions"]}
    missing = [i for i in land["faq_ids"] if i not in by_id]
    if missing:
        raise PageError(f"home.yaml faq_ids: unknown questions {missing}")
    questions = [by_id[i] for i in land["faq_ids"]]
    rows = [{"Q": q["q"], "A": Prose(q["a"])} for q in questions]
    return (
        Safe(
            render_file(
                templates / HOME / "faq.html",
                EYEBROW=land["faq_eyebrow"],
                HEADING=land["faq_heading"],
                ITEMS=_each(templates, "faq-details", rows),
                LINK=land["faq_link"],
            )
        ),
        questions,
    )


VIDEO_PREFIX = "/video/"


def _video_file(templates: Path, entry: dict[str, Any], field: str) -> Path:
    """The static file a video field names; the build fails unless it is under /video/."""
    value = entry.get(field)
    where = f"home.yaml videos {entry.get('title')!r} {field}"
    if not isinstance(value, str) or not value.startswith(VIDEO_PREFIX):
        raise PageError(f"{where}: {value!r} is not a site path under {VIDEO_PREFIX}")
    rel = value.removeprefix("/")
    parts = rel.split("/")
    if "\\" in rel or any(part in ("", ".", "..") for part in parts):
        raise PageError(f"{where}: {value!r} is not a plain path under {VIDEO_PREFIX}")
    static = (templates.parent / "static").resolve()
    path = (static / rel).resolve()
    if not path.is_relative_to(static / VIDEO_PREFIX.strip("/")) or not path.is_file():
        raise PageError(f"{where}: {value!r} has no file in static/")
    return path


def _size(path: Path) -> str:
    """A file's size in decimal megabytes, read from the file at build time."""
    return f"{path.stat().st_size / 1_000_000:.1f} MB"


def _video_row(
    templates: Path, land: dict[str, Any], entry: dict[str, Any]
) -> dict[str, Any]:
    """The video-item tokens for one home.yaml entry, after checking its paths."""
    mp4 = _video_file(templates, entry, "src")
    _video_file(templates, entry, "poster")
    track = Safe("")
    if entry.get("captions") is not None:
        _video_file(templates, entry, "captions")
        track = Safe(
            render_file(
                templates / PARTIALS / "video-track.html", SRC=entry["captions"]
            )
        )
    for field in ("width", "height"):
        if not isinstance(entry.get(field), int) or isinstance(entry[field], bool):
            raise PageError(
                f"home.yaml videos {entry['title']!r}: {field} is not a number"
            )
    return {
        "TITLE": entry["title"],
        "SRC": entry["src"],
        "POSTER": entry["poster"],
        "WIDTH": str(entry["width"]),
        "HEIGHT": str(entry["height"]),
        "TRACK": track,
        "DOWNLOAD": data_fill(land["videos_download"], {"__SIZE__": _size(mp4)}),
        "DESCRIPTION": entry["description"],
        "DURATION": entry["duration"],
    }


def _videos(site: Site, templates: Path, land: dict[str, Any]) -> Safe:
    """The video block, directly below the hero, only when home.yaml lists videos."""
    videos = site.data["home"]["videos"]
    if not videos:
        return Safe("")
    return Safe(
        render_file(
            templates / HOME / "videos.html",
            HEADING=land["videos_heading"],
            ITEMS=_each(
                templates,
                "video-item",
                [_video_row(templates, land, v) for v in videos],
            ),
        )
    )


def _video_lines(site: Site, land: dict[str, Any]) -> str:
    """The twin's video section: title, description, duration and the MP4 link."""
    videos = site.data["home"]["videos"]
    if not videos:
        return ""
    lines = "".join(
        f"- [{md(v['title'])}]({v['src']}) ({v['duration']}, MP4): {md(v['description'])}\n"
        for v in videos
    )
    return f"## {land['videos_heading']}\n\n{lines}\n"


def _twin(
    site: Site, templates: Path, land: dict[str, Any], subs: dict, faq: list
) -> str:
    """The Markdown twin: the same facts as text, with the ask-first rule stated."""
    policy = _policy(site, land["surface_policy"])
    values = _example_values(land)
    hours, money, days = homedata.savings(
        values["findings"],
        values["share"],
        values["minutes"],
        values["rate"],
        values["days"],
    )
    incidents = site.data["incidents"]
    demo = "".join(
        f"- {c.policy}: {md_code(_demo_input(land, c))} → "
        f"{land['demo_refused']} {c.policy}: {md(_policy(site, c.policy).says)}\n"
        for c in site.demo
    )
    tracks = "".join(
        f"- [{t.title}](/{t.slug}/index.md) ({t.status.replace('_', ' ')}): {t.summary}\n"
        for t in site.tracks
    )
    surfaces = "".join(
        f"- {row['name']} ({row['state_word']}): "
        + (
            md(row["says"])
            if row["keyword"] is None
            else f"{site.label_words[COUNTED][row['keyword']]} — {md(row['says'])}"
        )
        + "\n"
        for row in _surface_rows(site, policy)
    )
    cases = "".join(
        f"- {c['tab']} (preset {c['preset']}): {c['headline']} "
        + ", ".join(c["policies"])
        + "\n"
        for c in land["usecases"]
    )
    rows = "".join(
        f"| {r.incident} | {r.flaw} | {', '.join(r.policies)} |\n"
        for r in site.incidents
    )
    return render_text_file(
        templates / MD / "index.md",
        SUB=land["sub"],
        VIDEOS=_video_lines(site, land),
        TICKS=" · ".join(land["ticks"]),
        STATS=data_fill(land["stats_line"], subs).lower(),
        INSTALL=install_command(site),
        DEMO_NOTE=data_fill(land["demo_note"], subs),
        DEMO_LINES=demo,
        TRACK_LINES=tracks,
        HOW_HEADING=land["how_heading"],
        HOW_LINES="".join(
            f"{i}. {s['title']} — {s['body']}\n" for i, s in enumerate(land["how"], 1)
        ),
        COMMAND=how_command(site),
        APPLY_NOTE=land["how_apply_note"],
        SURFACE_BODY=data_fill(land["surface_body"], {"__POLICY__": policy.id}),
        SURFACE_LINES=surfaces,
        USECASE_LINES=cases,
        HONEST_HEADING=land["honest_heading"],
        HONEST_BODY=land["honest_body"],
        FRICTION=f"{land['honest_friction']} {land['honest_friction_body']}",
        NOMODEL_HEADING=land["nomodel_heading"],
        NOMODEL_BODY=land["nomodel_body"],
        SHIFT_HEADING=land["shift_heading"],
        SHIFT_INTRO=land["shift_intro"],
        TODAY=" → ".join(land["shift_today"]),
        WITH=" → ".join(land["shift_with"]),
        FORMULA="".join(f"- {line}\n" for line in land["calc_formula"]),
        EXAMPLE_LABEL=land["calc_example_label"],
        EXAMPLE_TEXT=data_fill(
            land["calc_example_text"],
            {
                **{f"__{k.upper()}__": f"{v:g}" for k, v in values.items()},
                "__HOURS__": homedata.fmt_hours(hours),
                "__MONEY__": homedata.fmt_money(money),
                "__SAVED_DAYS__": homedata.fmt_hours(days),
            },
        ),
        LOCAL_BODY=land["local_body"],
        LOCAL_CAVEAT=land["local_caveat"],
        INCIDENT_HEADING=incidents["heading"],
        INCIDENT_INTRO=incidents["intro"],
        INCIDENT_ROWS=rows,
        INCIDENT_FRAMEWORK=incidents["framework"],
        INCIDENT_HONESTY=incidents["honesty"],
        PRESET_LINES="".join(
            f"- {p.title} ({len(p.members)} policies): {p.summary}\n"
            for p in site.presets
        ),
        FIT_LINES="".join(
            f"- {r['row']}: {sentence_start(land['fit_cols'][0])}: {r['a']} "
            f"{sentence_start(land['fit_cols'][1])}: {r['b']}\n"
            for r in land["fit_rows"]
        ),
        OPEN_BODY=land["open_body"],
        FAQ_LINES="".join(f"- {q['q']} {q['a']}\n" for q in faq),
        CTA=f"{land['cta_heading']} {land['cta_sub']}",
    )


def build(site: Site, out_dir: Path, templates: Path) -> tuple[str, str, str]:
    """The landing page (plan 6.7, redesign R-2) and its Markdown twin."""
    land = site.data["home"]["landing"]
    subs = _sub(site)
    links = site.data["links"]
    faq_html, faq = _faq(site, templates, land)
    presets = _each(
        templates,
        "home-preset-card",
        [
            {
                "ID": p.id,
                "TITLE": p.title,
                "COUNT": str(len(p.members)),
                "SUMMARY": Prose(p.summary),
            }
            for p in site.presets
        ],
    )
    page = site.data["pages"]["home"]
    content = render_file(
        templates / "index.html",
        HERO=_hero(site, templates, land, subs),
        WORKS=_works(site, templates, land),
        SECTIONS_BLOCK=_track_cards(site, templates, land)
        if len(site.tracks) >= 2
        else Safe(""),
        HOW=_how(site, templates, land),
        SURFACE=_surface(site, templates, land, subs),
        USECASES=_usecases(site, templates, land),
        HONEST=_honest(site, templates, land, subs),
        NOMODEL=Safe(
            render_file(
                templates / HOME / "nomodel.html",
                EYEBROW=land["nomodel_eyebrow"],
                HEADING=land["nomodel_heading"],
                BODY=land["nomodel_body"],
            )
        ),
        SHIFT=_shift(site, templates, land),
        LOCAL=Safe(
            render_file(
                templates / HOME / "local.html",
                EYEBROW=land["local_eyebrow"],
                HEADING=land["local_heading"],
                BODY=land["local_body"],
                CAVEAT=land["local_caveat"],
            )
        ),
        INCIDENTS=_incidents(site, templates),
        PRESETS=Safe(
            render_file(
                templates / HOME / "presets.html",
                EYEBROW=data_fill(land["presets_eyebrow"], subs),
                HEADING=land["presets_heading"],
                LINK=land["presets_link"],
                CARDS=presets,
            )
        ),
        FIT=Safe(
            render_file(
                templates / HOME / "fit.html",
                EYEBROW=land["fit_eyebrow"],
                HEADING=land["fit_heading"],
                COL_A=land["fit_cols"][0],
                COL_B=land["fit_cols"][1],
                ROWS=_each(
                    templates,
                    "fit-row",
                    [
                        {"ROW": r["row"], "A": r["a"], "B": r["b"]}
                        for r in land["fit_rows"]
                    ],
                ),
            )
        ),
        TRUST=_trust(site, templates, land),
        OPEN=Safe(
            render_file(
                templates / HOME / "open.html",
                EYEBROW=land["open_eyebrow"],
                HEADING=land["open_heading"],
                BODY=land["open_body"],
                GITHUB=land["open_github"],
                GITHUB_URL=links["engine_repo"],
                CONTRIBUTE=land["open_contribute"],
                CONTRIBUTE_URL=links["catalog_contributing"],
            )
        ),
        VIDEOS=_videos(site, templates, land),
        FAQ=faq_html,
        CTA=Safe(
            render_file(
                templates / HOME / "cta.html",
                HEADING=land["cta_heading"],
                SUB=land["cta_sub"],
                PRIMARY=land["primary_cta"],
                GITHUB=land["cta_github"],
                GITHUB_URL=links["engine_repo"],
            )
        ),
    )
    write_page(
        site,
        out_dir,
        templates,
        path="/",
        title=page["title"],
        description=page["description"],
        content=Safe(content),
        jsonld_data={
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": site.data["wordmark"],
            "url": site.data["site_url"] + "/",
        },
        scripts=("common.js", "home.js", "cost.js"),
    )
    twin = _twin(site, templates, land, subs, faq)
    write_md(out_dir, "/", twin)
    return "/", "/index.md", twin
