"""A copy of data/ with the fixture agent untested and given an evidence row."""

import shutil
from pathlib import Path

import yaml

DATA = Path(__file__).resolve().parents[2] / "data"
FIXTURE = yaml.safe_load(
    (Path(__file__).with_name("untested-agent.yaml")).read_text(encoding="utf-8")
)
CLIENT = FIXTURE["client"]
ISSUE = FIXTURE["issue"]


def _edit(path: Path, edit) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def untested_data(dest: Path) -> Path:
    """Copy data/ to dest, mark CLIENT untested and add the ISSUE evidence row."""
    shutil.copytree(DATA, dest)
    _edit(dest / "witness.yaml", lambda d: d["clients"].update({CLIENT: "untested"}))
    _edit(dest / "evidence.yaml", lambda d: d["issues"].update({CLIENT: ISSUE}))
    return dest
