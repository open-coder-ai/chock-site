"""The release version marker: data/version.json in, dist/version.json out."""

import json
import re
from pathlib import Path

# chock-release check.py reads this file's "version" (its SITE_VERSION_FILE).
SOURCE = "version.json"
VERSION_JSON = "version.json"
SEMVER = re.compile(r"\d+\.\d+\.\d+")


class VersionError(ValueError):
    """data/version.json is missing, malformed, or holds a malformed version."""


def load_version(data_dir: Path) -> str:
    """The X.Y.Z version from data/version.json, an object with only "version"."""
    path = data_dir / SOURCE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionError(f"{path}: cannot read: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != {"version"}:
        raise VersionError(f'{path}: must be {{"version": "X.Y.Z"}}, got {raw!r}')
    version = raw["version"]
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise VersionError(f"{path}: version must be an X.Y.Z string, got {version!r}")
    return version


def write_version_json(out_dir: Path, version: str, engine: str, catalog: str) -> Path:
    """dist/version.json: {version, engine, catalog}, read by the release verify step."""
    path = out_dir / VERSION_JSON
    path.write_text(
        json.dumps({"version": version, "engine": engine, "catalog": catalog}, indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path
