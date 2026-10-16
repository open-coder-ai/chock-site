"""DOCS-6: each tape has its video, poster and sidecar; a tape changed without a re-render fails."""

import html
import shutil
from pathlib import Path

import yaml

from sitegen import videos

ROOT = Path(__file__).resolve().parents[1]
DOCS = yaml.safe_load((ROOT / "data" / "docs.yaml").read_text(encoding="utf-8"))
HOME = yaml.safe_load((ROOT / "data" / "home.yaml").read_text(encoding="utf-8"))
NAMES = ("own-policy", "adopt-policy", "catalog-policy")
PAGES = {
    "write-own": "own-policy",
    "catalog-adopt": "adopt-policy",
    "catalog-contribute": "catalog-policy",
}


def test_every_tape_matches_its_render_and_the_size_cap() -> None:
    assert videos.check(ROOT) == []
    assert sorted(t.stem for t in (ROOT / videos.TAPES).glob("*.tape")) == sorted(NAMES)
    for name in NAMES:
        assert videos.load(ROOT, name)["mp4_bytes"] <= videos.MAX_BYTES


def test_a_changed_tape_fails_until_it_is_rendered_again(tmp_path: Path) -> None:
    for folder in (videos.TAPES, videos.STATIC):
        (tmp_path / folder).mkdir(parents=True)
    for name in NAMES:
        shutil.copy(ROOT / videos.TAPES / f"{name}.tape", tmp_path / videos.TAPES)
        for suffix in (".mp4", ".png", ".json"):
            shutil.copy(
                ROOT / videos.STATIC / f"{name}{suffix}", tmp_path / videos.STATIC
            )
    assert videos.check(tmp_path) == []
    tape = tmp_path / videos.TAPES / "own-policy.tape"
    tape.write_text(tape.read_text(encoding="utf-8") + "Sleep 1s\n", encoding="utf-8")
    assert videos.check(tmp_path) == [
        "own-policy: the tape changed since the video was rendered; re-render it"
    ]


def test_the_catalog_videos_ran_the_pinned_catalog() -> None:
    ref = (ROOT / ".catalog-ref").read_text(encoding="utf-8").strip()
    assert videos.load(ROOT, "own-policy")["catalog"] is None
    for name in ("adopt-policy", "catalog-policy"):
        assert videos.load(ROOT, name)["catalog"] == ref
        assert ref in (ROOT / videos.TAPES / f"{name}.tape").read_text(encoding="utf-8")


def test_shown_commands_leave_out_the_hidden_setup_and_clear() -> None:
    tape = (
        'Hide\nType "secret setup"\nEnter\nShow\nType "a"\nEnter\nType "clear"\nEnter\n'
    )
    tape += (
        'Type "cat > f <<\'EOF\'"\nEnter\nType \'x = "1"\'\nEnter\nType "EOF"\nEnter\n'
    )
    assert videos.shown_commands(tape) == ["$ a", "$ cat > f <<'EOF'", 'x = "1"', "EOF"]


def test_shown_commands_hold_no_backslash() -> None:
    # The dist check reads a backslash between name characters as a Windows path.
    for name in NAMES:
        tape = (ROOT / videos.TAPES / f"{name}.tape").read_text(encoding="utf-8")
        assert "\\" not in "\n".join(videos.shown_commands(tape)), name


def test_pages_embed_their_video_and_list_its_commands(built) -> None:
    for key, name in PAGES.items():
        assert DOCS["pages"][key]["video"] == name
        folder = built.out / DOCS["pages"][key]["path"].strip("/")
        page = html.unescape((folder / "index.html").read_text(encoding="utf-8"))
        twin = (folder / "index.md").read_text(encoding="utf-8")
        assert f'<source src="/video/{name}.mp4" type="video/mp4">' in page
        assert f'poster="/video/{name}.png"' in page
        tape = (ROOT / videos.TAPES / f"{name}.tape").read_text(encoding="utf-8")
        for line in videos.shown_commands(tape):
            assert line in page, line
            assert line in twin, line


def test_home_page_shows_the_own_policy_video() -> None:
    record = videos.load(ROOT, "own-policy")
    entry = next(v for v in HOME["videos"] if v["src"] == "/video/own-policy.mp4")
    assert entry["poster"] == "/video/own-policy.png"
    assert (entry["width"], entry["height"], entry["duration"]) == (
        record["width"],
        record["height"],
        record["duration"],
    )
