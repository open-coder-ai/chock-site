"""The release version marker: data/release.yaml, dist/version.json and the footer."""

import json
from pathlib import Path

import pytest

from sitegen.version import VersionError, load_version

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _pin(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8").strip()


def test_version_json_is_version_engine_catalog(built) -> None:
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
    ["version: 1.0\n", "version: v1.0.0\n", "version: 1.0.0-rc1\n", "other: 1\n", ""],
)
def test_malformed_version_is_refused(tmp_path: Path, text: str) -> None:
    (tmp_path / "release.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(VersionError):
        load_version(tmp_path)


def test_release_yaml_version_is_semver() -> None:
    assert load_version(DATA).count(".") == 2
