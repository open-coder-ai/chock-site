"""Tests for catalog.py: misses extraction and where tags."""

from sitegen.catalog import extract_misses, where_tags


def test_misses_marker_present() -> None:
    desc = "Blocks bad git flags. Misses: older aliases, scripts, $VARs. More detail follows."
    assert extract_misses(desc) == "older aliases, scripts, $VARs."


def test_misses_not_caught_here_marker() -> None:
    desc = "Scans writes. Not caught here: symlinks. Further text."
    assert extract_misses(desc) == "symlinks."


def test_misses_absent() -> None:
    assert extract_misses("Does a thing. No marker anywhere.") is None


def test_misses_marker_at_end() -> None:
    assert extract_misses("Does a thing. Misses:") == ""


def test_misses_first_marker_by_position() -> None:
    desc = "Not caught here: the gap. Misses: another gap."
    assert extract_misses(desc) == "the gap."


def test_where_command_only() -> None:
    says = "refuses a matched shell command before it runs"
    assert where_tags(says) == ["command"]


def test_where_write_and_turn_end() -> None:
    says = "warns on an agent's file writes and at turn end"
    assert where_tags(says) == ["write", "turn-end"]


def test_where_advisory() -> None:
    says = "advisory only: skill text, nothing stops a violation"
    assert where_tags(says) == ["text"]


def test_where_command_write_turn_end() -> None:
    says = (
        "refuses a matched shell command before it runs; "
        "blocks on an agent's file writes and at turn end"
    )
    assert where_tags(says) == ["command", "write", "turn-end"]
