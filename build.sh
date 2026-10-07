#!/bin/sh
# Cloudflare Pages build (and CI): the pinned engine and catalog, then the site in dist/.
# Network: the two git sources below and PyPI. No secrets.
set -eu

cd "$(dirname "$0")"

ENGINE_URL=${ENGINE_URL:-https://github.com/open-coder-ai/chock}
CATALOG_URL=${CATALOG_URL:-https://github.com/open-coder-ai/chock-catalog}
PYTHON=${PYTHON:-python3}

fail() {
  echo "build.sh: $*" >&2
  exit 1
}

# A pin is one line holding a full 40-hex commit, nothing else.
read_pin() {
  [ -f "$1" ] || fail "$1 is missing"
  pin=$(cat "$1")
  case $pin in
    *[!0-9a-f]*) fail "$1 is not a full lowercase commit SHA: '$pin'" ;;
  esac
  [ ${#pin} -eq 40 ] || fail "$1 is not a full 40-hex commit SHA: '$pin'"
  printf '%s\n' "$pin"
}

FRAMEWORK_REF=$(read_pin .framework-ref)
CATALOG_REF=$(read_pin .catalog-ref)

"$PYTHON" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' \
  || fail "needs Python 3.12 (set PYTHON_VERSION=3.12); got $("$PYTHON" -V 2>&1)"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "build.sh: catalog $CATALOG_REF from $CATALOG_URL"
git init -q "$work/catalog"
git -C "$work/catalog" fetch -q --depth 1 "$CATALOG_URL" "$CATALOG_REF" \
  || fail "cannot fetch catalog commit $CATALOG_REF from $CATALOG_URL"
git -C "$work/catalog" -c advice.detachedHead=false checkout -q --detach FETCH_HEAD
head=$(git -C "$work/catalog" rev-parse HEAD)
[ "$head" = "$CATALOG_REF" ] \
  || fail "catalog HEAD is $head, expected $CATALOG_REF (.catalog-ref)"

echo "build.sh: engine $FRAMEWORK_REF from $ENGINE_URL"
"$PYTHON" -m venv "$work/venv"
"$work/venv/bin/python" -m pip install -q --disable-pip-version-check \
  -r requirements-build.txt "chock @ git+$ENGINE_URL@$FRAMEWORK_REF"

"$work/venv/bin/python" -m sitegen --catalog "$work/catalog" --out dist

[ -f dist/_headers ] || fail "dist/_headers is missing"
[ -f dist/version.json ] || fail "dist/version.json is missing"
echo "build.sh: dist/ built"
