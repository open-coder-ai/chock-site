"""S-10: every built page that prints a chock install line pins the site's own version."""

import json
import re
from pathlib import Path

from sitegen.version import load_version

ROOT = Path(__file__).resolve().parents[1]
# `pip install chock`, `pipx install chock` or `pip3 install chock`, bare or quoted, and the
# version after `==` if any. The commit-pinned form (`"chock @ git+...@<sha>"`) is not matched.
INSTALL = re.compile(
    r"""\bpip(?:x|3)?\s+install\s+(?:-[\w-]*\s+)*(?:&quot;|["'])?chock(?![\w-])(?!\s*@)"""
    r"""(?:==(\d+(?:\.\d+)*(?:[a-z]+\d+)?))?"""
)
TEXT_SUFFIXES = {".html", ".md", ".txt", ".json", ".xml", ".js"}


def _misprinted(out: Path, version: str) -> list[str]:
    """Each install line in out/ that is unpinned or pins a version other than `version`."""
    found = []
    for path in sorted(out.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        for match in INSTALL.finditer(text):
            if match.group(1) != version:
                found.append(f"{path.relative_to(out)}: {match.group(0)}")
    return found


def _lines(out: Path) -> int:
    """How many chock install lines out/ prints in all."""
    return sum(
        len(INSTALL.findall(p.read_text(encoding="utf-8")))
        for p in out.rglob("*")
        if p.is_file() and p.suffix in TEXT_SUFFIXES
    )


def test_the_site_version_is_the_one_version_json_names(built) -> None:
    built_json = json.loads((built.out / "version.json").read_text(encoding="utf-8"))
    assert built.site.data["version"] == load_version(ROOT / "data")
    assert built_json["version"] == built.site.data["version"]


def test_no_built_page_prints_an_unpinned_or_other_install_line(built_released) -> None:
    version = built_released.site.data["version"]
    assert _misprinted(built_released.out, version) == []
    if built_released.site.data["released"]:
        assert _lines(built_released.out) > 0, (
            "no page prints the released install line"
        )


def test_the_plugin_quickstart_pins_the_version(built_released) -> None:
    if not built_released.site.data["released"]:
        return
    version = built_released.site.data["version"]
    folder = built_released.out / "docs" / "quickstart" / "plugin"
    for name in ("index.html", "index.md"):
        assert f"pipx install chock=={version}" in (folder / name).read_text(
            encoding="utf-8"
        ), name


def test_the_check_refuses_unpinned_and_other_pins(tmp_path: Path) -> None:
    lines = {
        "a.md": "Run `pipx install chock` first.",
        "b.html": "<code>pip install chock</code>",
        "c.txt": "pip install &quot;chock==0.9.0&quot;",
        "d.md": "pipx install chock==1.0.0",
        "e.md": 'pip install "chock @ git+https://github.com/open-coder-ai/chock@abc"',
        "f.md": "pip install chock-catalog",
    }
    for name, text in lines.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    assert _misprinted(tmp_path, "1.0.0") == [
        "a.md: pipx install chock",
        "b.html: pip install chock",
        "c.txt: pip install &quot;chock==0.9.0",
    ]
