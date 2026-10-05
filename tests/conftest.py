"""Session fixtures: the pinned catalog checkout and the site built once from it."""

from collections import namedtuple
from pathlib import Path

import pytest

from sitegen.__main__ import build

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / ".catalog"
DATA = ROOT / "data"

Built = namedtuple("Built", ["site", "out"])


@pytest.fixture(scope="session")
def catalog_path() -> Path:
    """The pinned chock-catalog checkout at the repo root."""
    assert CATALOG.is_dir(), "clone chock-catalog into .catalog (see README)"
    return CATALOG


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory, catalog_path: Path) -> Built:
    """The site built once per session, with the local catalog as catalog.source."""
    out = tmp_path_factory.mktemp("dist")
    site = build(catalog_path, out, str(catalog_path.resolve()), None)
    return Built(site, out)
