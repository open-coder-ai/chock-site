## Everyday

### `init` — onboard a repository

```bash
chock init [repo] [--agents claude cursor copilot] [--agent-agnostic] [--skip-hooks] [--force]
```

Scaffolds a consumer repo — **wiring only, no policies**: creates `.chock/` (config, coverage, vendored runtime), `chock.lock` at the repo root and an empty `.agents/policies/`, writes agent wrapper files, installs the
git hook dispatchers, and runs a validation self-check. Add policies afterwards with
`chock add` (or by copying a policy folder in and running `chock sync`). **Idempotent** —
safe to re-run; it overwrites derived files but never your own policies.

- `--agents` — space-separated target agents (default: `claude copilot gemini`). A wrapper file is written only for an agent that cannot read `AGENTS.md` natively — of those three, Claude Code alone.
- `--agent-agnostic` — generate wrappers for all supported agents.
- `--skip-hooks` — skip git hook installation.
- `--force` — overwrite scaffolded files that have local edits (destructive).

A bare re-run keeps the `supported_agents` already recorded in `.chock/config.yaml` and
preserves any scaffolded file you have edited (reported as `[KEPT]`); `--force` overwrites them.

### `add` — install a policy or skill from a catalog

```bash
chock add <id> [--repo .] [--from URL_OR_PATH] [--ref REF]
               [--verify-sha SHA256] [--force] [--skip-compile]
```

Fetches one artifact from a catalog, copies it into `.agents/policies/<id>` (or
`.agents/skills/<id>`), and compiles it. `--from` defaults to the public catalog and also accepts a
local path, which is what CI and offline installs use.

| Flag | What it does |
| :--- | :--- |
| `--ref` | Pin the fetch to a branch, tag or commit id (a local path too). Without it, `add` resolves the catalog's **default branch**. |
| `--verify-sha` | Refuse to install unless the fetched artifact hashes to this value. Checked *before* anything is written. |
| `--force` | Replace an artifact that is already installed. Refused by default — installed content is yours. |
| `--skip-compile` | Copy only; run `chock sync` yourself afterwards. |

`add` prints the resolved commit and the content hash, and records `source`, `source_ref` and
`source_commit` in `chock.lock`.

> **A catalog policy can contain guard scripts that run on every commit.** `add` installs executable
> content over `git clone`, with no signature verification — see the catalog trust model in
> [SECURITY.md](../SECURITY.md). Pin with `--ref` and check the hash with `--verify-sha` when the
> catalog is not one you control.

### `remove` — uninstall a policy

```bash
chock remove <policy-id> [--repo .]
```

The inverse of `add`: deletes `.agents/policies/<id>` and runs `sync` so the compiled tree,
hooks, index, registry, and lockfile all stop describing it. Refuses (exit 2) for policies
marked `mandatory: true`. To keep a policy installed but inert, use `disable` instead.

### `sync` — make the repo match its policies

```bash
chock sync [--repo .] [--agents claude cursor copilot] [--skip-hooks] [--check]
chock sync --ci       # also install the GitHub Actions CI-gate workflow
chock sync --skills   # also install the bundled authoring skills
```

The one "make it so" verb (`uv sync` semantics): recompiles every enabled policy from `.chock/config.yaml` into
`.chock/compiled/`, reinstalls the git-hook dispatchers, policy wrappers and the in-agent hooks of the agents
`supported_agents` names, uninstalls chock's entries from any vendor it no longer names (deleting a config file that
held only chock's) before pruning that vendor's runtime, regenerates `INDEX.md` and the `AGENTS.md` pointer, refreshes
the registry, and rewrites `chock.lock`. Run after editing a policy, toggling config, or bumping the engine version. A
failed recompile never removes the existing compiled tree — staged and swapped in only on success — and a
lockfile-write failure fails the command. An adopter-edited dispatcher is backed up to `<event>.chock-backup` before
being regenerated; custom steps belong in `<event>.d/`.

- `--check` — write nothing; exit non-zero listing every compiled artifact that no longer matches its manifest. The CI drift gate.
- `--ci` — additionally write the GitHub Actions workflow running every compiled `ci-gate` on pull requests. Idempotent; refuses to overwrite a workflow it did not write. Until this runs, `ci-gate` output is compiled but not enforced.
- `--skills` — additionally refresh the bundled authoring skills in `.agents/skills/`.
- `--skip-hooks` — compile and refresh bookkeeping without touching `.git/hooks`.

### `check` — is this repo sound?

```bash
chock check [--repo .] [--only validate,verify,evals,matrix,mechanisms,index,conflicts,baseline] [--mode MODE] [--event EVENT] [--base REF]
```

Runs every truth check, read-only — `check` never regenerates what it measures (that is `sync`'s job):

| Target | What it proves |
| :--- | :--- |
| `validate` | Artifacts conform to the spec: schemas, budgets, security baseline, determinism, drift. |
| `verify` | Installed packs match `chock.lock` — both source and compiled-artifact hashes. |
| `evals` | Every policy's eval suite passes under deterministic replay. |
| `matrix` | Spec invariants are traceable in the enforcement matrix. Framework-repo homework: auto-skipped (with a note) in repos that have no `spec/enforcement-matrix.md`. |
| `mechanisms` | Every enforcement-matrix row naming a `` `function()` `` names a real, invoked, severity-capable one — presence in `matrix` is not the same as being real. Same auto-skip as `matrix`. |
| `index` | `INDEX.md` and the `AGENTS.md` pointer are fresh. |
| `conflicts` | No two installed policies contradict each other — one allowing what another refuses. |
| `baseline` | The policy set is no weaker than `--base REF`'s: nothing newly in `policies.disabled`, nothing downgraded to advisory, no surfaces dropped. Bare `chock check` skips it with a note; CI runs it against the pull request's base branch. |

- `--only` — comma-separated subset, e.g. `--only validate,verify`.
- `--mode` — frontier validation profile (e.g. `frontier-claude`), passed to `validate`.
- `--event` — hook event context (e.g. `commit`), passed to `validate`; softens pre-existing-drift findings at commit time.
(`chock eval export --format context-report --out DIR [POLICY_ID ...]` exports a policy's tier-3
cases as a context-report run/v0.1 directory — its own command, not a `check` flag. See
[Evals](evals.md#exporting-tier-3-cases-to-context-report).)

### `status` — what is installed, and what happened

```bash
chock status [--repo .] [--only policies,registry,log]
```

Read-only. Default prints the policy table: every installed policy, its resolved state
(`enabled`, `overridden`, `disabled`), coverage level, and whether it is `mandatory`.
`--only registry` lists the artifact registry; `--only log` reports recorded gate outcomes on
both routes, including policies that never fired ([Decision log](decision-log.md): levels, filters); `--summary` adds rates, latency vs timeout, faults and heartbeats; `--verify-log` walks each log's hash chain and exits 1 at its first break ([Decision log](decision-log.md#hash-chain)); `chock witness export` writes one client's redacted log for its agentseam issue ([Decision log](decision-log.md#summary)). `chock incident --since <time> [--until <time>] [--format text|md|json] [--share]` prints an ordered, redacted timeline of the log, chain breaks inline ([Decision log](decision-log.md#incident-timeline)). `chock doctor [--client X]` checks each client's hooks are in place, current and running ([Doctor](doctor.md)). A stop in force (`chock stop [--agent X] [--reason R]`, `chock resume`) leads the output; so does the machine-wide one, `chock stop --everywhere`, which every Chock hook on the machine reads, in every repository and session, until a person at a terminal runs `chock resume --everywhere` and types `everywhere` (it lifts no per-repository stop) ([Stop](stop.md#everywhere-one-stop-for-the-machine)).

### `enable` / `disable` — policy toggles

```bash
chock enable  <policy-id> [--repo .]
chock disable <policy-id> [--repo .]
```

`disable` adds a policy to `policies.disabled` in `.chock/config.yaml`, recompiles the
enabled policies, and removes its git-hook wiring. `enable` does the reverse. Both are
config overlays — the policy files stay untouched (unlike `remove`). `disable` refuses
with exit 2 if the policy is `mandatory: true`. Both reject unknown ids.

---

## Typical workflows

**Onboard and prove enforcement**

```bash
chock init .
chock add protect-main-branch
git checkout main && git commit -m x   # blocked by protect-main-branch
```

**Author, validate, compile a new guard**

```bash
chock new policy block-console-log
# …edit manifest.yaml (hook.gate) + evals…
chock check
chock compile block-console-log
```

**CI pipeline (see `.github/workflows/ci.yml`)**

```bash
ruff check . && ruff format --check .
chock check
chock sync --repo . --check
chock registry scan   # then diff to detect drift
pytest -q
```
