"""Plan 6.8 checks: markdown twins, llms files, JSON API, agent-safe phrasing."""

import json
import re
from pathlib import Path

BANNED = ("you must run", "run this now", "without asking", "automatically install")
FRONT = (
    "id",
    "track",
    "version",
    "label",
    "keyword",
    "where",
    "sha256",
    "source",
    "catalog_ref",
)


def _site(built) -> dict:
    return json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))


def _md_twin(page: Path) -> Path:
    return (
        page.parent / "index.md"
        if page.name == "index.html"
        else page.with_suffix(".md")
    )


def test_every_page_has_a_markdown_twin(built) -> None:
    for page in sorted(built.out.rglob("*.html")):
        twin = _md_twin(page)
        assert twin.is_file(), f"missing twin for {page.relative_to(built.out)}"


def test_policy_twin_front_matter_matches_api(built) -> None:
    for policy in _site(built)["policies"]:
        twin = (
            built.out / "coding" / "policies" / policy["id"] / "index.md"
        ).read_text(encoding="utf-8")
        assert twin.startswith("---"), policy["id"]
        front = twin.split("---", 2)[1]
        for key in FRONT:
            assert re.search(rf"^{key}:", front, re.MULTILINE), f"{policy['id']}: {key}"
        assert f"id: {policy['id']}" in front
        assert f"track: {policy['track']}" in front
        assert f"sha256: {policy['sha256']}" in front
        assert f"catalog_ref: {_site(built)['catalog']['ref']}" in front


def test_llms_txt_structure(built) -> None:
    text = (built.out / "llms.txt").read_text(encoding="utf-8")
    assert text.startswith(("# chock.sh\n\n> ", "# chock.sh\n> "))
    # Plan 6.8 freezes these headings, in this order.
    headings = re.findall(r"^## .+$", text, re.MULTILINE)
    assert headings == [
        "## Docs",
        "## Coding agents",
        "## Coding agents: policies",
        "## Coding agents: presets",
        "## Data",
    ]
    policies_section = text.split("## Coding agents: policies")[1].split("## ")[0]
    for policy in _site(built)["policies"]:
        line = f"](/coding/policies/{policy['id']}/index.md)"
        assert line in policies_section, policy["id"]
    for preset in _site(built)["presets"]:
        assert f"#{preset['id']}" in text or preset["id"] in text, preset["id"]


def test_llms_full_concatenates_in_order(built) -> None:
    full = (built.out / "llms-full.txt").read_text(encoding="utf-8")
    docs = re.findall(r"^# (/[^\n]+\.md)$", full, re.MULTILINE)
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    llms_docs = re.findall(r"\]\((/[^\s)]+\.md)\)", llms)
    assert set(docs) == set(llms_docs)
    assert docs == [d for d in llms_docs if d in docs]
    for twin in built.out.rglob("index.md"):
        body = twin.read_text(encoding="utf-8").strip()
        assert body in full, twin


def test_api_files(built) -> None:
    index = json.loads((built.out / "api" / "index.json").read_text(encoding="utf-8"))
    assert index["schema_version"] == 1
    assert [t["id"] for t in index["tracks"]] == [t.id for t in built.site.tracks]
    assert index["tracks"][0]["api"] == "/api/coding/"
    catalog = json.loads(
        (built.out / "api" / "coding" / "catalog.json").read_text(encoding="utf-8")
    )
    site = _site(built)
    assert catalog["schema_version"] == 1
    assert catalog["track"] == "coding"
    assert catalog["policies"] == site["policies"]
    assert catalog["presets"] == site["presets"]
    by_id = {p["id"]: p for p in site["policies"]}
    for pid, record in by_id.items():
        api = json.loads(
            (built.out / "api" / "coding" / "policies" / f"{pid}.json").read_text(
                encoding="utf-8"
            )
        )
        assert api.pop("schema_version") == 1
        assert api == record, pid
    presets = json.loads(
        (built.out / "api" / "coding" / "presets.json").read_text(encoding="utf-8")
    )
    assert presets["schema_version"] == 1
    schema = json.loads(
        (built.out / "api" / "coding" / "selection.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert "policies" in schema.get("properties", {})


def test_policy_rows_carry_data_attributes(built) -> None:
    text = (built.out / "coding" / "policies" / "index.html").read_text(
        encoding="utf-8"
    )
    rows = re.findall(r'<article class="row[^"]*"[^>]*>', text)
    assert len(rows) == len(_site(built)["policies"])
    for row in rows:
        for attr in (
            "data-policy-id",
            "data-label",
            "data-where",
            "data-groups",
        ):
            assert attr in row, row


def test_chip_title_format(built) -> None:
    text = (built.out / "coding" / "policies" / "index.html").read_text(
        encoding="utf-8"
    )
    for title in re.findall(r'class="label label-\w+" title="([^"]+)"', text):
        word, _, _meaning = title.partition(": ")
        assert word in ("blocks", "asks", "warns", "advisory")


def _agent_files(built) -> list[Path]:
    files = [p for p in built.out.rglob("*") if p.suffix in (".md", ".txt")]
    files.append(built.out / "for-agents" / "index.html")
    return files


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def test_chock_install_sentences_ask(built) -> None:
    for path in _agent_files(built):
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".html":
            text = re.sub(r"<[^>]+>", " ", text)
        for sentence in _sentences(text):
            if "chock install" in sentence:
                assert "ask" in sentence.lower(), f"{path}: {sentence!r}"


def test_no_imperative_agent_phrasing(built) -> None:
    for path in _agent_files(built):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in BANNED:
            assert phrase not in text, f"{path}: {phrase!r}"


def test_worked_example_decodes_and_validates(built) -> None:
    from sitegen import engine
    from sitegen.presets import load_presets

    text = (built.out / "for-agents" / "index.md").read_text(encoding="utf-8")
    object_block = re.search(r"```json\n(.*?)\n```", text, re.DOTALL).group(1)
    code = re.search(r"# Share code\n(\S+)\n", text).group(1)
    command = re.search(r"\n(chock install --selection '[^']+' --apply)", text).group(1)
    assert command == f"chock install --selection '{code}' --apply"
    selection = engine.load_selection(code)
    assert selection == json.loads(object_block)
    engine.check_selection(selection)
    members = next(
        p.members
        for p in load_presets(Path(__file__).parents[1] / "data" / "presets.yaml")
        if p.id == "git-hygiene"
    )
    assert selection["preset"] == "git-hygiene"
    assert [p["id"] for p in selection["policies"]] == sorted(members)
    html = (built.out / "for-agents" / "index.html").read_text(encoding="utf-8")
    assert code in html


def test_builder_texts_are_in_site_json(built) -> None:
    texts = _site(built)["builder_texts"]
    for key in ("link_unreadable", "ref_mismatch", "use_same", "not_available"):
        assert texts[key]
