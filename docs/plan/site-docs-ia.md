# SITE-DOCS information architecture (DOCS-0)

Status: proposal for the orchestrator. No content pages are written by this item.
Plan: open-coder-ai/org-plan `plan/site-docs-full.md` at 0f06be4.

Every count below was measured during this survey. Where something was not measured, it says "unmeasured".

## 0. Pins and commits surveyed

| Repo | Commit read | Note |
|---|---|---|
| chock-site | 8433e34 (main) | `.framework-ref` = 39df00b, `.catalog-ref` = 563a6ce |
| chock | fd37691 (main) and 39df00b (the site's pin) | the site builds from the pin |
| agentseam | dd4f0a4 (main) | chock pins agentseam at bebbfa6 in its `pyproject.toml` (both commits) |
| chock-catalog | 5155a22 (main) | the site pins 563a6ce; that commit was not in the shallow clone, so only main was read |

**The engine pin must move before DOCS-1 and DOCS-2.** At 39df00b:
- `stop`, `resume` and `incident` do not exist;
- `docs/stop.md` does not exist.

The parser walk in section 3 measured 45 parser nodes at 39df00b and 48 at fd37691. The difference is exactly `stop`, `resume` and `incident`.

## 1. Inventory: what exists today

### 1.1 chock-site

- **Docs pages.** `data/docs.yaml` declares 12 pages in 4 nav groups:
  - Get started: overview, quickstart-plugin, quickstart-repo
  - Guides: agents, policies, configure, monitor, troubleshooting, bypasses
  - Reference: cli, release-notes
  - Architecture: architecture

  Generated child pages come on top: one per agent under `/docs/agents/<slug>/` and one per catalog policy under `/docs/policies/<id>/`. This means the `/docs/policies/` prefix is already taken by catalog policy ids, so no new page may live under it.
- **How a page is built.**
  - `sitegen/docs.py` turns each `pages.<key>` entry into a page by running:
    - its `blocks`: Python functions registered in `BLOCKS`, 23 today;
    - its `prose`: sections quoted from chock files.
  - `sitegen/engine.py` is the only module that imports chock and agentseam:
    - `cli_commands()` renders every command's `--help` from `chock/data/commands.json`;
    - `subcommand_help()` renders one subcommand's help.
  - The current `/docs/cli/` page puts every command on one page and does not walk subparsers.
- **Prose snapshot.**
  - `data/docs-source/` holds 14 files from chock at `engine_ref` 39df00b; `source.json` lists them.
  - `python -m sitegen.docsource --chock <checkout> [--check]` regenerates the snapshot or checks it.
  - The snapshot covers chock only. Nothing snapshots agentseam or catalog prose.
- **Drift checks in CI** (`.github/workflows/ci.yml`):
  - `ruff check`, `ruff format --check`;
  - `pytest` (unit), with the engine installed from `.framework-ref`;
  - `python -m sitegen.docsource --chock .chock-src --check`;
  - `python -m sitegen.architecture --check --fetch --clones .arch-src --repo chock-site=.`;
  - e2e Playwright;
  - local-test scripts on Linux and Windows;
  - `sitegen.distcheck`.

  The catalog is checked out at `.catalog-ref` into `.catalog` in two jobs.
- **Other generators:** `sitegen/architecture.py` builds diagrams from `data/architecture/*.json`; each node cites a file at a pinned commit. Today there are 2 diagrams: `whole-train`, `life-of-a-policy`.
- **Videos and assets.**
  - `static/video/` holds 2 promo films, listed in `data/home.yaml` `videos:` and rendered by `sitegen/home.py` (`_videos`, with `templates/home/videos.html`, `video-item.html` and `video-track.html` for captions):
    - `chock-promo-v9b.mp4`: 7,172,058 B, 1280x720, 1:02;
    - `chock-promo-v8-explainer.mp4`: 10,008,393 B, 1280x720, 1:57.
  - Later (VID-OFF, 2026-10-18): both promo films and their posters were taken off the site because their voice did not sync; the home page keeps the silent `own-policy` recording.
  - Docs pages have no video block today.
  - There are no terminal recordings on the site.
- **Author page:** `/author/` already fills chock policy templates in the browser. It uses `data/kinds/<kind>/**.tmpl`, which mirrors the engine; `data/kinds/engine-commit.txt` follows `.framework-ref`.

### 1.2 chock (engine)

- **docs/:** 27 top-level `.md` files.
  - Relevant to this plan: `cli-reference.md`, `architecture.md`, `concepts.md`, `enforcement-surfaces.md`, `stop.md` (main only), `decision-log.md`, `authoring-policies.md`, `custom-policies.md`, `evals.md`, `validation.md`, `script-backed-gates.md`, `registry-and-lockfile.md`, `getting-started.md`, `doctor.md`.
  - Subfolders: `adapters/` (15 vendor pages plus a README), `hooks/`, `policies/`, `runtime/`, `tools/`, `design/`.
- **CLI.**
  - `src/chock/cli.py` dispatches from `src/chock/data/commands.json`: 3 groups, everyday (15), authoring (10) and aliases (10), so 35 commands. `chock --help` lists everyday and authoring; aliases are hidden.
  - Each command builds its own `argparse` parser, except `compliance` and `check-matrix`, which parse by hand.
  - `docs/cli-reference.md` is hand-written; no check in chock ties it to the parsers.
- **Schemas:** `src/chock/validation/schemas/` holds `manifest.schema.json`, `eval.schema.json`, `selection.schema.json`, `guardrails.schema.json`, `subagent.schema.json` and the plugin schema.
- **Authoring skills:** `src/chock/packs/_skills/` contains `chock-init`, `policy-init`, `validate`, `eval` and `optimize`. `chock init` installs them; `policy-init` is a skill, not a CLI command.
- **Recording precedent:**
  - `docs/assets/demo.tape` is a VHS tape;
  - `.github/workflows/demo-gif.yml` renders it with `charmbracelet/vhs-action@f6d7db07…` (pinned by SHA): manual dispatch, `contents: read`, the output uploaded as an artifact;
  - `demo.gif` is 955,293 B.

  agentseam (182,025 B) and chock-catalog (1,202,499 B) carry the same pattern.

### 1.3 agentseam

- **README:** Install, How it works, Quick start (`run(handler)` with `Decision.deny`, then `agentseam install all …`), What it stops, Guardrails not guarantees, FAQ.
- **docs/:**
  - `design.md`, `design/dialect-families.md`, `bundles.md`, `coverage-gaps.md`, `vendor-examples.md`;
  - `quickstart.sh`, generated from the README block and checked by `quickstart.yml`;
  - per-vendor examples in `examples/generated/*.md`, checked by `examples/generate.py --check`.
- **Package:**
  - `agentseam` 0.3.5; stdlib only; `requires-python >=3.9`.
  - Its `__all__` exports `Event`, `Decision`, `run`, `handle`, `degrade`, event and outcome constants, `MATRIX`, `agents`, `adapted_agents`, `capability`, `can_block`, `can_rewrite`, `can_transform`, `enforcement_level`, and the submodules `adapters`, `bundler`, `instructions`, `packaging` and `permissions`.
- **CLI:** one console script, `agentseam`. Its subcommands are `agents`, `matrix`, `tier-table`, `doctor`, `probe {list,run,conformance}`, `install`, `instructions`, `permissions`, `packaging`, `uninstall`.

### 1.4 chock-catalog

- **README:** three adoption routes:
  - in-repo `chock init` / `chock add <id> --ref <sha> --verify-sha <sha256>` / `chock sync --repo . --ci`;
  - per-agent plugin repos (retired: plugins come from the chock.sh builder);
  - `chock install --selection`.
- **docs/:**
  - generated per-policy `docs/<id>/README.md` and `adoption.md`;
  - `policy-prose.yaml` (hand-written);
  - `how-it-works.md`, `coverage.md`, `demo-session.md`, `review-criteria/effects-honesty.md`.
- **Authoring:**
  - `CONTRIBUTING.md` is the guide.
  - Policies live in 3 trees (`tools/trees.py`): `base`, `compliance`, `agentic-security`.
  - A policy folder holds `manifest.yaml`, `plugin.json`, `skills/<id>/SKILL.md`, `evals/suite.yaml` and `implementations/*`.
  - `python tools/regen_all.py` regenerates:
    - lib copies;
    - plugin build;
    - sync;
    - `gen_registry.py` (registry.yaml, README rows, counts);
    - `gen_policy_docs.py`;
    - coverage matrix, quickstart, figures;
    - adoption transcripts.
- **CI gates:** `ci.yml` runs these jobs:
  - `dco`, `no-private-data`, `scope`;
  - `generated` (registry, installed, workflows, `chock sync --check`, `chock plugin build --check`, ruff);
  - `adopter` (`chock check`);
  - `tests-shard`, `tests-policy` (one entry per policy id), `tests-targeted`, `tests`, `durations`;
  - `staged-adopter`;
  - `policies` (aggregate).

  Docs and transcripts are checked nightly and at release, not per PR.

## 2. Proposed docs tree (nav)

New groups are added and existing pages keep their paths; the only change to an existing page is to `/docs/cli/` (see the Reference group). "G" means generated and "H" means hand-written wording in `data/docs.yaml`; each page lists its source of truth.

```
Get started                      (unchanged)
  Overview                       /docs/
  Quickstart: plugin             /docs/quickstart/plugin/
  Quickstart: repo               /docs/quickstart/repo/
Guides                           (unchanged)
  Agents, Policies, Configure, Monitor, Troubleshooting, What Chock doesn't stop
Write policies                   (new: DOCS-5)
  Your own policy                /docs/write/own-policy/
  On the fly                     /docs/write/on-the-fly/
  Manifest reference             /docs/write/manifest/
  Evals reference                /docs/write/evals/
Catalog                          (new: DOCS-4)
  Adopt catalog policies         /docs/catalog/adopt/
  Add a policy to the catalog    /docs/catalog/contribute/
How Chock works                  (new: DOCS-2; takes over the "Architecture" group label)
  How it works                   /docs/how-it-works/
  Enforcement surfaces           /docs/how-it-works/surfaces/
  Stop and resume                /docs/how-it-works/stop/
  Architecture                   /docs/architecture/   (existing; gains a lifecycle diagram)
agentseam                        (new: DOCS-3)
  What agentseam is              /docs/agentseam/
  Use it without Chock           /docs/agentseam/direct/
  Python API                     /docs/agentseam/api/
  agentseam CLI                  /docs/agentseam/cli/
Reference
  CLI reference (index)          /docs/cli/            (existing page becomes an index)
    one page per command         /docs/cli/<command>/
    one page per subcommand      /docs/cli/<command>/<sub>/
  Release notes                  /docs/release-notes/  (unchanged)
```

Agents and adapters are not duplicated: `/docs/agents/` already renders agentseam's matrix, and the agentseam pages link to it.

## 3. Every page: source of truth, generated or hand-written

### DOCS-1 CLI reference (generated)

- **Parser nodes measured.** Command used: argparse introspection, which captures each command's parser and walks its `_SubParsersAction`s.

  | Engine | Nodes (everyday / authoring / aliases) | Options in total |
  |---|---|---|
  | fd37691 | 48 (19 / 18 / 11) | 150 |
  | 39df00b (pin) | 45 (16 / 18 / 11) | 136 |

  Two more commands are not argparse: `compliance` and `check-matrix`.
- **Pages: 50 at fd37691.**
  - 35 command pages, with aliases included and marked "alias of: …" from `commands.json`;
  - 15 subcommand pages: `witness export`, `bundle on/off/status`, `registry init/scan/list/get/resolve`, `gateway run`, `review emit/verify/require`, `verify init/verify`;
  - the existing `/docs/cli/` becomes the index.
- **Source per page:**
  - syntax, options, defaults, choices and help come from the argparse parser at `.framework-ref`;
  - the group and the one-line summary come from `chock/data/commands.json`;
  - `compliance` and `check-matrix` get their raw `--help` text only.
- **Exit codes:** chock documents none (see Gaps). The page states only:
  - argparse's usage error, exit 2;
  - each recorded example's real exit code.
- **Examples:** real runs, recorded by a new `python -m sitegen.cliexamples --record`. It runs scripted commands in a throwaway repo at a fixed path and writes `data/cli-examples/<command>.json`, which holds the command, normalised output and exit code.

### DOCS-2 How Chock works (mixed)

| Page | Generated part | Hand-written part |
|---|---|---|
| How it works | Lifecycle diagram (author → compile → sync → hook → verdict → log) as `data/architecture/lifecycle.json`; each node cites a chock file and passes `architecture --check` | Framing in docs.yaml; prose quoted from chock `docs/architecture.md` (The three stages, Two-tier model) and `docs/concepts.md` |
| Enforcement surfaces | Per-surface route table from engine data (`surface_routes`, `engine.matrix_row`) | Prose quoted from `docs/enforcement-surfaces.md` (The nine surfaces, What happens when the guard cannot decide) |
| Stop and resume | `chock stop/resume --help` via `subcommand_help`-style capture | Prose quoted from `docs/stop.md` (needs the pin bump) |
| Architecture (existing) | One more diagram | none |

### DOCS-3 agentseam (mixed)

| Page | Source | Generated or hand-written |
|---|---|---|
| What agentseam is | agentseam README (How it works, Guardrails not guarantees) and `docs/design.md`, quoted from a new snapshot at the commit chock pins (bebbfa6) | Hand-written framing and quoted prose |
| Use it without Chock | The README Quick start, which is already drift-checked in agentseam as `docs/quickstart.sh`; the output comes from a real run | Hand-written steps, recorded output |
| Python API | `agentseam.__all__`, introspected at build: `inspect.signature` plus the first docstring line | Generated |
| agentseam CLI | agentseam's argparse parser (`agentseam.cli`), walked like DOCS-1 | Generated |

### DOCS-4 Catalog (mixed)

| Page | Source | Generated or hand-written |
|---|---|---|
| Adopt catalog policies | catalog README Install and Quick start (quoted); `chock add/sync --help`; a recorded run of `chock add protect-main-branch --ref <.catalog-ref>` | Hand-written steps; outputs recorded |
| Add a policy to the catalog | `CONTRIBUTING.md` (quoted); trees from `tools/trees.py`; the CI gate table built at build time from `.catalog/.github/workflows/ci.yml` (job ids and `run:` lines at `.catalog-ref`); `regen_all.py` steps from its source | Hand-written step list; gate table and tree list generated |

### DOCS-5 Your own policy (mixed)

| Page | Source | Generated or hand-written |
|---|---|---|
| Your own policy | Recorded run (section 5, video 1): `chock init .`, `chock new policy <id> --kind content_regex`, `chock check --repo .`, `chock sync --repo .`, a refused commit, a clean commit. Kinds from `chock new --help` choices | Hand-written steps; all output recorded |
| On the fly | The `policy-init` skill (`src/chock/packs/_skills/policy-init/SKILL.md`), quoted; the site's `/author/` page; `chock new --kind` | Hand-written |
| Manifest reference | `manifest.schema.json` at `.framework-ref`: field, type, required, enum, description | Generated |
| Evals reference | `eval.schema.json` (generated table) plus `docs/evals.md` (quoted: Anatomy of a suite, What `expect` can say) | Mixed |

### Page count

**New pages: 63.**
- **Generated: 54.**
  - 50 CLI pages;
  - agentseam API and agentseam CLI;
  - Manifest reference and Evals reference.
- **Hand-written: 9,** with quoted or recorded content:
  - How it works, Enforcement surfaces, Stop and resume;
  - What agentseam is, Use it without Chock;
  - Adopt, Add to catalog;
  - Your own policy, On the fly.

**Changed pages:**
- the existing `/docs/cli/` becomes an index;
- `/docs/architecture/` gains a diagram;
- the home page gains a video.

## 4. Drift checks that keep generated pages honest

1. **Existing, kept:**
   - `sitegen.docsource --check`, now also covering the new chock prose (architecture.md, stop.md, evals.md, authoring-policies.md);
   - `sitegen.architecture --check`, covering the new lifecycle diagram.
2. **CLI coverage test:**
   - every parser node in the installed engine has a page and a nav entry, and every page maps to a node;
   - a new command or subcommand fails the build until it is listed. This follows the existing `cli_groups` check in `_cli`.
3. **`sitegen.cliexamples --check`:**
   - re-runs each recorded example against the installed engine in a fresh repo at the fixed path and diffs the normalised output and exit code;
   - runs in CI next to `docsource --check`;
   - examples that need the network (`chock add`) use the pinned `--ref` and run in the CI job that already has network access for the catalog checkout.
4. **agentseam snapshot check:**
   - `python -m sitegen.agentseamdoc --agentseam <checkout> --check` diffs the quoted README and docs sections at the commit chock pins;
   - a unit test fails when a name in `agentseam.__all__` has no API entry.
5. **Catalog snapshot check:** `python -m sitegen.catalogdoc --catalog .catalog --check` diffs the quoted CONTRIBUTING and README sections at `.catalog-ref`.
6. **Schema pages:** the manifest and eval references are built from the installed engine's schema files, so they cannot drift. A test fails if a schema property has no row.
7. **Videos:**
   - a test checks each `videos/<name>.tape`:
     - it has its `.mp4` and poster under `static/video/`;
     - each file is at or under the size cap (section 5);
     - its sidecar `static/video/<name>.json` records the sha256 of the tape it was rendered from, and that hash still matches the tape.
   - The sidecar also records the engine commit the recording was made with, and the page prints it. A tape changed without re-rendering fails the build.

## 5. Videos

All three are silent VHS terminal recordings of real commands; no audio, so no audio licence is needed. Each tape sits in chock-site under `videos/<name>.tape`, and the page shows the command list, taken from the tape itself.

**Recording.**
- New workflow `.github/workflows/videos.yml`:
  - `workflow_dispatch` only, `contents: read`;
  - installs chock at `.framework-ref`;
  - renders with `charmbracelet/vhs-action`, pinned to the same SHA chock uses;
  - uploads the artifact.
- A worker reviews the artifact and commits it, as chock's `demo-gif.yml` does. VHS can also be run locally (`vhs videos/<name>.tape`).
- Recordings run outside any agent session. During this survey's dry runs, the agent session's environment made the gate print an extra "treated as an agent's commit" line; the CI render will not have that variable set.

**Format.**
- MP4 (H.264) via VHS `Output static/video/<name>.mp4`;
- a PNG poster via VHS `Screenshot`;
- 1200x640, 16 px font, as chock's tape;
- size cap: 3,000,000 B per MP4, enforced by the test in section 4.7.

Actual sizes and durations are unmeasured until recorded.

**Hidden setup in every tape:** a throwaway repo at the fixed path `/work/demo` on an unborn `main`, with git user `Demo` <demo@example.com>. It is created with `Hide` … `Show`, as chock's tape does, so the printed paths are stable.

### Video 1: `own-policy`, create a policy in your own repo (DOCS-5 page and home page)

Dry run: done at chock fd37691; each line below ran with the exit code shown.

```
chock init .                                          # rc 0
chock new policy block-marker --kind content_regex    # rc 0, creates .agents/policies/my-block-marker/
cat .agents/policies/my-block-marker/manifest.yaml
chock check --repo .                                  # rc 1 at fd37691, though it prints "[PASS] All checks passed." (see Gaps)
git add -A && git commit -qm "scaffold"               # rc 0 (before sync, so the new gate is not armed yet)
chock sync --repo .                                   # rc 0
git add -A && git commit -qm "sync"                   # rc 0
echo 'x = 1  # DO NOT COMMIT' > notes.py && git add notes.py
git commit -m "add notes"                             # rc 1: "this change adds a line marked DO NOT COMMIT"
echo 'x = 1' > notes.py && git add notes.py
git commit -m "add notes"                             # rc 0
```

The order (commit the scaffold before `chock sync`) is required at fd37691; see Gaps.

### Video 2: `adopt-policy`, add a catalog policy to your own repo (DOCS-4 adopt page)

Dry run: done at chock fd37691 against catalog main 5155a22. The tape pins the catalog with `--ref <.catalog-ref> --verify-sha <hash>`, filled in when the tape is written from the values `chock add` printed.

```
chock init .                                          # rc 0
chock add protect-main-branch --ref <.catalog-ref> --verify-sha <sha256>
chock sync --repo .                                   # prints "enforced-at-commit" for claude, copilot, gemini
git add -A && git commit -qm "adopt"                  # rc 1: "Direct commits/pushes to a protected branch (main|master) are blocked."
git switch -c feature
git commit -qm "adopt"                                # rc 0
```

A secret-scanning demo was considered and rejected, because its fixture line would need an allowlist pragma, which is owner-only. Splitting the key to dodge the scanner is forbidden.

### Video 3: `catalog-policy`, add a new policy to the catalog (DOCS-4 contribute page)

Dry run: not done. DOCS-6 must dry-run it at `.catalog-ref` first. The commands come from catalog `CONTRIBUTING.md` and `tools/regen_all.py`:

```
git clone https://github.com/open-coder-ai/chock-catalog /work/catalog && cd /work/catalog
chock new policy block-marker --kind content_regex --repo .
python tools/regen_all.py --fast
chock check --repo .
git status --short
```

Open questions for the dry run:
- which tree `chock new` writes to inside the catalog;
- whether `regen_all.py --fast` runs without the full dev requirements. These need to be answered in the dry run.

**Home page:** video 1 goes into `data/home.yaml` `videos:`, using the existing `sitegen/home.py` code.

## 6. Files each item touches (for ordering)

Shared files are marked **[S]**. A shared hot file (CI) is marked **[HOT]**.

| Item | Touches |
|---|---|
| DOCS-1 | `data/docs.yaml` [S]; `sitegen/docs.py` [S] (per-command page emit plus one `BLOCKS` line); `sitegen/engine.py` [S] (parser walk); new `sitegen/cliexamples.py`; new `data/cli-examples/**`; new `templates/docs/cli-*.html`; new `tests/test_docs_cli.py`; `.github/workflows/ci.yml` [HOT] (cliexamples --check); `.framework-ref`, `data/docs-source/**`, `data/kinds/engine-commit.txt` [S] (pin bump) |
| DOCS-2 | `data/docs.yaml` [S]; `sitegen/docs.py` [S] (blocks `surfaces`, `stop_help`); new `data/architecture/lifecycle.json`; `data/architecture/texts.yaml` [S]; `data/docs-source/**` [S] (regenerated: architecture.md, stop.md); new `tests/test_docs_how.py` |
| DOCS-3 | `data/docs.yaml` [S]; `sitegen/docs.py` [S] (one `BLOCKS` line each for `agentseam_api` and `agentseam_cli`); `sitegen/engine.py` [S] (the only agentseam importer); new `sitegen/agentseamdoc.py`; new `data/agentseam-source/**`; `.github/workflows/ci.yml` [HOT] (snapshot check); new `tests/test_docs_agentseam.py` |
| DOCS-4 | `data/docs.yaml` [S]; `sitegen/docs.py` [S]; new `sitegen/catalogdoc.py`; new `data/catalog-source/**`; `.github/workflows/ci.yml` [HOT]; new `tests/test_docs_catalog.py`; `data/cli-examples/**` [S] (adopt run, using the DOCS-1 recorder) |
| DOCS-5 | `data/docs.yaml` [S]; `sitegen/docs.py` [S] (blocks `schema_table`, `recorded`); `sitegen/engine.py` [S] (schema read); `data/cli-examples/**` [S]; `data/docs-source/**` [S] (evals.md, authoring-policies.md); new `tests/test_docs_write.py` |
| DOCS-6 | new `videos/*.tape`; new `static/video/{own-policy,adopt-policy,catalog-policy}.{mp4,png,json}`; `sitegen/docs.py` [S] (a `video` block); new `templates/docs/video.html`; `data/docs.yaml` [S] (video blocks on 3 pages); `data/home.yaml` [S]; new `.github/workflows/videos.yml` [HOT]; new `tests/test_videos.py` |

Every item touches `data/docs.yaml` and `sitegen/docs.py`. Those are append-only edits (new page entries, one `BLOCKS` line), but under the parallel rule they still overlap.

**Proposed order:**
1. **DOCS-1 alone.** It moves `.framework-ref`, which DOCS-2 and DOCS-5 need. It also adds the recorder that DOCS-4 and DOCS-5 use and the first `ci.yml` step.
2. **DOCS-2, DOCS-3 and DOCS-4 in parallel,** if the orchestrator accepts the append-only overlap in `docs.yaml` and `docs.py`, the way catalog generated files are allowed (each worker merges `main` with a merge commit before its merge).
   - Otherwise, run them serially: DOCS-2, then DOCS-3, then DOCS-4.
   - DOCS-3 and DOCS-4 both edit `ci.yml` [HOT], so those two serialize either way.
3. **DOCS-5,** after DOCS-1, since it needs the recorder and the pin.
4. **DOCS-6,** after DOCS-4 and DOCS-5, as the plan says.

## 7. Known gaps (where a product repo lacks docs to source from)

**chock**
- No exit codes are documented for any command.
- `docs/cli-reference.md` is hand-written and is not checked against the parsers.
- `chock new policy` prints `Next:  python -m chock check .`. When run as `chock check .`, it exits 2 with "unrecognized arguments: ." (measured at fd37691). The working form is `chock check --repo .`.
- `chock check --repo .` in a freshly scaffolded repo prints "[PASS] All checks passed." but exits 1 (measured at fd37691). The reason is undocumented.
- The `content_regex` template's message text matches its own pattern in `.agents/policies/INDEX.md`. As a result, the first commit after `chock sync` is refused unless the scaffold was committed before sync (measured at fd37691).
- `compliance` and `check-matrix` have no argparse parser, so only their raw help text is available.
- The site's pin (39df00b) lacks `stop`, `resume`, `incident` and `docs/stop.md`.

**agentseam**
- No API reference: nothing documents `Event` fields, `Decision` constructors, `handle(raw, handler, agent)`, `degrade` or `run(..., exit=)`.
- No standalone install page, and nothing says whether 0.3.5 is on PyPI (unmeasured).
- No docs for `tier_table`, which is not exported, or for library use of `install`, `instructions` and `permissions`.

**chock-catalog**
- README says to scaffold with `chock new policy <id>`; CONTRIBUTING says to use the `policy-init` skill.
- CONTRIBUTING's layout section leaves out:
  - `plugin.json`;
  - `skills/<id>/SKILL.md`;
  - `.py` guards;
  - the `compliance` and `agentic-security` trees.
- CONTRIBUTING says a PR without its adoption transcript fails CI, but `ci.yml` does not run `gen_adoption_transcript.py`; only the nightly and release workflows do.
- Nothing documents:
  - the manifest field by field (chock's schema covers this);
  - choosing a tree;
  - the `docs/policy-prose.yaml` entry;
  - the `tests-policy` registration;
  - `lib/` copies.
- The site pin 563a6ce was not readable in the shallow clone, so the catalog facts above are from main 5155a22.

**Videos**
- No recording exists yet. The catalog video's commands have not been dry-run.
