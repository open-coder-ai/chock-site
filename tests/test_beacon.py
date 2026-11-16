"""The page-view beacon loader (plan AN-2), tested with Node's built-in runner (tests/node/beacon.test.mjs)."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE_TEST = ROOT / "tests" / "node" / "beacon.test.mjs"


def test_beacon_node_suite() -> None:
    node = shutil.which("node")
    assert node, "node is required to test static/js/common.js loadPageBeacon"
    result = subprocess.run(
        [node, "--test-reporter=tap", "--test", str(NODE_TEST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "# fail 0" in result.stdout
