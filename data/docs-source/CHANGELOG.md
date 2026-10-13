## Unreleased

- Entries for unreleased changes now live in `changelog.d/` (one file per change); see
  `changelog.d/README.md`.
- **`egress_allowlist` is a hook kind the manifest schema accepts.** The engine validates,
  compiles and evaluates it at the mcp-gateway, but `manifest.hook.json` left it out of the
  `hook.gate.kind` enum, so `chock validate` refused every manifest using it (a schema error,
  exit 1). The enum now lists it; the gateway-only rule (no `commit`/`push` in `on`) and its
  closed `params` still apply, and `outside_repo` is now refused on any kind that never judges a
  write (it was accepted and ignored). Only the MCP gateway evaluates the kind, so a policy using
  it earns `advisory` coverage per agent. A test pins the enum to the engine's kinds and param
  schemas, and `spec/` prose quoting a `` `kind: <value>` `` must name one the schema accepts.
- **Security: `chock add --ref` resolves a 40-hex pin as a commit object only.** A pin that looked
  like a SHA was first tried as a branch or tag name (`git clone --branch`), so anyone able to create
  a branch or tag with that name in the catalog remote could substitute different content under the
  pin; `--verify-sha` is a content hash and did not catch it. A 40-hex ref (upper case is lowered) is
  now fetched by id into an empty repo, must resolve to a commit, and `HEAD` must equal it before any
  catalog file is read; otherwise `add` exits 2 and installs nothing. A remote that will not serve
  the commit by id is refused rather than retried as a branch; over git protocol v2 a remote may serve
  an unreachable commit, and whatever is served must still be exactly the pinned commit. A short hex
  ref (7-39 characters) is refused as ambiguous: pin the full SHA. A ref starting with `-` or outside
  git's ref rules is refused, and `--` ends git's options. Exit 2 applies to SHA pins and invalid
  refs; a branch or tag that cannot be fetched still exits 1. Branch and tag refs still work, record
  the resolved commit, and print a warning that they can move.
- **Security: `chock add` runs its git commands isolated from the caller's environment.** An inherited
  `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` or similar variable made the temp-repo commands act on
  the caller's own repo. Fetch and clone now drop the variables that redirect git (repository,
  object-store, config-injection and exec/template paths), bind every command to the temp repo with
  `--git-dir`/`--work-tree`, create it with an empty template, and run with `core.hooksPath=/dev/null`
  and `core.fsmonitor=false`, so no hook or fsmonitor from a template or user config runs.
  `GIT_ALLOW_PROTOCOL` is set to `https:ssh:file:git` (no `ext::`/`fd::` helpers), system config is
  ignored, and each git call has a timeout (600s fetch/clone, 60s local) that fails cleanly with
  nothing installed. The user's global config, ssh settings and proxy/CA variables are kept.
- **`chock add` and `chock sync` write one spelling of a local pack to `chock.lock`.** A pack added
  from the repo itself was recorded as `"source": "."` with `"source_commit": null`, and the next
  `sync` rewrote it as `"source": "local"` with no `source_commit`, so a clean tree kept producing a
  lockfile diff. A local pack is now always `"source": "local"` with no `source_commit`; an old
  lockfile converges on its next `sync` and is then stable. Catalog provenance (`source`,
  `source_commit`, `source_ref`) is kept across `sync` while the pack still hashes to what was
  fetched; an edited pack is local again.
- **`chock check --event ci --base <ref> --format sarif` writes the ci gates' findings as SARIF 2.1.0.**
  One `run` (driver `chock`, version, `informationUri`) with a rule per policy rule of each gated
  policy's shipped setup contract (`<policy>/<rule>`, title, constraint, first https reference as
  `helpUri`, CWE ids as `external/cwe/cwe-NNN` tags) and a result per finding: `block` is `error`,
  `ask` `warning`, `warn` `note`; repo-relative POSIX `artifactLocation.uri` (a path outside the repo
  falls back to the policy's manifest), `startLine` when known, a `partialFingerprints` entry that
  ignores the line, text with no control or invisible character. A finding the rollout level holds
  keeps the level it would have and carries `rolloutHeld: true`. `--output <file>` writes it to a file;
  the exit code is the gates' own (1 on a block, 2 when a gate cannot judge), never the format's.
  `chock sync --ci` installs a workflow that uploads it with a commit-pinned
  `github/codeql-action/upload-sarif`, `security-events: write` on that job only, `if: always()`, and
  `continue-on-error` on the upload step alone (code scanning may be off or a fork's token read-only).
  `--output` is written through a new file beside the target and renamed into place, and is refused
  (exit 2, nothing written) when the target or any part of its path below the repo is a symlink, a
  `..` is in it, or an existing target is not a regular file. Rule ids are one safe line of at most
  200 characters; `helpUri` must be an https URL with a host. The same workflow now pins
  `actions/checkout` and `actions/setup-python` to commits and sets `persist-credentials: false`. The
  rules' titles and links are read from the checked-out tree, so a pull request can change its own
  SARIF text (never a verdict or exit code).
- **`chock sync` can register the `chock mcp` guidance server with your agents, opt-in.** Set
  `guidance_mcp: true` (one top-level line, read like `rollout:`) in `.chock/config.yaml` and sync
  merges a `chock` server into each wired client's project MCP config: Claude Code `.mcp.json`,
  Cursor `.cursor/mcp.json`, VS Code `.vscode/mcp.json` (`servers`, `type: stdio`), Gemini
  `.gemini/settings.json` and Codex `.codex/config.toml` (`[mcp_servers.chock]` in a marked block).
  The entry is `git -c alias.chock-hook=... chock-hook -m chock mcp --repo .`: the committed launcher
  picks the interpreter at run time (`chock.python`, as hooks do), so no absolute path or home
  directory is committed. Other servers and keys are kept, a second sync changes nothing, and
  `guidance_mcp: false` (or removing the line) removes only chock's own entry. A config that does
  not parse (JSONC comments included), a `chock` server chock did not write or edited (extra args,
  env), forged TOML markers, a symlink on the path, a non-regular file or one over 1 MiB is refused
  with an error and never overwritten, deleted or followed; with the opt-in off, such files are left
  alone without error. Writes go through a same-directory temp file and an atomic rename, with every directory
  opened by file descriptor (so swapping one for a symlink mid-run cannot redirect the write; where
  the platform lacks directory fds the path-based fallback runs); every client is planned before any
  is written, and an I/O error is a clean refusal; a UTF-8 BOM,
  CRLF line endings, key order and non-ASCII text are kept; duplicate JSON keys are refused; only
  lowercase `true` opts in. `chock sync --check` reports drift in these files.
- **`chock check --history` scans the existing git history once.** At adoption, secrets committed
  before chock was installed were invisible: the gates judge a diff, so only new commits were ever
  read. `chock check --history [--since <rev>] [--max-commits N] [--max-blob-bytes N] [--time-budget S]
  [--allow-shallow] [--json] [--report-only]` applies the `content_regex` commit gates installed in
  the working tree's `.chock/compiled` (scan-secrets, block-invisible-unicode and any other gate of
  that kind) to every blob the newest N commits introduced (default 5000; blobs up to 1 MiB) and
  reports commit, path, line, policy and rule, oldest commit first; a line that persists across edits
  is reported once, where it entered. Read-only: `git log --raw` and `cat-file --batch` (list argv,
  never a checkout, a hook or a history rewrite; signature verification, textconv, external diff and
  the repo's gpg programs are switched off), each distinct blob read once, output streamed. Refuses an
  option-like or unknown ref. Matched text is never printed. **Exit codes:** 0 clean (or an unborn
  HEAD), 1 findings (`--report-only` makes this 0, for history that predates adoption), 2 the scan
  could not decide: not a git repository or git missing, a missing or corrupt blob, a shallow clone
  (unless `--allow-shallow`), no installed content gate, an unreadable or non-object gate document,
  a gate pattern that does not compile or runs over 10 seconds on one blob (POSIX), the time budget,
  or any unexpected error. **Coverage gaps, stated in the output:** binary and oversize blobs and
  submodule pointers are not scanned (counted in the text, JSON and stderr); script, ref, dependency
  and test-integrity gates are not applied; only the newest N commits are scanned. The gate patterns
  come from the working tree, so a hostile checkout could ship a slow pattern: the per-blob limit
  turns that into exit 2, and the scan runs no repo code beyond those patterns. `chock check -h`
  and the command list mention `--history`.
- **A plugin's Stop hook refuses an unreadable payload in the vendor's Stop grammar.** Plugin
  packages reuse the pre-tool `gate.json` for their Stop hook, so the runtime could not tell it was
  at Stop and answered in the pre-tool grammar (Claude, Codex and Copilot `permissionDecision: deny`,
  Cursor `{"permission": "deny"}`), which does not end a Stop. The Stop command now carries
  `--stop`: Claude, Codex and Devin answer `{"decision": "block"}`, Copilot its nested Stop
  `decision: block`, Cursor exit 2.
- **An unreadable Stop payload is refused at most 3 times, then warned.** Without a readable payload
  there is no session id, so the per-session re-entry ledger could not count it and the turn was
  refused every time. A per-repository ledger in the state directory under `.chock/` now counts refusals in a 600 second
  window: 3 refusals, then the turn ends with a warning (`systemMessage` where the vendor documents
  one; Cursor and Devin get stderr only, Devin with an `approve` answer) and a held `would_block`
  record (`reentry_verdict: unreadable`), never silently. The ledger sits under the state directory under `.chock/`, which
  protect-agent-config's shell guard covers; an agent that could edit it could pre-seed it, the same
  trust the per-session ledger places in its own for clients that send no count. Pre-tool unreadable
  payloads are never capped.
- **A stop ledger that is not a plain file keeps refusing.** Both stop ledgers (the per-session
  `<session>.stop.jsonl` and the unreadable-stop one) are lstat-checked before they are opened: a
  symlink, FIFO, socket, device or directory in the ledger, the state directory under `.chock/` or `.chock` is never
  opened (a FIFO would hang the hook until a client's timeout, which it may read as an allow) and
  nothing is written through it. With nothing countable the Stop is refused, as it is when the ledger
  cannot be written. A client that sends its own count (Cursor `loop_count`) is still believed.
- **Hooks that cannot read their input, or find their package, refuse.** Every vendored runtime
  (`.chock/bin/<agent>.py`, plugin `scripts/<agent>.py`, bundles included) used to exit 0 on an
  empty, unparseable or non-object payload. A run that judges a call (`--guard`, a blocking
  `--gate` or `--tool-call`) now refuses in the deny its client reads at the pre-tool event (Claude
  Code and Codex `permissionDecision: deny`, Copilot both the nested and the top-level CLI form,
  Cursor `{"permission": "deny"}`, Devin `{"decision": "block"}`, Gemini, Tabnine and Grok
  `{"decision": "deny"}`, Windsurf exit 2 on `pre_run_command`), a stop gate in its stop grammar,
  and exit 2 wherever that answer would not refuse; the reason goes to stderr. A spec that declares
  `warn`, a `--record` (PostToolUse) run and a run with no arguments (SessionStart) stay silent and
  exit 0. Unmapped events of a readable payload are still allowed.
- **Plugin hooks refuse when their package is missing.** Claude, Codex, Cursor and Devin plugin
  commands check for the launcher inside git's `sh` and exit 2 when it is absent, where bash-as-sh
  exited 127. The path reaches that check as an argument, never as shell text, so a root holding
  a quote, `$` or backtick neither breaks the hook nor skips it. Copilot's command still exits 0 when `PLUGIN_ROOT` is unset or empty (VS Code's
  agent-plugin format exports no root), and now exits 2 when the root is set but lacks the bundled
  adapter. Cursor's plugin hooks set `failClosed: true` on the pre-tool entry, as the repo-level
  hooks already did.
- **Coverage labels name both points.** A cell whose policy has a commit-time gate and an installed
  tool-use hook reads `enforced-at-commit + best-effort at tool use (live-run)` in `chock sync`
  and `chock enable`/`disable` output. `coverage.json` cells carry `at_commit`, true on every
  `enforced-at-commit` cell, and cells written by an older or newer chock still read. A git hook
  that runs only at push (`block-destructive-commands`' pre-push script) no longer earns
  `enforced-at-commit`, so those cells read `advisory`; no other `level` changes.
- **The baseline check holds rule verdicts.** `chock check --only baseline --base <ref>` also
  reads `.chock/security.json` (java-security) and `.chock/agentic-security.json`
  (agentic-code-security) as their runtimes do, and fails on a verdict the head loosens against the
  base: deny to ask, deny to allow, ask to allow, a pack verdict loosened, or a rule entry dropped
  where silence is looser (agentic-code-security rules carry their own default, so a dropped deny
  entry is flagged). A selection the runtime would refuse fails too. Deleting a committed
  `.chock/security.json` fails, since java-security then falls back to `~/.chock/security.json`, and a
  symlink, directory or other non-regular file at either selection path is an error.
  At the base commit, a selection path that is a symlink, a directory or a submodule, or a `.chock`
  that is not a directory, is an error naming the object (it was read as absent or as text); a
  regular file at `.chock` in the worktree is a named error too.

- **The turn's end is re-judged when the client re-enters the Stop hook.** Claude Code, Codex and
  Copilot (`stop_hook_active`) and Cursor (`loop_count`) re-enter the hook after a refusal, and it
  used to allow every re-entry, so an agent that ignored the first refusal ended its turn with the
  violation on disk. While findings remain, every re-entry is now refused, up to 3 per turn; the
  next one ends the turn with a warning that the findings are still on disk and a commit will
  refuse them: `systemMessage` for Claude Code, Codex and VS Code Copilot, stderr for every vendor,
  and a held `warn` record (`would_block: true`) in `.chock/log/gate-events.jsonl`. Each re-entry is
  logged there under the `stop-reentry` surface with `verdict` `block`, `allow` or `warn` and a
  `reentry_verdict`. The count is kept in `.chock/state/<session>.stop.jsonl` (digests of each
  flagged file's path and content, never the text), keyed on Codex's `turn_id` and Cursor's
  `generation_id` where sent; Cursor's own `loop_count` is believed over it. A ledger that is
  missing, damaged or unwritable never allows silently: it refuses again, or ends the turn with the
  warning. A warn at Stop now also reaches Codex and VS Code Copilot users as `systemMessage`.
  Commit and CI are unchanged.

- **`chock mcp`: plan-time guidance.** A stdio MCP server with one read-only tool,
  `chock_guidance(plan, paths)`. It maps a plan's words and the paths to be touched to the rules of
  the repo's installed `java-security` (read from its shipped `setup-contract.json`), keeps the
  ones the repo's `.chock/security.json` sets to deny or ask (absent = deny; a user-level
  `~/.chock/security.json` or a version-1 selection is not read), and returns at most 12 of them,
  deny before ask, then by match score, then id, each with its verdict, pack, CWE ids and the rule's
  own constraint text, in a response line of at most 4000 bytes. Matching is a rarity-weighted word overlap
  plus pack path globs from `src/chock/guidance/data/guidance_map.json`: no model call, no
  network, nothing written, nothing read outside `.agents/policies/java-security`, the selection
  file and `.chock/config.yaml`. Input is capped (plan 4000 characters, 50 paths of 512, 1 MiB per
  request line, counted in bytes); absolute,
  `..` and control-character paths are refused, and paths are only matched, never opened; a
  symlinked, oversize, too deeply nested or unreadable contract, selection or config is reported as
  an error, never as "no rules", and the server answers every request (an unexpected failure is a
  JSON-RPC internal error) and keeps serving. Not done: `chock sync` does not yet register the server in any client's MCP config (chock
  has no MCP config writer and agentseam records no MCP paths), and `agentic-code-security` ships
  no structured rule metadata to read, so only `java-security` is served. Matching is lexical: a
  plan that names none of a rule's words gets nothing, and an empty result is not a clearance.

- **GitHub annotations from the CI gate.** With `GITHUB_ACTIONS=true`, `chock gate run --event ci`
  also prints one `::error` (or `::warning` for warn, ask and anything the rollout level lowered)
  workflow command per new finding, `file`, `line` and `title=chock <policy>: <rule>` included, and
  appends a policy, new findings, baseline, verdict table to `$GITHUB_STEP_SUMMARY`. GitHub
  shows 10 errors and 10 warnings per step and one step runs every gate, so the gates of a step
  share that budget (a file under `$RUNNER_TEMP` keyed by run, attempt, job and step); every new
  finding not annotated is listed in the summary. Only new findings (the gate's own baseline logic)
  are annotated. Text from a finding, path or rule is escaped so it cannot inject a workflow
  command, and at ci no line of the refusal on stderr can start one either; summary cells cannot
  render a link, image or mention. Output only: an annotation failure is reported and never changes
  a verdict, an exit code, the refusal or the gate log, and other environments print exactly what
  they did.
- **A watch-only rollout mode.** `rollout: observe | ask | enforce` in `.chock/config.yaml` caps
  how far compiled gates escalate: observe turns a block or ask into a warning, ask caps at ask
  (and an ask does not fail CI), enforce (the default, and what an absent, repeated, unreadable,
  unknown or symlinked value means) changes nothing. Not capped: command guards, `tool_call`
  gates, the MCP gateway and a script hook's own exit 1, which still block. A gate the level
  lowered logs `rollout`, `would_action` and `would_block` to `.chock/log/gate-events.jsonl`, even
  with `CHOCK_GATE_LOG=0`, and `chock status --only log` counts them. Nothing the judged actor
  can edit lowers the level: an agent (a tool call, the turn's end, an agent's commit) is held to
  the stricter of HEAD's committed level and the working tree's; at CI the base's committed level
  caps the head's, so a pull request cannot lower its own gates; `CHOCK_ROLLOUT` counts only for a
  person's own commit or push. `chock check --only baseline --base <ref>` refuses a downgrade,
  reading the level the way the runtime does (line by line, not as YAML), so a config the two
  would read differently cannot hide one. `chock status` leads with `ROLLOUT:` and where the level
  came from whenever it is below enforce. The catalog's protect-agent-config and block-no-verify
  must also cover `.chock/config.yaml` and `CHOCK_ROLLOUT` / `CHOCK_GATE_LOG` for agents that set
  no marker.
- **Gate-log report fixes.** `--by rule` credited each rule with the record's total new findings,
  so two rules in one refusal were each shown every finding; each rule now counts its own. Ties in
  the top-files list are broken by path, so the report is the same on every run. `chock status`
  refuses `--json` and `--format md` unless `--only log` is the only section, since mixing the
  policy or registry text into them made the output unparseable. A markdown cell escapes `\`, `[`
  and `]`, so a log value can no longer render as a link, and the text report replaces control
  characters, so a log line cannot send escape sequences to the terminal. `--since` takes 1 or
  more days.
- **A findings refusal leads with the finding.** A script gate's refusal put the policy's long
  message first and the findings last, so an agent read the boilerplate before the `path:line:`
  that mattered. Findings now come first, then a one-line summary, then the policy message. A
  tool-use refusal (and the turn's end) carries the findings and one line on how a person
  customises the rules, with no policy text. At tool use and for an agent's commit, a sentence
  telling the reader to write `chock: allow` is replaced by "ask a person to review it; an agent
  cannot add the waiver", since an agent's waiver is never honoured; a person's commit and CI
  keep the sentence.
- **`chock status --only log` groups and reports.** `--by policy|rule|agent|event` counts blocked,
  asked, warned, `would_block` (its own column once a record carries it), new against baseline
  findings, agents and the top three files per group; `--format md` prints a paste-able markdown
  summary. The log is read locally and only ids, counts and the paths in `matches` are shown, never
  file contents. `chock status` now forwards `--policy`, `--since` and `--json` to the log, which
  only `python -m chock.gatelog` accepted. The runner records `agent` (the `agent_signal` marker,
  when one is set) on every git and script-hook outcome, and `rules` (rule id to count of new
  findings) when a script finding names its optional `rule`; older records group under "unknown".
- **Plugin bundles: install a set once.** `chock plugin build` reads an optional `bundles.yaml`
  (schema-checked: id, version, description, two or more member policies) and packages each bundle
  beside the policies in every format. Claude's manifest documents `dependencies`, so its bundle is a
  manifest-only meta-plugin that installs its members. The Agent Plugins 1.0.0 schema forbids extra
  manifest fields, and no dependency field was found for Codex, Cursor, Copilot or Devin, so those
  merge: one plugin carrying every member's skills, hooks and scripts, each member's scripts, gate
  and sibling packages kept under `scripts/<member>/` and its hook commands re-pointed there. The
  bundle description states each member's enforcement, and its posture sentence is the weakest
  member's. `chock marketplace build` lists bundles first in the index and in `PLUGINS.md`.
  A bundle writes its own `LICENSE`, and only when every member shares one licence and holder
  (dated from the oldest member); a member's notice is never carried over to cover the others. A
  `--bundles` file that does not exist fails the build instead of reading as "no bundles".
  A bundle whose built content changes while its version in the bundles file stays the same
  fails `chock plugin build` (and `--check` reports it as `unbumped`): clients that update a
  plugin by version would otherwise never receive a member's fix. That includes a change that
  comes from an engine update, not only a member's own.
- **Runtime bytecode stays out of git.** `.chock/bin/` holds Python the hooks import, so running a
  hook wrote `__pycache__` there, and the `!.chock/bin/**` rule that keeps the runtime tracked
  re-included it: every adopter saw untracked bytecode after the first hook ran. `chock sync` now
  appends ignores for `__pycache__/` and `*.pyc` under `.chock/bin/` and `.chock/compiled/`, after
  the negations, the way it already did for `.agents/policies/`.
- **A packaged skill's gate note states the gate's action.** Every Claude, Codex, Copilot, Cursor
  and Devin package with a tool-use gate said the policy "is enforced in this client", including a
  gate that only asks or warns. The note now reads "asks the person before the action proceeds" or
  "warns, and does not block" for those gates, and keeps "is enforced" for a gate that blocks.
- **SKILL.md footers say what chock actually enforces.** The footer was picked by artifact type
  alone, so a rule with a command guard, a git script or a gate still read "stays advisory even
  when compiled", and a hook whose gate only warns, or binds only at tool use, still read "becomes
  a git hook that exits non-zero". The footer now keeps "advisory" for the skill alone and names
  what `chock` compiles from the manifest: a guard or git script can refuse, a gate blocks, asks
  or warns, at the surfaces it declares.
- **Plugin keywords use a compliance entry's control id.** A dict-shaped `owasp_asi` entry such
  as `{control: ASI01, coverage: partial}` was stringified whole into `plugin.json` `keywords`.
  The keyword is now the control id, lowercased.
- **The MCP gateway judges a `content_regex` gate inside its scope.** The gateway matched every
  string argument of a tool call, so `pin-github-actions` (bounded to `.github/workflows/*` and
  `.github/actions/*`) refused a README written through an MCP filesystem tool for quoting
  `uses: a/b@v4`. The gateway spec now carries `applies_to.paths`. A call's write target is read
  from the same argument keys the session log uses (`file_path`, `filePath`, `path`,
  `notebook_path`, `target_file`, `TargetFile`). Content is judged only at an in-scope path,
  `forbidden_path_regex` applies to that path, and a path-bounded gate does not judge a call that
  names no path. Gates with no bound behave as before. `allowlist_pragma` stays unhonoured there:
  a waiver the agent writes into its own call must never lift the block.
- **The SKILL.md advisory line shows the gate's paths and no longer cuts a regex mid-pattern.**
  `paths=<applies_to globs>` follows the gate kind; a regex param (`*_regex`, `*_pattern`,
  `*_pragma`) longer than 60 characters renders as `<name>(regex)`, shorter ones in full.
- **`chock sync --check` compares committed agent-hook configs.** It compared only the compiled
  tree, so a vendor hook config still naming a guard script a later sync had replaced passed the
  check while the gate failed closed and denied every shell command. It now runs the real
  installers on a scratch copy of each wired vendor's committed config and reports `differs`
  where chock's own entries disagree; foreign entries and list order are ignored. The repo's own
  hook configs, coverage and `chock_session.py` runtime are regenerated.

## 0.15.2 — Script hashes skip Python bytecode

- **Script hashes skip Python bytecode.** A `.py` guard that imports a sibling package makes
  Python write `__pycache__` into `implementations/` the first time it runs. The registry scan
  and the determinism check hashed those `.pyc` files, so `chock registry scan` drifted as soon
  as `chock check --only evals` had run a guard. Both now hash only shipped files, through one
  predicate. The shellcheck sweep also leaves `*.py` guards out: their sh trampoline header made
  discovery by shebang hand their Python bodies to shellcheck.

## 0.15.1 — Plugins ship their guard's shared packages

- **Plugins ship their guard's shared packages.** The Claude, Codex, Copilot, Cursor and Devin
  plugins copied only `implementations/<id>.py`, so a guard that imports a sibling package such
  as `chock_shellparse` crashed with `ModuleNotFoundError` and asked instead of denying. Each
  plugin now also carries every directory under `implementations/` that has an `__init__.py`
  (its `.py` files, recursively, no `__pycache__`) beside the guard.

## 0.15.0 — Script gates judge only the findings a change introduces

- **Script gates judge only the findings a change introduces.** A `kind: script` gate that prints
  `{"findings": [{"key", "path", "line", "message"}]}` on stdout is run again on the baseline text
  (`"baseline": true`; HEAD at commit and Stop, the range base at push and ci, the disk before the
  write at PreToolUse), and only findings whose key the baseline lacks count, including a
  violation created by deleting a line. No new findings allows; otherwise the change-run's exit
  code decides and the reason lists just the new findings. A script that prints no findings
  document behaves as before. The two runs share the 30s budget. The gate log records
  `new_findings` and `baseline_findings`. Agent-event HEAD reads now resolve from `repo_root`, so
  a root below the git top-level finds its baseline (and a `content_regex` waiver already in
  HEAD). Vendored runner resynced; run `chock sync`.
