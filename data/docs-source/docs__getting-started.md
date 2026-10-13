## Prerequisites

- **Python 3.11+** (for pip/pipx/source installs)
- **git**
- A shell with **bash** available for git hooks (Linux/macOS have it; on Windows, Git for Windows provides it)

## 2. Onboard a repository

From inside the repo you want to protect:

```bash
cd /path/to/your/project
chock init .
```

`init` is fully deterministic — no AI agent required. It:

- creates `.chock/` (config, `coverage.json`, `dependency-allowlist.txt`, the vendored
runtime under `bin/` and compiled output under `compiled/`) plus `chock.lock` at the repo root and an empty `.agents/policies/`,
- writes `AGENTS.md`, a `.gitattributes` pinning generated scripts to LF, `.gitignore` rules that
  ignore the per-machine gate log (`.chock/log/`) and keep the gate runtime and compiled gates
  (`.chock/bin/`, `.chock/compiled/`) tracked even where a global `bin/` rule would ignore them, a wrapper file for each agent that does **not** read
  `AGENTS.md` natively (root `CLAUDE.md` for Claude Code, and by default nothing else — Cursor,
  Copilot, Codex, Gemini, VS Code and Windsurf all read `AGENTS.md` directly), and the
  guardrail pairs `.agents/policies/{AGENTS.md,CLAUDE.md}` and `.agents/skills/{AGENTS.md,CLAUDE.md}`,
- installs the four authoring skills (`policy-init`, `validate`, `eval`, `optimize`) into
  `.agents/skills/`, and
- installs the git hook dispatchers.

It installs **no policies**, and tells you so — a freshly initialised repo enforces nothing yet.
Policies are content, not framework, and you choose which to adopt.

The default target set is `claude copilot gemini`. Of those, only Claude Code gets a wrapper
file: Copilot and Gemini read `AGENTS.md` natively, so naming them changes nothing on disk.
Pass `--agents` to change the set:

```bash
chock init . --agents claude cursor copilot codex gemini aider
```

Re-running `init` is safe: files you have edited are kept, and it says which it left alone. Use
`--force` when you genuinely want them overwritten.

## 3. Install a policy

```bash
chock add protect-main-branch
chock sync --repo .
```

`add` fetches from the base catalog
([`chock-catalog`](https://github.com/open-coder-ai/chock-catalog)), copies the
artifact in, and compiles it. Point it elsewhere with `--from <url-or-path>`; transport is
`git clone`, so a private catalog works with the credentials you already have.

Once installed, the policy is **yours** — edit it freely. `add` refuses to replace an
installed artifact unless you pass `--force`.

## 4. See enforcement in action

`protect-main-branch` blocks direct commits to protected branches:

```bash
git checkout main
echo "oops" > hotfix.txt && git add hotfix.txt
git commit -m "straight to main"
# ❌ Direct commits/pushes to a protected branch (main|master) are blocked.
#    Create a feature branch and open a pull request.
#      - main

git checkout -b feature/x
git commit -m "on a feature branch"   # ✅ allowed
```

This policy's gate declares `on: [commit, push]`, so it compiles to the git hook, the CI gate
and the ambient rule — not to a pre-tool hook. A policy whose gate also declares `tool_use`
(`scan-secrets`, for one) additionally reaches your agent's native controls, stopping it
*before* it writes, rather than only at commit time.

## 6. Keep it reproducible

`init` writes a `chock.lock` with an empty packs list; `sync` and `add` populate it, pinning
each installed pack by content hash. Verify a repo
hasn't drifted at any time:

```bash
chock check --only verify        # "all packs match lockfile"
```
