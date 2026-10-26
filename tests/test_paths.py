"""SITE-1: a path a data file names stays inside the folder it was named for (sitegen/paths.py)."""

import os
from pathlib import Path

import pytest

from sitegen.pageparts import PageError, page_target, write_md
from sitegen.paths import safe_join


def test_a_relative_path_inside_the_root_resolves_under_it(tmp_path: Path) -> None:
    (tmp_path / "base" / "x").mkdir(parents=True)
    found = safe_join(tmp_path, "base/x")
    assert found == (tmp_path / "base" / "x").resolve()
    assert (
        safe_join(tmp_path, "not-yet-there.md")
        == tmp_path.resolve() / "not-yet-there.md"
    )


@pytest.mark.parametrize(
    ("relative", "reason"),
    [
        ("../../../escaped", "'..' segment"),
        ("base/../../escaped", "'..' segment"),
        ("..", "'..' segment"),
        ("/etc/passwd", "absolute"),
        ("C:\\escaped", "absolute"),
        ("\\\\server\\share", "absolute"),
        ("", "non-empty relative path"),
        (None, "non-empty relative path"),
        (3, "non-empty relative path"),
        (".", "does not stay under"),
        ("base/..", "'..' segment"),
    ],
)
def test_an_escape_is_refused_naming_the_value(
    tmp_path: Path, relative: object, reason: str
) -> None:
    with pytest.raises(PageError, match=reason) as found:
        safe_join(tmp_path, relative, "snapshot")
    assert "snapshot" in str(found.value)
    assert repr(relative) in str(found.value)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks here")
def test_a_symlink_that_leaves_the_root_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    os.symlink(tmp_path / "outside.txt", root / "link.txt")
    with pytest.raises(PageError, match="does not stay under"):
        safe_join(root, "link.txt")


def test_a_root_that_is_itself_a_symlink_still_contains_its_files(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    (real / "a").mkdir(parents=True)
    link = tmp_path / "link"
    os.symlink(real, link)
    assert safe_join(link, "a") == (real / "a").resolve()


def test_a_page_route_is_written_under_the_output_folder(tmp_path: Path) -> None:
    out = tmp_path.resolve()
    assert page_target(tmp_path, "/", "index.html") == out / "index.html"
    assert page_target(tmp_path, "/coding/policies/block-no-verify/", "index.md") == (
        out / "coding" / "policies" / "block-no-verify" / "index.md"
    )
    assert page_target(tmp_path, "/llms.txt", "index.html") == out / "llms.txt"
    assert write_md(tmp_path, "/x/", "# x\n") == out / "x" / "index.md"


@pytest.mark.parametrize(
    "route",
    ["/../escaped/", "/coding/policies/../../../escaped/", "/coding/policies/.."],
)
def test_a_page_route_that_leaves_the_output_folder_is_refused(
    tmp_path: Path, route: str
) -> None:
    with pytest.raises(PageError, match="page route") as found:
        write_md(tmp_path, route, "outside")
    assert repr(route) in str(found.value)
    assert not list(tmp_path.parent.glob("escaped*"))
