"""Install the engine's commit-pinned git dependencies, each with --no-deps."""

import re
import subprocess
import sys
from importlib import metadata

# Only an open-coder-ai repo at a full commit; anything else is refused.
GIT_PIN = re.compile(
    r"([A-Za-z0-9][\w.-]*) @ git\+https://github\.com/open-coder-ai/[\w.-]+@[0-9a-f]{40}"
)


def git_pins(requires: list[str]) -> list[str]:
    """The direct-reference requirements in requires, refusing any loose one."""
    pins = []
    for req in requires:
        req = req.strip()
        if "extra ==" in req or " @ " not in req:
            # Extras are not installed; name-only requirements come from the lock.
            continue
        if not GIT_PIN.fullmatch(req):
            raise SystemExit(
                f"install_engine_deps: not a commit-pinned git source: {req}"
            )
        pins.append(req)
    return pins


def main() -> None:
    """Install every git pin the installed chock engine declares."""
    for req in git_pins(metadata.requires("chock") or []):
        print(f"install_engine_deps: {req}", flush=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "--disable-pip-version-check",
                "install",
                "--quiet",
                "--no-deps",
                "--no-build-isolation",
                req,
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
