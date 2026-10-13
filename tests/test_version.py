"""The release version marker: data/version.json, dist/version.json and the footer."""

import json
import re
from pathlib import Path

import pytest

from sitegen.version import VersionError, load_version

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RELEASE_CHECK_FILE = "data/version.json"  # chock-release check.py SITE_VERSION_FILE


def _pin(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8").strip()


def test_source_is_where_the_release_check_reads_it() -> None:
    # check.py does json.loads(text)["version"] on this path and compares it to the manifest.
    raw = json.loads((ROOT / RELEASE_CHECK_FILE).read_text(encoding="utf-8"))
    assert raw == {"version": load_version(DATA)}
    assert re.fullmatch(r"\d+\.\d+\.\d+", raw["version"])


def test_version_json_is_version_engine_catalog(built) -> None:
    # release.py verify fetches <site>/version.json and compares these three keys.
    marker = json.loads((built.out / "version.json").read_text(encoding="utf-8"))
    assert marker == {
        "version": load_version(DATA),
        "engine": _pin(".framework-ref"),
        "catalog": _pin(".catalog-ref"),
    }


def test_footer_shows_version(built) -> None:
    version = load_version(DATA)
    for page in ("index.html", "404.html", "faq/index.html"):
        html = (built.out / page).read_text(encoding="utf-8")
        assert f"v{version} · " in html, page


@pytest.mark.parametrize(
    "text",
    [
        '{"version": "1.0"}',
        '{"version": "v1.0.0"}',
        '{"version": "1.0.0-rc1"}',
        '{"version": 1}',
        '{"version": "1.0.0", "engine": "x"}',
        '{"other": "1.0.0"}',
        '["1.0.0"]',
        "version: 1.0.0",
        "",
    ],
)
def test_malformed_version_is_refused(tmp_path: Path, text: str) -> None:
    (tmp_path / "version.json").write_text(text, encoding="utf-8")
    with pytest.raises(VersionError):
        load_version(tmp_path)


def test_missing_version_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(VersionError):
        load_version(tmp_path)
