"""UT-1 finding 5c: the built site is the same whatever OS builds it, with posix paths only."""

import json
from pathlib import Path, PureWindowsPath

import pytest

from sitegen import clientpage, distcheck, engine

TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "coding"


def test_client_tokens_are_posix_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(engine, "Path", PureWindowsPath)
    for client in engine.client_ids():
        tokens = engine.client_tokens(client)
        for key in ("__DEST__", "__PLUGIN_DIR__"):
            assert "\\" not in tokens[key], (client, key, tokens[key])
            assert tokens[key].startswith("~/"), (client, key, tokens[key])


def test_client_steps_are_posix_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(engine, "Path", PureWindowsPath)
    for client in engine.client_ids():
        for step in engine.client_steps(client):
            for text in step.values():
                assert not distcheck.PAGE_PATH.search(text), (client, text)


def test_built_install_page_and_twin_show_no_backslash_path(built) -> None:
    for name in ("index.html", "index.md"):
        text = (built.out / "coding" / "install" / name).read_text(encoding="utf-8")
        assert not distcheck.PAGE_PATH.search(text), name


def test_built_site_passes_the_dist_check(built) -> None:
    assert distcheck.find(built.out) == []


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("page/index.html", "<code>claude plugin add '~\\.chock\\marketplace'</code>"),
        ("page/index.md", "run C:\\Users\\me\\x"),
        ("data/site.json", json.dumps({"steps": ["add ~\\.chock\\marketplace"]})),
    ],
)
def test_dist_check_flags_windows_paths(tmp_path, name, text) -> None:
    target = tmp_path / name
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    assert distcheck.main([str(tmp_path)]) == 1
    assert len(distcheck.find(tmp_path)) == 1


def test_dist_check_allows_json_escapes_and_regexes(tmp_path) -> None:
    data = {"a": "x = 1  # DO\\x20NOT", "b": "^(?!.*\\.\\.)[\\w-]+$"}
    (tmp_path / "x.json").write_text(json.dumps(data), encoding="utf-8")
    assert distcheck.main([str(tmp_path)]) == 0


def test_notes_are_not_numbered_steps() -> None:
    html = clientpage.step_blocks(
        TEMPLATES,
        [
            {"command": "one"},
            {"command": "two"},
            {"note": "Read this."},
            {"settings": "{}"},
            {"command": "three"},
        ],
    )
    assert html.count('<ol class="steps-list"') == 2
    assert 'start="1"' in html and 'start="3"' in html
    assert '<p class="steps-note">Read this.</p>' in html
    first_list = html.split("</ol>")[0]
    assert "Read this." not in first_list and "{}" not in first_list
