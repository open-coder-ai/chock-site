"""The release version marker: data/release.yaml in, dist/version.json out."""

import json
import re
from pathlib import Path

import yaml

RELEASE = "release.yaml"
VERSION_JSON = "version.json"
SEMVER = re.compile(r"\d+\.\d+\.\d+")


class VersionError(ValueError):
    """data/release.yaml is missing its version or holds a malformed one."""


def load_version(data_dir: Path) -> str:
    """The X.Y.Z version from data/release.yaml; anything else is an error."""
    raw = yaml.safe_load((data_dir / RELEASE).read_text(encoding="utf-8"))
    version = raw.get("version") if isinstance(raw, dict) else None
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        msg = f"{data_dir / RELEASE}: version must be a quoted X.Y.Z string, got {version!r}"
        raise VersionError(msg)
    return version


def write_version_json(out_dir: Path, version: str, engine: str, catalog: str) -> Path:
    """dist/version.json: {version, engine, catalog}, read by the release check."""
    path = out_dir / VERSION_JSON
    path.write_text(
        json.dumps({"version": version, "engine": engine, "catalog": catalog}, indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path
