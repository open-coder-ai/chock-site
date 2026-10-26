"""R-4: the Git repositories section — tiers, API, commands, and the real engine on a temp repo."""

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from sitegen import repodata
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = yaml.safe_load((ROOT / "data" / "repos.yaml").read_text(encoding="utf-8"))
TIERS = DATA["tiers"]
CHOCK = [sys.executable, "-m", "chock"]
SCRUBBED = ("CLAUDECODE", "AI_AGENT")


def _site_json(built) -> dict:
    return json.loads((built.out / "data" / "site.json").read_text(encoding="utf-8"))


def _registry(catalog_path: Path) -> dict[str, dict]:
    rows = yaml.safe_load((catalog_path / "registry.yaml").read_text("utf-8"))
    return {row["id"]: row for row in rows["policies"]}


def test_section_is_a_row_in_tracks_yaml(built) -> None:
    track = next(t for t in built.site.tracks if t.id == "repos")
    assert (track.slug, track.title, track.status) == (
        "repos",
        "Git repositories",
        "available",
    )
    index = json.loads((built.out / "api" / "index.json").read_text(encoding="utf-8"))
    row = next(t for t in index["tracks"] if t["id"] == "repos")
    assert row == {
        "id": "repos",
        "title": "Git repositories",
        "home": "/repos/",
        "status": "available",
        "api": "/api/repos/",
    }


def test_every_policy_tier_matches_its_registry_enforces(built, catalog_path) -> None:
    registry = _registry(catalog_path)
    words = {t["key"]: t["word"] for t in TIERS}
    for policy in built.site.policies:
        enforces = registry[policy.id]["enforces"]
        expected = (
            "commit"
            if enforces == "enforced-at-commit"
            else "agent"
            if enforces.startswith("best-effort")
            else "advise"
            if enforces == "advisory"
            else None
        )
        assert policy.tier == expected, policy.id
        page = (built.out / "coding" / "policies" / policy.id / "index.html").read_text(
            encoding="utf-8"
        )
        tile = re.search(r'id="repo-tier".*?</div>', page, re.DOTALL).group(0)
        assert "In a git repo" in tile
        word = words[expected]
        assert f">{word[:1].upper() + word[1:]}<" in tile, policy.id
        twin = (built.out / "coding" / "policies" / policy.id / "index.md").read_text(
            encoding="utf-8"
        )
        assert f"In a git repo: {words[expected]}" in twin


def test_unknown_enforces_value_fails_the_build() -> None:
    with pytest.raises(PageError):
        repodata.tier_for("something-new", TIERS)
    assert repodata.tier_for("best-effort (anything)", TIERS) == "agent"


def test_home_counts_are_computed_from_the_registry(built, catalog_path) -> None:
    registry = _registry(catalog_path)
    visible = {p.id for p in built.site.policies}
    html = (built.out / "repos" / "index.html").read_text(encoding="utf-8")
    twin = (built.out / "repos" / "index.md").read_text(encoding="utf-8")
    for tier in TIERS:
        n = sum(
            1
            for pid in visible
            if (
                registry[pid]["enforces"] == tier.get("equals")
                or registry[pid]["enforces"].startswith(tier.get("starts_with", "\0"))
            )
        )
        card = re.search(rf'id="tier-{tier["key"]}".*?</div>', html, re.DOTALL).group(0)
        assert f'<p class="stat-num">{n}</p>' in card
        group = re.search(
            rf'data-tier="{tier["key"]}".*?</section>', html, re.DOTALL
        ).group(0)
        assert group.count("<li>") == n
        assert f'{tier["heading"]} <span class="repos-count">({n})</span></h3>' in group
        assert f"\n### {tier['heading']} ({n})\n" in twin
    for pid in visible:
        assert f'href="/coding/policies/{pid}/"' in html


def test_api_policies_file(built) -> None:
    doc = json.loads(
        (built.out / "api" / "repos" / "policies.json").read_text(encoding="utf-8")
    )
    assert set(doc) == {"schema_version", "catalog_ref", "policies"}
    assert doc["schema_version"] == 1
    assert doc["catalog_ref"] == built.site.catalog_ref
    assert [p["id"] for p in doc["policies"]] == sorted(
        p.id for p in built.site.policies
    )
    by_id = {p.id: p for p in built.site.policies}
    for row in doc["policies"]:
        assert row == {
            "id": row["id"],
            "version": by_id[row["id"]].version,
            "sha256": by_id[row["id"]].sha256,
            "tier": by_id[row["id"]].tier,
        }


def test_llms_sitemap_and_coding_api_additions(built) -> None:
    llms = (built.out / "llms.txt").read_text(encoding="utf-8")
    assert "## Git repositories" in llms
    assert "/api/repos/policies.json" in llms
    sitemap = (built.out / "sitemap.xml").read_text(encoding="utf-8")
    assert "/repos/</loc>" in sitemap
    assert "/repos/builder/</loc>" in sitemap
    catalog = json.loads(
        (built.out / "api" / "coding" / "catalog.json").read_text(encoding="utf-8")
    )
    assert "repos" not in catalog
    assert set(catalog["label_words"]) == {"coding"}
    assert not (built.out / "api" / "repos" / "catalog.json").exists()


def test_site_json_carries_the_repos_data_the_builder_reads(built) -> None:
    repos = _site_json(built)["repos"]
    assert [t["key"] for t in repos["tiers"]] == ["commit", "agent", "advise"]
    assert repos["tier_of"] == {p.id: p.tier for p in built.site.policies}
    assert [q["id"] for q in repos["quiz"]["questions"]] == [
        "host",
        "worries",
        "strictness",
    ]


def test_pinned_catalog_commit_is_on_the_catalogs_main(catalog_path) -> None:
    ref = (ROOT / ".catalog-ref").read_text(encoding="utf-8").strip()
    result = subprocess.run(
        [
            "git",
            "-C",
            str(catalog_path),
            "merge-base",
            "--is-ancestor",
            ref,
            "origin/main",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _commands(built, preset_id: str, ci: bool, catalog_path: Path) -> list[str]:
    preset = next(p for p in built.site.presets if p.id == preset_id)
    by_id = {p.id: p for p in built.site.policies}
    picks = [by_id[m] for m in preset.members]
    lines = repodata.command_lines(
        built.site.data["repos"]["commands"], picks, built.site.catalog_ref, ci
    )
    return [
        line + f" --from {catalog_path.resolve()}"
        if line.startswith("chock add ")
        else line
        for line in lines
    ]


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in SCRUBBED}
    return {k: v for k, v in env.items() if not k.startswith("CHOCK_")}


def _run(line: str, repo: Path, check: bool = True) -> subprocess.CompletedProcess:
    argv = line.split(" ")
    if argv[0] == "chock":
        argv = [*CHOCK, *argv[1:]]
    result = subprocess.run(
        argv, cwd=repo, env=_env(), capture_output=True, text=True, check=False
    )
    if check:
        assert result.returncode == 0, f"{line}\n{result.stdout}\n{result.stderr}"
    return result


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        env=_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_commands_install_git_hygiene_in_a_temp_repo(
    built, catalog_path, tmp_path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q", "-b", "work").returncode == 0
    lines = _commands(built, "git-hygiene", True, catalog_path)
    assert lines[0] == "chock init ."
    assert lines[-1].startswith("# Next: review `git status`")
    for line in lines[:-1]:
        _run(line, repo)
    preset = next(p for p in built.site.presets if p.id == "git-hygiene")
    api = {
        p["id"]: p
        for p in json.loads(
            (built.out / "api" / "repos" / "policies.json").read_text(encoding="utf-8")
        )["policies"]
    }
    lock = json.loads((repo / "chock.lock").read_text(encoding="utf-8"))
    locked = {pack["id"]: pack["sha256"] for pack in lock["packs"]}
    for pid in preset.members:
        assert (repo / ".agents" / "policies" / pid).is_dir(), pid
        assert locked[pid] == api[pid]["sha256"], pid


def test_a_commit_on_main_is_refused_by_the_added_gate(
    built, catalog_path, tmp_path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q", "-b", "main").returncode == 0
    by_id = {p.id: p for p in built.site.policies}
    lines = repodata.command_lines(
        built.site.data["repos"]["commands"],
        [by_id["protect-main-branch"]],
        built.site.catalog_ref,
        False,
    )
    for line in lines[:-1]:
        if line.startswith("chock add "):
            line += f" --from {catalog_path.resolve()}"
        _run(line, repo)
    # tc-001 of the policy's own suite: a file on main, then `git commit`.
    (repo / "app.py").write_text("print('work')\n", encoding="utf-8")
    assert _git(repo, "add", "app.py").returncode == 0
    refused = _git(repo, "commit", "-m", "work")
    assert refused.returncode != 0, refused.stdout
    assert "protected branch" in refused.stdout + refused.stderr
    assert _git(repo, "checkout", "-q", "-b", "feature/work").returncode == 0
    assert _git(repo, "commit", "-m", "work").returncode == 0


def test_command_lines_are_sorted_and_end_as_the_plan_says(built) -> None:
    commands = built.site.data["repos"]["commands"]
    by_id = {p.id: p for p in built.site.policies}
    picks = [by_id["scan-secrets"], by_id["block-no-verify"]]
    lines = repodata.command_lines(commands, picks, built.site.catalog_ref, False)
    assert lines[0] == "chock init ."
    assert [line.split(" ")[2] for line in lines[1:3]] == [
        "block-no-verify",
        "scan-secrets",
    ]
    assert lines[3] == "chock sync --repo ."
    assert lines[4] == commands["review"]
    assert "git add" not in "\n".join(lines)
    assert "`git status`" in lines[4] and "commit the files chock wrote" in lines[4]
    assert repodata.command_lines(commands, picks, "r", True)[3].endswith("--ci")
    assert repodata.script_text(commands, lines).startswith(
        "#!/bin/sh\nset -eu\nchock init .\n"
    )


def test_fill_is_one_pass() -> None:
    assert repodata.fill("{a}", {"a": "{b}", "b": "X"}) == "{b}"
    with pytest.raises(PageError):
        repodata.fill("{missing}", {})


# --- SITE-1: every value in a command line is one shell argument ---------------------------

# Values a catalog could carry: the review's injection, quotes, spaces, globs, unicode, empty.
TRICKY = [
    "safe;echo PWNED > pwned",
    "a'b",
    "it's",
    "two words",
    "$(id)",
    "`id`",
    "a&&b",
    "a|b",
    "*.py",
    "~user",
    "naïve",
    "",
    "plain-id-9",
    "abc123" * 10,
    "--ref",
    "{id}",
    "a\nb",
    "tab\there",
    "back\\slash",
    '"quoted"',
]


def test_shell_arg_is_shlex_quote() -> None:
    for value in TRICKY:
        assert repodata.shell_arg(value) == shlex.quote(value), value


def test_shell_line_quotes_every_value_in_one_pass() -> None:
    line = repodata.shell_line(
        "chock add {id} --ref {ref}", {"id": "safe;echo PWNED > pwned", "ref": "{id}"}
    )
    assert line == "chock add 'safe;echo PWNED > pwned' --ref '{id}'"
    assert shlex.split(line) == [
        "chock",
        "add",
        "safe;echo PWNED > pwned",
        "--ref",
        "{id}",
    ]
    with pytest.raises(PageError):
        repodata.shell_line("{missing}", {})


def test_command_lines_read_back_as_the_arguments_they_carry(built) -> None:
    commands = built.site.data["repos"]["commands"]
    policy = next(p for p in built.site.policies if p.id == "block-no-verify")
    hostile = replace(policy, id="safe;echo PWNED > pwned", sha256="a'b c")
    lines = repodata.command_lines(commands, [hostile], "r$(id)", False)
    assert shlex.split(lines[1]) == [
        "chock",
        "add",
        "safe;echo PWNED > pwned",
        "--ref",
        "r$(id)",
        "--verify-sha",
        "a'b c",
        "--skip-compile",
    ]
    assert "PWNED > pwned" not in shlex.join(shlex.split(lines[1])[:2])


def test_real_values_are_shown_bare(built) -> None:
    """Every pinned id, the catalog commit and every sha256 are shell-safe, so no line gains quotes."""
    for policy in built.site.policies:
        [line] = repodata.command_lines(
            built.site.data["repos"]["commands"],
            [policy],
            built.site.catalog_ref,
            False,
        )[1:2]
        assert "'" not in line, line
        assert line.split(" ")[2] == policy.id
