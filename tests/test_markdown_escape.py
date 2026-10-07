"""Hostile catalog text cannot plant a Markdown link in the twins or llms files."""

import re
import shutil
from pathlib import Path

import pytest
import yaml

from sitegen.__main__ import build
from sitegen.render import md, md_code

EVIL = "https://evil.example/"
POLICY = "base/agent-discipline"
LINK_RE = re.compile(r"(?<!\\)\]\(" + re.escape(EVIL) + r"|(?<!\\)<" + re.escape(EVIL))


def test_md_escapes_link_syntax() -> None:
    assert md("a](b) [c] <d> `e` \\") == r"a\](b) \[c\] \<d\> \`e\` \\"


def test_md_leaves_plain_parentheses_alone() -> None:
    assert md("Warns only (observe).") == "Warns only (observe)."


def test_md_code_fence_outlasts_backticks_in_the_text() -> None:
    assert md_code("ls") == "`ls`"
    assert md_code("a `b` c") == "``a `b` c``"
    assert md_code("`x") == "`` `x ``"


@pytest.fixture(scope="module")
def hostile_out(tmp_path_factory: pytest.TempPathFactory, catalog_path: Path) -> Path:
    """The site built from a catalog copy whose policy text plants links."""
    catalog = tmp_path_factory.mktemp("catalog") / "c"
    shutil.copytree(catalog_path, catalog, symlinks=True)
    manifest_file = catalog / POLICY / "manifest.yaml"
    manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    manifest["name"] = f"Evil](<{EVIL}n>) [x"
    manifest["description"] = (
        f"Desc <{EVIL}d> [d]({EVIL}d2) `code`. Misses: [m]({EVIL}m) here."
    )
    manifest["changelog"][-1]["changes"] = [f"[c]({EVIL}c)"]
    manifest_file.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    out = tmp_path_factory.mktemp("dist")
    build(catalog, out, str(catalog.resolve()), None)
    return out


def test_no_planted_link_in_any_markdown_or_text_file(hostile_out: Path) -> None:
    files = [*hostile_out.rglob("*.md"), *hostile_out.rglob("*.txt")]
    assert files
    leaks = [
        f"{path.relative_to(hostile_out)}: {match.group(0)}"
        for path in files
        for match in LINK_RE.finditer(path.read_text(encoding="utf-8"))
    ]
    assert not leaks, "\n".join(leaks)


def test_hostile_name_still_reaches_the_policy_twin(hostile_out: Path) -> None:
    twin = (hostile_out / "coding/policies/agent-discipline/index.md").read_text(
        encoding="utf-8"
    )
    assert md(f"Evil](<{EVIL}n>) [x") in twin
