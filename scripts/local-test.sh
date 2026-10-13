#!/usr/bin/env bash
# Build and serve chock-site locally at its pinned catalog and engine, as CI does.
# Run from a chock-site checkout (any folder inside it works):
#   bash scripts/local-test.sh                 # build + serve http://127.0.0.1:8000/
#   bash scripts/local-test.sh --test          # also run unit, then browser (e2e) tests
#   bash scripts/local-test.sh --port 8080     # serve on another port
#   bash scripts/local-test.sh --no-serve      # build dist/ only, then exit (CI uses this)
#   bash scripts/local-test.sh --no-open       # serve without opening a browser
# Needs: git and Python 3.12 or newer. Installs nothing outside this checkout.
set -euo pipefail
export PYTHONUTF8=1

run_tests=0
serve=1
open_browser=1
port=8000

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
step() { printf '\n==> %s\n' "$*"; }
usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        --test) run_tests=1 ;;
        --no-serve) serve=0 ;;
        --no-open) open_browser=0 ;;
        --port)
            [ "$#" -ge 2 ] || die "--port needs a number"
            port="$2"
            shift
            ;;
        --port=*) port="${1#--port=}" ;;
        -h | --help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done
case "$port" in
    '' | *[!0-9]*) die "--port must be a number, got '$port'" ;;
esac

step "Checking tools"
[ -n "$(command -v git || true)" ] || die "git not found. Install Git: https://git-scm.com/downloads"
python_cmd=""
for cand in python3.12 python3; do
    if [ -n "$(command -v "$cand" || true)" ] \
        && "$cand" -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
        python_cmd="$cand"
        break
    fi
done
[ -n "$python_cmd" ] || die "Python 3.12 not found (tried python3.12, python3). Install it: https://www.python.org/downloads/"
git --version
"$python_cmd" --version

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [ ! -f .catalog-ref ] || [ ! -f .framework-ref ]; then
    die "run this from a chock-site checkout (.catalog-ref and .framework-ref not found in $root)"
fi
catalog_ref="$(tr -d '[:space:]' < .catalog-ref)"
engine_ref="$(tr -d '[:space:]' < .framework-ref)"
echo "site      $(git rev-parse --short HEAD)"
echo "catalog   $catalog_ref (.catalog-ref)"
echo "engine    $engine_ref (.framework-ref)"

step "Catalog at the pinned commit -> .catalog"
# Keep LF endings: CRLF would change policy sha256s and break the site's pins.
if [ ! -e .catalog ]; then
    git -c core.autocrlf=false clone --quiet https://github.com/open-coder-ai/chock-catalog.git .catalog
elif [ ! -e .catalog/.git ]; then
    die ".catalog exists but is not a git checkout. Move it away and run again."
fi
git -C .catalog config core.autocrlf false
if [ -f .catalog/.git/shallow ]; then
    git -C .catalog fetch --quiet --unshallow origin
fi
if [ -z "$(git -C .catalog rev-parse -q --verify "${catalog_ref}^{commit}" || true)" ]; then
    git -C .catalog fetch --quiet origin
fi
git -C .catalog checkout --quiet --force "$catalog_ref"
if git -C .catalog ls-files --eol | grep -q 'i/lf.*w/crlf'; then
    die ".catalog has files checked out with CRLF endings. Move .catalog away and run again."
fi
echo "catalog at $(git -C .catalog rev-parse --short HEAD)"

step "Python environment (.venv) with the pinned chock engine"
if [ ! -d .venv ]; then
    "$python_cmd" -m venv .venv
fi
py="$root/.venv/bin/python"
[ -x "$py" ] || die ".venv has no bin/python. Move .venv away and run again."
"$py" -c 'import sys; sys.exit(sys.version_info < (3, 12))' \
    || die ".venv uses Python older than 3.12. Move .venv away and run again."
marker=".venv/chock-framework-ref"
installed_ref=""
[ -f "$marker" ] && installed_ref="$(cat "$marker")"
if [ "$installed_ref" != "$engine_ref" ] \
    && "$py" -c 'import importlib.util, sys; sys.exit(importlib.util.find_spec("chock") is None)'; then
    # The pin changed (or first run): drop the old engine so pip installs the pinned one.
    "$py" -m pip uninstall --quiet --yes chock
fi
# PyPI packages are checked by hash; the engine is pinned by commit and pulls nothing else.
"$py" -m pip install --quiet --require-hashes -r requirements-dev.txt
"$py" -m pip install --quiet --no-deps --no-build-isolation "chock @ git+https://github.com/open-coder-ai/chock@${engine_ref}"
"$py" scripts/install_engine_deps.py
"$py" -m pip check
printf '%s\n' "$engine_ref" > "$marker"
"$py" -m chock --version

if [ "$run_tests" -eq 1 ]; then
    step "Unit tests"
    "$py" -m pytest -q --ignore=tests/e2e
    step "Browser tests (downloads Playwright's Chromium once)"
    "$py" -m playwright install chromium
    "$py" -m pytest -q tests/e2e
fi

tmp_dest="$("$py" -c 'import os, tempfile; print(os.path.join(tempfile.gettempdir(), "chock-try"))')"
engine_check() {
    echo "To test a builder selection end to end, in a second terminal:"
    echo "  \"$py\" -m chock install --selection '<code from the builder>' --client codex --dest \"$tmp_dest\""
    echo "  (no --apply: it only builds the plugin into that folder; your agent config is untouched)"
}

if [ "$serve" -eq 0 ]; then
    step "Building dist/"
    "$py" -m sitegen --catalog .catalog --out dist
    [ -f dist/index.html ] || die "build finished but dist/index.html is missing"
    echo "Built $root/dist/index.html"
    engine_check
    exit 0
fi

step "Building and serving http://127.0.0.1:${port}/ (Ctrl+C to stop)"
engine_check
if [ "$open_browser" -eq 1 ]; then
    opener=""
    for cand in xdg-open open; do
        if [ -n "$(command -v "$cand" || true)" ]; then opener="$cand"; break; fi
    done
    if [ -n "$opener" ]; then
        # Open the page once the server answers (the build runs first).
        port_up='import socket, sys
try:
    socket.create_connection(("127.0.0.1", int(sys.argv[1])), 1).close()
except OSError:
    sys.exit(1)'
        (
            for _ in $(seq 1 120); do
                if "$py" -c "$port_up" "$port"; then
                    "$opener" "http://127.0.0.1:${port}/" || true
                    exit 0
                fi
                sleep 1
            done
        ) &
    else
        echo "No xdg-open or open found: open http://127.0.0.1:${port}/ yourself."
    fi
fi
exec "$py" -m sitegen serve --catalog .catalog --port "$port"
