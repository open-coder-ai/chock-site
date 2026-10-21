"""The Architecture docs section: data/architecture/<id>.json drawn as inline SVG, cards and a Markdown twin.

Run `python -m sitegen.architecture --check --clones DIR` to fail (exit 1) when a cited
`repo/path` is missing at the commit its diagram pins.
"""

import argparse
import itertools
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .pageparts import PageError, data_fill
from .render import Prose, Safe, md_code, md_prose, render_file
from .render import md as md_escape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FOLDER = "architecture"
TEXTS = "texts.yaml"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DIAGRAM_KEYS = {
    "id",
    "order",
    "title",
    "summary",
    "intro",
    "pins",
    "canvas",
    "nodes",
    "edges",
}
OPTIONAL_KEYS = {"boundaries", "path"}
NODE_KEYS = {"id", "label", "kind", "x", "y", "source", "card"}
NODE_OPTIONAL = {"w", "h", "facts", "code"}
EDGE_KEYS = {"from", "to", "label"}
EDGE_OPTIONAL = {"via", "label_at", "code"}
FACTS = ("tiers",)

Point = tuple[float, float]
Section = Callable[[Any, Any, str, str, str], None]


@dataclass
class Diagram:
    """One diagram as its JSON file holds it, checked."""

    id: str
    order: int
    title: str
    summary: str
    intro: str
    pins: dict[str, str]
    raw: dict[str, Any]

    @property
    def nodes(self) -> list[dict[str, Any]]:
        """The boxes, in file order."""
        return self.raw["nodes"]

    @property
    def edges(self) -> list[dict[str, Any]]:
        """The arrows, in file order."""
        return self.raw["edges"]

    @property
    def path(self) -> list[str]:
        """The main flow's node ids in order, or an empty list."""
        return self.raw.get("path", [])


def load_texts(data_dir: Path = DATA) -> dict[str, Any]:
    """data/architecture/texts.yaml."""
    return yaml.safe_load((data_dir / FOLDER / TEXTS).read_text(encoding="utf-8"))


def split_source(source: str) -> tuple[str, str]:
    """`repo/path/in/repo` as (repo, path)."""
    repo, _, path = source.partition("/")
    return repo, path


def _refuse(name: str, msg: str) -> None:
    """Raise the build error for one diagram file."""
    raise PageError(f"data/{FOLDER}/{name}: {msg}")


def _keys(name: str, where: str, item: dict[str, Any], need: set, may: set) -> None:
    """Refuse an item missing a required key or carrying an unknown one."""
    missing = need - set(item)
    extra = set(item) - need - may
    if missing or extra:
        _refuse(name, f"{where}: missing {sorted(missing)}, unknown {sorted(extra)}")


def _check_node(name: str, node: dict[str, Any], doc: dict, texts: dict) -> None:
    """A node's kind, source, size and that its words fit its box."""
    _keys(name, f"node {node.get('id')!r}", node, NODE_KEYS, NODE_OPTIONAL)
    if not ID_RE.match(node["id"]):
        _refuse(name, f"node id {node['id']!r} must be lowercase words and hyphens")
    if node["kind"] not in texts["kinds"]:
        _refuse(name, f"node {node['id']!r}: unknown kind {node['kind']!r}")
    _check_label(name, f"node {node['id']!r}", node)
    if node.get("facts") not in (None, *FACTS):
        _refuse(name, f"node {node['id']!r}: unknown facts {node['facts']!r}")
    repo, path = split_source(node["source"])
    if repo not in doc["pins"] or not path or path.startswith("/") or ".." in path:
        _refuse(
            name,
            f"node {node['id']!r}: source {node['source']!r} needs a pinned repo/path",
        )
    w, h = _size(node, texts)
    canvas = doc["canvas"]
    if (
        node["x"] < 0
        or node["y"] < 0
        or node["x"] + w > canvas["width"]
        or node["y"] + h > canvas["height"]
    ):
        _refuse(name, f"node {node['id']!r} lies outside the canvas")
    room = w - 2 * texts["node_pad_px"]
    glyph = texts["code_char_px"] if node.get("code") else texts["label_char_px"]
    if len(node["label"]) * glyph > room or len(repo) * texts["repo_char_px"] > room:
        _refuse(
            name, f"node {node['id']!r}: label or repo name too long for a {w}px box"
        )


def _check_label(name: str, where: str, item: dict[str, Any]) -> None:
    """Refuse a label holding a backtick, or a `code` flag that is not true or false."""
    if "`" in item["label"]:
        _refuse(name, f'{where}: a label holds no backtick; set "code": true instead')
    if item.get("code", False) not in (True, False):
        _refuse(name, f"{where}: code must be true or false")


def _check(name: str, doc: dict[str, Any], texts: dict[str, Any]) -> None:
    """Refuse a diagram file that is incomplete, inconsistent or cites an unpinned repo."""
    _keys(name, "diagram", doc, DIAGRAM_KEYS, OPTIONAL_KEYS)
    if f"{doc['id']}.json" != name or not ID_RE.match(doc["id"]):
        _refuse(name, f"id {doc['id']!r} must match the file name")
    for repo, sha in doc["pins"].items():
        if not SHA_RE.match(sha):
            _refuse(name, f"pin for {repo!r} is not a 40-hex commit")
    ids = [n["id"] for n in doc["nodes"]]
    if len(set(ids)) != len(ids):
        _refuse(name, "node ids repeat")
    for node in doc["nodes"]:
        _check_node(name, node, doc, texts)
    used = {split_source(n["source"])[0] for n in doc["nodes"]}
    if used != set(doc["pins"]):
        _refuse(name, f"pins no node cites: {sorted(set(doc['pins']) - used)}")
    pairs = set()
    for edge in doc["edges"]:
        _keys(
            name,
            f"edge {edge.get('from')}->{edge.get('to')}",
            edge,
            EDGE_KEYS,
            EDGE_OPTIONAL,
        )
        _check_label(name, f"edge {edge['from']}->{edge['to']}", edge)
        if (
            edge["from"] not in ids
            or edge["to"] not in ids
            or edge["from"] == edge["to"]
        ):
            _refuse(name, f"edge {edge['from']}->{edge['to']} names an unknown node")
        pairs.add((edge["from"], edge["to"]))
    path = doc.get("path", [])
    for a, b in itertools.pairwise(path):
        if (a, b) not in pairs:
            _refuse(name, f"path step {a}->{b} has no edge")
    for box in doc.get("boundaries", []):
        _keys(name, "boundary", box, {"label", "x", "y", "w", "h"}, set())


def load(data_dir: Path = DATA, texts: dict[str, Any] | None = None) -> list[Diagram]:
    """Every data/architecture/*.json, checked, in `order`."""
    texts = texts or load_texts(data_dir)
    out = []
    for file in sorted((data_dir / FOLDER).glob("*.json")):
        doc = json.loads(file.read_text(encoding="utf-8"))
        _check(file.name, doc, texts)
        out.append(
            Diagram(
                id=doc["id"],
                order=doc["order"],
                title=doc["title"],
                summary=doc["summary"],
                intro=doc["intro"],
                pins=doc["pins"],
                raw=doc,
            )
        )
    orders = [d.order for d in out]
    if len(set(orders)) != len(orders):
        raise PageError(f"data/{FOLDER}: two diagrams share an order")
    return sorted(out, key=lambda d: d.order)


# --- geometry -------------------------------------------------------------------


def _size(node: dict[str, Any], texts: dict[str, Any]) -> tuple[int, int]:
    """A node's width and height, or the defaults."""
    return node.get("w", texts["node"]["w"]), node.get("h", texts["node"]["h"])


def _num(value: float) -> str:
    """A coordinate for an SVG attribute: one decimal at most."""
    text = f"{round(value, 1):.1f}"
    return text.removesuffix(".0")


def _clip(box: tuple[float, float, float, float], toward: Point) -> Point:
    """Where the line from the box's centre toward a point leaves the box."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    dx, dy = toward[0] - cx, toward[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy
    scale = min(
        (w / 2) / abs(dx) if dx else float("inf"),
        (h / 2) / abs(dy) if dy else float("inf"),
    )
    return cx + dx * scale, cy + dy * scale


def edge_points(
    diagram: Diagram, edge: dict[str, Any], texts: dict[str, Any]
) -> list[Point]:
    """An edge's polyline: from the first box's border, through any via points, to the second's."""
    boxes = {}
    for node in diagram.nodes:
        w, h = _size(node, texts)
        boxes[node["id"]] = (node["x"], node["y"], w, h)
    a, b = boxes[edge["from"]], boxes[edge["to"]]
    via = [tuple(p) for p in edge.get("via", [])]
    centre_b = (b[0] + b[2] / 2, b[1] + b[3] / 2)
    centre_a = (a[0] + a[2] / 2, a[1] + a[3] / 2)
    start = _clip(a, via[0] if via else centre_b)
    end = _clip(b, via[-1] if via else centre_a)
    return [start, *via, end]


def _label_at(edge: dict[str, Any], points: list[Point]) -> Point:
    """The edge label's anchor: given, or just above the middle of the longest segment."""
    if "label_at" in edge:
        return tuple(edge["label_at"])
    segs = list(itertools.pairwise(points))
    p, q = max(segs, key=lambda s: (s[1][0] - s[0][0]) ** 2 + (s[1][1] - s[0][1]) ** 2)
    return (p[0] + q[0]) / 2, (p[1] + q[1]) / 2 - 6


# --- labels ---------------------------------------------------------------------


def label_prose(item: dict[str, Any]) -> str:
    """A node or edge label for HTML: a Prose code span when it is a command, else plain text."""
    return Prose(f"`{item['label']}`") if item.get("code") else item["label"]


def label_md(item: dict[str, Any]) -> str:
    """A node or edge label for Markdown: a code span when it is a command, else escaped."""
    return md_code(item["label"]) if item.get("code") else md_escape(item["label"])


def text_class(base: str, item: dict[str, Any]) -> str:
    """An SVG <text> class: `mono` added for a command, so it reads as code."""
    return f"{base} mono" if item.get("code") else base


# --- HTML -----------------------------------------------------------------------


def card_id(diagram: Diagram, node: dict[str, Any]) -> str:
    """The id of a node's card on the page: the no-JS target of the box's link."""
    return f"arch-{diagram.id}-{node['id']}"


def source_url(texts: dict[str, Any], diagram: Diagram, source: str) -> str:
    """A cited file on GitHub at its diagram's pinned commit."""
    repo, path = split_source(source)
    url = data_fill(texts["repo_url"], {"__REPO__": repo})
    return data_fill(
        texts["blob_url"],
        {"__URL__": url, "__SHA__": diagram.pins[repo], "__PATH__": path},
    )


def commit_url(texts: dict[str, Any], repo: str, sha: str) -> str:
    """A pinned commit on GitHub."""
    url = data_fill(texts["repo_url"], {"__REPO__": repo})
    return data_fill(texts["commit_url"], {"__URL__": url, "__SHA__": sha})


def tier_facts(texts: dict[str, Any], agents: list[dict[str, Any]]) -> list[str]:
    """One line per fail mode in agentseam's tier table: its agents and their tiers."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for agent in agents:
        groups.setdefault(agent["fail_mode"], []).append(agent)
    rows = []
    for mode, members in groups.items():
        if mode not in texts["fail_modes"]:
            raise PageError(f"data/{FOLDER}/{TEXTS}: no wording for fail mode {mode!r}")
        names = ", ".join(
            data_fill(
                texts["tiers_agent"], {"__NAME__": a["name"], "__TIER__": a["tier"]}
            )
            for a in members
        )
        rows.append(
            data_fill(
                texts["tiers_row"],
                {
                    "__MODE__": texts["fail_modes"][mode],
                    "__COUNT__": str(len(members)),
                    "__AGENTS__": names,
                },
            )
        )
    return rows


class Renderer:
    """Draws one diagram's SVG, cards and twin from its data and the docs facts."""

    def __init__(
        self, templates: Path, texts: dict[str, Any], agents: list[dict[str, Any]]
    ):
        self.templates = templates
        self.texts = texts
        self.agents = agents

    def t(self, name: str, **tokens: object) -> str:
        """An architecture template, filled."""
        return render_file(self.templates / FOLDER / f"{name}.html", **tokens)

    def facts(self, node: dict[str, Any]) -> list[str]:
        """The generated fact lines a node carries, if any."""
        if node.get("facts") == "tiers":
            return tier_facts(self.texts, self.agents)
        return []

    def svg(self, diagram: Diagram) -> str:
        """The diagram as inline SVG: boundaries, then edges, then nodes as links to their cards."""
        on_path = set(itertools.pairwise(diagram.path))
        boundaries = "".join(
            self.t(
                "boundary",
                X=_num(b["x"]),
                Y=_num(b["y"]),
                W=_num(b["w"]),
                H=_num(b["h"]),
                TX=_num(b["x"] + 12),
                TY=_num(b["y"] + 18),
                LABEL=b["label"],
            )
            for b in diagram.raw.get("boundaries", [])
        )
        edges = []
        for edge in diagram.edges:
            points = edge_points(diagram, edge, self.texts)
            lx, ly = _label_at(edge, points)
            path = (edge["from"], edge["to"]) in on_path
            edges.append(
                self.t(
                    "edge",
                    CLASS="arch-edge arch-on-path" if path else "arch-edge",
                    FROM=edge["from"],
                    TO=edge["to"],
                    D="M" + " L".join(f"{_num(x)},{_num(y)}" for x, y in points),
                    MARKER=f"{diagram.id}-arrow-path"
                    if path
                    else f"{diagram.id}-arrow",
                    LX=_num(lx),
                    LY=_num(ly),
                    LABEL_CLASS=text_class("arch-edge-label", edge),
                    LABEL=edge["label"],
                )
            )
        nodes = []
        for node in diagram.nodes:
            w, h = _size(node, self.texts)
            repo, _ = split_source(node["source"])
            kind = f"arch-node arch-kind-{node['kind']}"
            nodes.append(
                self.t(
                    "node",
                    CLASS=kind
                    + (" arch-on-path" if node["id"] in diagram.path else ""),
                    CARD_ID=card_id(diagram, node),
                    NODE=node["id"],
                    ARIA=f"{node['label']} ({self.texts['kinds'][node['kind']]})",
                    X=_num(node["x"]),
                    Y=_num(node["y"]),
                    W=_num(w),
                    H=_num(h),
                    TX=_num(node["x"] + w / 2),
                    LABEL_Y=_num(node["y"] + h / 2 - 3),
                    REPO_Y=_num(node["y"] + h / 2 + 14),
                    LABEL_CLASS=text_class("arch-node-label", node),
                    LABEL=node["label"],
                    REPO=repo,
                )
            )
        return self.t(
            "svg",
            ID=diagram.id,
            W=_num(diagram.raw["canvas"]["width"]),
            H=_num(diagram.raw["canvas"]["height"]),
            TITLE=diagram.title,
            BOUNDARIES=Safe(boundaries),
            EDGES=Safe("".join(edges)),
            NODES=Safe("".join(nodes)),
        )

    def figure(self, diagram: Diagram, data_href: str) -> str:
        """The SVG with its toolbar, legend and card panel (both revealed by JS), and its data link."""
        texts = self.texts
        kinds = list(dict.fromkeys(n["kind"] for n in diagram.nodes))
        legend = self.t(
            "legend",
            LABEL=texts["legend_label"],
            ITEMS=Safe(
                "".join(
                    self.t("legend-item", KIND=k, LABEL=texts["kinds"][k])
                    for k in kinds
                )
            ),
        )
        title = {"__TITLE__": diagram.title}
        return self.t(
            "figure",
            ID=f"arch-{diagram.id}",
            PATH_BUTTON=texts["path_button"],
            SCROLL_LABEL=data_fill(texts["scroll_label"], title),
            SVG=Safe(self.svg(diagram)),
            LEGEND=Safe(legend),
            NOJS_HINT=texts["nojs_hint"],
            JS_HINT=texts["js_hint"],
            PANEL_LABEL=texts["panel_label"],
            CLOSE=texts["close_button"],
            DATA_HREF=data_href,
            DATA_LINK=texts["data_link"],
        )

    def cards(self, diagram: Diagram) -> str:
        """Every node's card, in file order: the no-JS view of the diagram."""
        items = []
        for node in diagram.nodes:
            facts = self.facts(node)
            facts_html = (
                self.t(
                    "facts",
                    INTRO=self.texts["tiers_intro"],
                    ROWS=Safe(
                        "".join(
                            render_file(self.templates / "docs" / "li.html", TEXT=row)
                            for row in facts
                        )
                    ),
                )
                if facts
                else ""
            )
            items.append(
                self.t(
                    "card",
                    KIND=node["kind"],
                    CARD_ID=card_id(diagram, node),
                    NODE=node["id"],
                    LABEL=label_prose(node),
                    KIND_LABEL=self.texts["kinds"][node["kind"]],
                    CARD=Prose(node["card"]),
                    FACTS=Safe(facts_html),
                    SOURCE_WORD=self.texts["source_word"],
                    HREF=source_url(self.texts, diagram, node["source"]),
                    SOURCE=node["source"],
                    SHA12=diagram.pins[split_source(node["source"])[0]][:12],
                )
            )
        return self.t("cards", ITEMS=Safe("".join(items)))


def _nodes(diagram: Diagram) -> dict[str, dict[str, Any]]:
    """Node id to node."""
    return {n["id"]: n for n in diagram.nodes}


def _code_span(item: dict[str, Any]) -> str:
    """A label as Prose source: wrapped in backticks when it is a command."""
    return f"`{item['label']}`" if item.get("code") else item["label"]


def _connection(
    texts: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    edge: dict[str, Any],
    label: Callable[[dict[str, Any]], str],
) -> str:
    """One edge as a line of text: from, to and its label, each written by `label`."""
    return data_fill(
        texts["connection_row"],
        {
            "__FROM__": label(nodes[edge["from"]]),
            "__TO__": label(nodes[edge["to"]]),
            "__LABEL__": label(edge),
        },
    )


def data_href(texts: dict[str, Any], diagram: Diagram) -> str:
    """Where the build publishes a diagram's JSON."""
    return f"{texts['api_dir']}/{diagram.id}.json"


def page(
    ctx: Any, body: Any, section: Section, diagram: Diagram, texts: dict[str, Any]
) -> None:
    """One diagram page's sections, as HTML and as its Markdown twin."""
    draw = Renderer(ctx.templates, texts, ctx.agents)
    nodes = _nodes(diagram)
    href = data_href(texts, diagram)
    section(
        ctx,
        body,
        texts["diagram_heading"],
        draw.figure(diagram, href),
        f"[{md_escape(texts['data_link'])}]({href})\n",
    )

    md_cards = []
    for node in diagram.nodes:
        line = (
            f"- **{label_md(node)}** ({md_escape(texts['kinds'][node['kind']])}): "
            f"{md_prose(node['card'])} {md_escape(texts['source_word'])}: "
            f"[{md_escape(node['source'])}]({source_url(texts, diagram, node['source'])})\n"
        )
        facts = draw.facts(node)
        if facts:
            line += f"  {md_escape(texts['tiers_intro'])}\n"
            line += "".join(f"  - {md_escape(row)}\n" for row in facts)
        md_cards.append(line)
    section(
        ctx, body, texts["components_heading"], draw.cards(diagram), "".join(md_cards)
    )

    rows = [_connection(texts, nodes, e, _code_span) for e in diagram.edges]
    md_rows = [_connection(texts, nodes, e, label_md) for e in diagram.edges]
    section(
        ctx,
        body,
        texts["connections_heading"],
        ctx.t(
            "list",
            ITEMS=Safe("".join(ctx.t("li", TEXT=Prose(row)) for row in rows)),
        ),
        "".join(f"- {row}\n" for row in md_rows),
    )

    if diagram.path:
        steps = [nodes[i] for i in diagram.path]
        section(
            ctx,
            body,
            texts["path_heading"],
            ctx.t("para", TEXT=texts["path_intro"])
            + draw.t(
                "path-list",
                ITEMS=Safe("".join(ctx.t("li", TEXT=label_prose(s)) for s in steps)),
            ),
            f"{md_escape(texts['path_intro'])}\n\n"
            + "".join(f"{i}. {label_md(s)}\n" for i, s in enumerate(steps, 1)),
        )

    pins = list(diagram.pins.items())
    section(
        ctx,
        body,
        texts["sources_heading"],
        ctx.t("para", TEXT=texts["sources_intro"])
        + ctx.t(
            "list",
            ITEMS=Safe(
                "".join(
                    draw.t(
                        "source-item",
                        REPO=repo,
                        HREF=commit_url(texts, repo, sha),
                        SHA12=sha[:12],
                    )
                    for repo, sha in pins
                )
            ),
        ),
        f"{md_escape(texts['sources_intro'])}\n\n"
        + "".join(
            f"- {md_code(repo)} @ [{sha[:12]}]({commit_url(texts, repo, sha)})\n"
            for repo, sha in pins
        ),
    )


def index(
    ctx: Any,
    body: Any,
    section: Section,
    diagrams: list[Diagram],
    texts: dict[str, Any],
    base: str,
) -> None:
    """The Architecture page's list of diagrams."""
    items = "".join(
        render_file(
            ctx.templates / FOLDER / "index-item.html",
            HREF=f"{base}{d.id}/",
            TITLE=d.title,
            SUMMARY=d.summary,
        )
        for d in diagrams
    )
    section(
        ctx,
        body,
        texts["index_heading"],
        ctx.t("list", ITEMS=Safe(items)),
        "".join(
            f"- [{md_escape(d.title)}]({base}{d.id}/index.md): {md_escape(d.summary)}\n"
            for d in diagrams
        ),
    )
    rows = [
        data_fill(
            texts["kind_row"],
            {"__KIND__": label, "__NOTE__": texts["kind_notes"][kind]},
        )
        for kind, label in texts["kinds"].items()
    ]
    section(
        ctx,
        body,
        texts["kinds_heading"],
        ctx.t("para", TEXT=texts["kinds_intro"])
        + ctx.t("list", ITEMS=Safe("".join(ctx.t("li", TEXT=row) for row in rows))),
        f"{md_escape(texts['kinds_intro'])}\n\n"
        + "".join(f"- {md_escape(row)}\n" for row in rows),
    )


def write_data(out_dir: Path, diagrams: list[Diagram], texts: dict[str, Any]) -> None:
    """Each diagram's JSON, as checked, under the docs API folder."""
    folder = out_dir / texts["api_dir"].lstrip("/")
    folder.mkdir(parents=True, exist_ok=True)
    for d in diagrams:
        (folder / f"{d.id}.json").write_text(
            json.dumps(d.raw, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )


# --- the cited-path check -------------------------------------------------------


def _git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git in a folder and keep its output."""
    return subprocess.run(
        ["git", "-C", str(repo_dir), *args], capture_output=True, text=True, check=False
    )


def fetch(clones: Path, repo: str, sha: str, texts: dict[str, Any]) -> None:
    """Make sure clones/<repo> holds the commit: a blobless clone, then a fetch of the commit."""
    target = clones / repo
    if not (target / ".git").exists() and not (target / "HEAD").exists():
        url = data_fill(texts["repo_url"], {"__REPO__": repo})
        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--filter=blob:none",
                "--no-checkout",
                url,
                str(target),
            ],
            check=True,
        )
    if _git(target, "cat-file", "-e", f"{sha}^{{commit}}").returncode:
        _git(target, "fetch", "--quiet", "--filter=blob:none", "origin", sha)


def missing_sources(diagrams: list[Diagram], where: Callable[[str], Path]) -> list[str]:
    """Every cited `repo/path` (and pin) not found at its diagram's pinned commit."""
    problems = []
    for d in diagrams:
        for repo, sha in d.pins.items():
            if _git(where(repo), "cat-file", "-e", f"{sha}^{{commit}}").returncode:
                problems.append(f"{d.id}: {repo} has no commit {sha}")
        for node in d.nodes:
            repo, path = split_source(node["source"])
            found = _git(
                where(repo), "ls-tree", "--name-only", d.pins[repo], "--", path
            )
            if found.returncode or found.stdout.strip() != path:
                problems.append(
                    f"{d.id}: {node['source']} is missing at {repo}@{d.pins[repo][:12]}"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    """`--check`: every cited path exists at its pinned commit, in clones under --clones."""
    parser = argparse.ArgumentParser(prog="python -m sitegen.architecture")
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument(
        "--clones", type=Path, required=True, help="a folder of clones, one per repo"
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="use PATH for repo NAME",
    )
    parser.add_argument(
        "--fetch", action="store_true", help="clone or fetch what is missing first"
    )
    args = parser.parse_args(argv)
    overrides = dict(item.split("=", 1) for item in args.repo)
    texts = load_texts()
    diagrams = load(texts=texts)

    def where(repo: str) -> Path:
        return Path(overrides[repo]) if repo in overrides else args.clones / repo

    if args.fetch:
        args.clones.mkdir(parents=True, exist_ok=True)
        for d in diagrams:
            for repo, sha in d.pins.items():
                if repo not in overrides:
                    fetch(args.clones, repo, sha, texts)
    problems = missing_sources(diagrams, where)
    for problem in problems:
        print(problem, file=sys.stderr)
    cited = sum(len(d.nodes) for d in diagrams)
    if problems:
        print(
            f"{len(problems)} of {cited} cited paths or pins are missing",
            file=sys.stderr,
        )
        return 1
    print(f"all {cited} cited paths exist at their pinned commits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
