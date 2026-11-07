"""DOCS-1: the installed `chock` exits 2 on an unknown option for each person-only command."""

import shutil
import subprocess
import sys
from pathlib import Path

from sitegen import engine

TREE = engine.cli_tree()
NO_SUCH_OPTION = "--no-such-option-for-the-docs"


def test_every_person_only_command_exits_2_on_an_unknown_option(
    tmp_path: Path,
) -> None:
    # The unit suite checks these parsers in process; this runs the shipped entry point.
    chock = shutil.which("chock", path=str(Path(sys.executable).parent))
    assert chock, "install chock at .framework-ref beside this Python"
    person_only = engine.person_only_commands()
    ran = set()
    for node in TREE:
        if not node["parser"] or node["path"][0] not in person_only:
            continue
        done = subprocess.run(
            [chock, *node["path"], NO_SUCH_OPTION],
            cwd=tmp_path,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert done.returncode == 2, (node["path"], done.stderr[-300:])
        assert "error:" in done.stderr, node["path"]
        ran.add(node["path"][0])
    assert ran == person_only, sorted(person_only - ran)
