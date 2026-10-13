"""DOC-2: the Monitor and Troubleshooting pages follow the engine's decision log, summary and export."""

import html
from pathlib import Path

import yaml

from sitegen import engine

ROOT = Path(__file__).resolve().parents[1]
DOCS = yaml.safe_load((ROOT / "data" / "docs.yaml").read_text(encoding="utf-8"))
TEXTS = DOCS["texts"]


def _page(built, key: str, name: str = "index.html") -> str:
    path = DOCS["pages"][key]["path"].strip("/")
    return (built.out / path / name).read_text(encoding="utf-8")


def test_monitor_lists_each_routes_log_files_from_the_engine(built) -> None:
    page, twin = _page(built, "monitor"), _page(built, "monitor", "index.md")
    files = engine.gate_logs()
    assert set(files) == {"sync", "plugin"}
    for paths in files.values():
        for path in paths:
            assert f"<code>{html.escape(path)}</code>" in page, path
            assert f"`{path}`" in twin, path


def test_monitor_shows_summary_and_export_as_the_engine_prints_them(built) -> None:
    page, twin = _page(built, "monitor"), _page(built, "monitor", "index.md")
    export = engine.subcommand_help("witness", "export")
    assert export.startswith("usage: chock witness export")
    assert html.escape(export) in page
    assert export.split("\n\n", 1)[0] in twin
    status = next(c for c in engine.cli_commands() if c["name"] == "status")
    assert "--summary" in status["help"]
    assert html.escape(status["help"]) in page
    assert TEXTS["summary_command"] in page and TEXTS["summary_command"] in twin


def test_monitor_states_the_person_only_rule_from_the_catalog(built) -> None:
    policy = next(p for p in built.site.policies if p.id == TEXTS["person_only_policy"])
    page, twin = _page(built, "monitor"), _page(built, "monitor", "index.md")
    for text in (page, twin):
        assert f"{policy.id} ({policy.version} in the pinned catalog)" in text
        assert "the whole <code>.chock/</code> folder" in text or (
            "the whole `.chock/` folder" in text
        )
    assert f'href="/docs/policies/{policy.id}/"' in page


def test_monitor_quotes_the_engine_decision_log(built) -> None:
    page = _page(built, "monitor")
    assert "/docs/decision-log.md" in page
    for heading in ("Levels", "Reading it"):
        assert f">{heading}</h2>" in page, heading


def test_troubleshooting_says_how_to_read_the_log(built) -> None:
    page, twin = (
        _page(built, "troubleshooting"),
        _page(built, "troubleshooting", "index.md"),
    )
    assert f">{TEXTS['diagnose_heading']}</h2>" in page
    assert "<code>chock status --only log</code>" in page
    assert "<code>chock witness export --client &lt;client&gt;</code>" in page
    section = twin.split(f"## {TEXTS['diagnose_heading']}", 1)[1].split("\n## ", 1)[0]
    for line in section.splitlines():
        if "`chock " in line:
            assert "ask" in line.lower(), line
