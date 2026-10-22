"""A rendered install command shows the selection code bare, never in quotes (cmd.exe passes quotes through)."""

import re

# A quote, or its HTML escape, straight after --selection; a path in "$FOLDER/..." (author script) is not a code.
QUOTED = re.compile(r"--selection\s+(?:['\"]|&#x27;|&quot;|&#34;|&#39;)(?!\$FOLDER/)")
SUFFIXES = {".html", ".md", ".txt", ".js", ".json", ".yaml"}


def _quoted_selections(root) -> list[str]:
    """Every file under root, with the text around each quoted selection argument."""
    found = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in QUOTED.finditer(text):
            found.append(
                f"{path.relative_to(root)}: {text[match.start() : match.end() + 40]!r}"
            )
    return found


def test_no_page_quotes_the_selection_code(built) -> None:
    """Pages, agent twins and scripts of the built site never wrap the selection code in quotes."""
    assert _quoted_selections(built.out) == []


def test_no_untested_page_quotes_the_selection_code(built_untested) -> None:
    """The same holds where every agent takes the untested command form."""
    assert _quoted_selections(built_untested.out) == []


def test_the_check_sees_a_quoted_code() -> None:
    """The pattern catches the quote forms a page can carry."""
    for text in (
        "chock install --selection 'abc' --client x",
        'chock install --selection "abc" --client x',
        "chock install --selection &#x27;abc&#x27; --client x",
    ):
        assert QUOTED.search(text), text
    assert not QUOTED.search("chock install --selection abc-_9 --client x")
