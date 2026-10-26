"""The deep-link same-pack comparison, tested with Node's built-in runner (tests/node/samepack.test.mjs)."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE_TEST = ROOT / "tests" / "node" / "samepack.test.mjs"


def test_samepack_node_suite() -> None:
    node = shutil.which("node")
    assert node, "node is required to test static/js/samepack.js"
    result = subprocess.run(
        [node, "--experimental-detect-module", "--test", str(NODE_TEST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "# fail 0" in result.stdout
