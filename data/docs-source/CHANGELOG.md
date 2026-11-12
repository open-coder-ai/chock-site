## 1.1.0 - 2026-11-11

- `.agents/policies/INDEX.md` says "Also checked in the agent" only when the policy's effective surfaces
  keep an in-agent one (`pre-tool-use`, `stop` or `agent-hooks`). A `policies.overrides.<id>.surfaces`
  that removed them left the note in place while `chock status` reported the narrowed state (#231).
- A refused agent commit prints the "a waiver it adds was not honoured" note only when the policy defines
  an `allowlist_pragma` or is a `kind: script` gate, which may honour its own waiver comment. A built-in
  policy with no waiver got the note too, pointing a person at a waiver that does not exist. The refusal,
  its message and its exit code are unchanged (#238).
- **`docs/compatibility.md` states the 1.x promise.** It said chock was pre-1.0. It now says what
  a patch, minor and major release may change, which part is machine-checked (patch byte-identity,
  `tests/test_emitter_stability.py`) and which is kept by review. `SECURITY.md` no longer says
  "Until 1.0".
- A hook command that names a pinned policy index (`--multi <index> --index-sha256 <hex>`) judges every member policy in one process and refuses if any member denies, if the index or a member file does not match its pin, or if a member fails (not wired by `sync` yet).
- A multi-policy hook refuses on any fault in its member run, combine or log write instead of exiting with a traceback; each member judges its own copy of the event; the policy index refuses a member file or path argument that is absolute or contains `..`.
- `chock sync` writes one hook entry per event and matcher for the policies that judge a call before it runs. Its command names a pinned policy index (`.chock/index/<vendor>-<event>-<hash>.json`) listing each policy's argv, timeout and the sha256 of every file its single-policy entry was verified by. A policy whose timeout plus a 5 s grace cannot fit the client's entry timeout is refused. A vendor whose hook schema documents no timeout keeps one entry per policy. `chock check` reports an old per-policy config, or an index that no longer matches its sources, as drift for `chock sync` to rewrite.
- Hook start-up is cheaper: the runtime loader executes the already-hashed bytes without importing `inspect`, the POSIX launcher runs the runtime directly instead of a separate Python probe (a candidate that writes no start marker passes to the next; Windows keeps the probe), and the write gate reads each committed file once per process.
- The repo stop's pre-tool check (`--stop-check`) rides the catch-all multi entry when one exists (the entry with no matcher, today token-efficiency's): that process checks the stop once, before any member, and refuses at once with the standalone check's own answer, so a tool call runs one hook process fewer. A fault in the stop check refuses, and a stopped call whose payload cannot be read is refused. Where no entry matches every tool, or the vendor folds nothing (Windsurf), the standalone stop-check entry stays exactly as it was. Applies to sync's repo hooks and to built plugins and bundles alike.
- A timed-out policy child is killed with its whole process tree, and a member's own deadline can be set per thread (groundwork for one hook process per event).
- `chock plugin build` writes `"homepage": "https://chock.sh"` into the Claude Code, Codex, Copilot and Cursor plugin manifests, each of which documents the field. Devin's manifest carries none, since no Devin field reference documents it.
- A built plugin runs one hook per (event, matcher) instead of one per policy: its commands name a pinned policy index shipped in the package (`--multi <root>/scripts/chock_index/<name>.json --index-sha256 <hex> --root <root>`), whose members are paths relative to the plugin root. A bundle folds into one index per (event, matcher) and its per-member toggle still switches a member off. An index that fails its pin, a member file that drifted, a path that is absolute or climbs out of the root, an empty index and an empty root each refuse. A multi-policy hook now refuses an unreadable payload, and keeps what a member wrote to stderr.
- PyPI's Homepage is now https://chock.sh. The README links chock.sh, its builder, `/llms.txt` and
  `/api/index.json` instead of "launching soon", and its Quick start installs the pinned release from PyPI
  (`chock==<version>`) instead of a git commit. A test refuses any README install line that is not the current version.
- The README opens with chock.sh's promise. Its catalog numbers, incident table, agent lists and repository
  table are written by `docs/assets/readme/derive.py readme` from `data.json` (catalog `1e60d21`) and chock's
  own install and witness data; a test fails when they differ. The FAQ links `docs/compare.md`. The PyPI
  classifier is `Development Status :: 4 - Beta`. New issue form: "I tried Chock and…".
- **README numbers leave out deprecated policies.** `docs/assets/readme/derive.py` skips a registry
  entry whose `status` is `deprecated`, so the README counts what chock.sh lists. At catalog
  `1e60d21`: 71 policies (was 72), 11 in the agent (was 12), 38 Claude Code `block` labels (was 39),
  4,390 of 4,572 eval cases replayed (was 4,501 of 4,683).

## 1.0.0 - 2026-11-02

- Entries for unreleased changes now live in `changelog.d/` (one file per change); see
  `changelog.d/README.md`.
- **chock depends on `agentseam==0.4.1`.** 0.4.1 keeps `locked(path)`'s lock file out of the
  config's directory (a per-user lock directory), so an install leaves no file beside a committed
  config. Only the pin changes: `pyproject.toml`, the two `.in` files and the four lock files.
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
- **Hardening: `chock add --from` never stores or prints a URL's credentials.** The `user:token@` part of a
  catalog URL is dropped before the source is written to `chock.lock`, printed, or put in an error message.
- **Hardening: `chock add` finds a pack only inside the catalog.** The fallback lookup (`<area>/<id>`) now
  applies the same containment check as a `registry.yaml` entry, a pack directory that is itself a symlink
  is refused, and the copy never follows a link.
- **Security: `chock add --ref <sha>` accepts only a commit on a branch or tag the source publishes.** A
  remote can serve by id any commit in its repository network, including a fork's or a
  `refs/pull/N/head` commit, so a copied `--from <official url> --ref <sha>` could install code the
  source never published. After the commit is fetched, `add` now fetches the source's branches and tags
  (no blobs) and refuses, installing nothing (exit 2), unless the commit is reachable from one of them;
  `refs/pull/*` and other namespaces never count and there is no override. To use a fork's commit, pass
  the fork's own URL as `--from`. A local directory source is the user's own checkout and is not
  checked; branch and tag refs are unchanged.
- **An agent cannot switch chock off.** `chock sync`, `recompile`, `install-hooks`, `enable`, `disable`,
  `add`, `remove`, `init` and `compile`, the commands that change `.chock/config.yaml`, `chock.lock` or the
  compiled tree, refuse under an agent marker (`CLAUDECODE=1`, `AI_AGENT`, a truthy `CHOCK_AGENT_COMMIT`, a
  configured `agent_commit_env` name) with the rule `chock resume` applies: a person runs them from their own
  shell. The refusal is logged (`policy_id: chock-cli`). `sync --check`, `check` and `status` stay open. One
  actor rule now serves every check: `CHOCK_AGENT_COMMIT=0` unsets that one variable and clears no vendor
  marker, so `CHOCK_ALLOW=<id> CHOCK_AGENT_COMMIT=0` in an agent's terminal no longer answers an ask and
  `CHOCK_ROLLOUT` is ignored there; a person's own shell, which has no marker, keeps both. A refused ask tells
  a person the `CHOCK_ALLOW` line and tells an agent to ask the person, naming no override. For the agent
  asking `chock_guidance`, a `policies.disabled` entry counts only once committed (HEAD), the way the
  committed rollout caps the working tree's. docs/assurance-case.md restates "tamper-evident" to what the
  mechanism gives and lists the bytecode and runtime-pin limits.
- **chock depends on the released `agentseam==0.4.0`.** The build-time dependency was a direct
  reference to an agentseam commit, which PyPI refuses; it is now the PyPI release, and the
  runtime, brand-assets, dev and binary lockfiles carry its PyPI hashes.
- **Antigravity: hooks.json now uses the documented schema, so Antigravity loads chock's hooks.**
  Antigravity rejected the plugin's hooks.json (`invalid hook "agentseam": command hook must specify
  'command'`, a maintainer's witness run, 2026-10-17) because Stop was written as a `{hooks}` group.
  agentseam is pinned to main 945ceb0, which writes Stop handlers bare (`{type, command}`) and gives every
  PreToolUse/PostToolUse group `matcher: "*"`, per antigravity.google/docs/hooks (read 2026-10-17). Both the
  plugin's hooks.json and `chock sync`'s `.agents/hooks.json` follow. Not witnessed yet: the corrected file
  has not been run in Antigravity.
- **Antigravity's plugin is witnessed: `chock install --selection --client antigravity` no longer warns "Untested" or
  asks for evidence.** In Antigravity IDE on Windows 11 (version not recorded), chock's shipped plugin, built on Windows
  (quote-free hook command), refused `block-no-verify` on a shell command before it ran and `pin-github-actions` on a
  workflow write at turn end, not at the write, while `git status` ran (org-plan
  `witness/results/witness-antigravity-2026-10-18.md`). The claim is for a Windows build only. The turn-end and
  fail-mode warning stays.
- **Antigravity on Windows: plugin hook commands are now quote-free, so cmd.exe hands them to git intact.**
  Antigravity IDE on Windows runs a hook `command` through cmd.exe and passes each `"` on as `\"`, so the
  single-quoted git alias split (`unknown option: -f`) and a double-quoted one did too (a maintainer's witness
  run, 2026-10-18; agentseam 683f95b records the cmd.exe runner). Built on Windows, the Antigravity plugin now
  runs `git -c alias.chock-sh=!<refusal> chock-sh <launcher> <args>` with no quote or space in any argument:
  words split by `${IFS}` in git's sh, every cmd.exe operator caret-escaped, and the missing-launcher refusal
  (exit 2) kept. A plugin folder whose path holds a space, quote or cmd.exe metacharacter is refused at install
  with an error naming the path. The fact is store data (`windows_hook_command: quote_free`); every other
  client, and every non-Windows build, is byte-identical. Not witnessed yet: the built command has not been run
  in Antigravity.
- **Antigravity on Windows: `chock sync` writes quote-free hook commands too, following the plugin's rule.**
  The repo route's double-quoted git alias reaches cmd.exe the same way the plugin's did, so on Windows, for a
  client whose store data says `windows_hook_command: quote_free`, sync now writes each command in
  `.agents/hooks.json` as `git -c alias.chock-hook=!<refusal> chock-hook <runtime> <args>` with no quote or
  space in any argument; the missing-launcher refusal (exit 2) is kept, and an argument that cannot be carried
  bare is refused. `.chock/compiled` is unchanged; every other client and every non-Windows sync is
  byte-identical. A committed `.agents/hooks.json` synced on Windows is the Windows form. Not witnessed yet.
- **goose's guard note and Antigravity's posture render their witness clause from the ledger.** goose's note
  now cites its witness row and says goose runs every hook with `sh -c`, so sh (Git for Windows' sh on Windows)
  must be on PATH, else every tool call is denied (org-plan `witness/results/witness-goose-2026-10-18.md`).
  Antigravity's posture says "not witnessed by chock" until its ledger row lands.
- **Per-policy on/off inside the agent (builder v2, 2.1b).** Every merged plugin `chock install --selection`
  builds now checks `.chock/guardrails.json` (repo scope, committed) or `~/.chock/guardrails.json` (user
  scope, where the repository has none) before each member judges, honouring it only while it matches the
  record `chock bundle` keeps (below):
  `{"version": 1, "bundles": {"<bundle.name>": {"<policy-id>": "on"|"off"}}}`, schema in
  `guardrails.schema.json`. An absent entry is on; on and off only. A file that is unreadable or invalid
  switches nothing off and prints a one-line warning. A member switched off answers the client's own
  allow and writes one line to `.chock/log/gate-events.jsonl` beside the governing file.
- **`chock bundle on|off <policy-id> [--bundle <name>] [--scope repo|user]` and `chock bundle status`** are the
  file's only writers and its reader. `status` lists every chock bundle installed in a client's default
  folder with each member's state and label. Every merged plugin also carries a "customize guardrails"
  skill that shows the members and prints the command for a person to run; it never writes the file.
- **Built-in self-protection, not switchable:** every merged plugin refuses an agent's write to either
  toggle file (shell guard, best effort, and an Edit/Write gate; case, `//`, `..`, backslashes and links
  folded) and an agent's own `chock bundle on|off` or `status --adopt`. Reads pass.
- **Turn-end check of the toggle files:** `chock bundle on|off` records each file's sha256 in
  `.chock/state/guardrails.sha256` beside it. Every merged plugin's Stop hook refuses a turn's end, in the
  client's own words and with the usual re-entry cap, while a toggle file in scope (repo or user) differs from
  that record: changed, deleted, or never recorded. That catches a write the best-effort shell guard missed,
  including on Copilot and Devin, which judge no write tool. The hook-time lookup honours a toggle file only
  while it matches that record; otherwise every guardrail stays on, with a one-line warning, so a file an agent
  wrote by any trick switches nothing off.
- **`chock sync` records a committed `.chock/guardrails.json` only when it is byte-identical to the remote
  default branch** (`origin/HEAD`, else `origin/main`), so a teammate's fresh clone honours the reviewed file
  once synced, and prints its on/off summary. A local commit that is not on the remote is never recorded: a
  person reviews it and runs `chock bundle status --adopt`, which the built-in guard refuses from an agent.
- **`chock check --only baseline` reports a member switched off in `.chock/guardrails.json` against the
  base branch, or the committed file deleted, as a loosening.**
- **Hardening: a catalog URL is never read as a path in the working directory.** A source spelled as a URL
  or `user@host:path` is always fetched from the remote, and its published-branch checks always run, even
  when a directory of the same shape exists under the current directory. A local catalog is a path.
- **`chock sync --ci` pins the engine in the generated workflow.** It used to install
  `git+https://github.com/open-coder-ai/chock` with no ref, so an adopter's CI ran whatever chock
  `main` held. It now installs the exact commit that generated the file (the same commit the install
  marker records). When no commit is known (a PyPI install), it pins the installed version from PyPI
  and says so in a comment. Re-run `chock sync --ci` to move the pin.
- **Claude Code's plugin is witnessed.** In Claude Code 2.1.283 on Windows, the chock plugin refused
  `block-no-verify` at `PreToolUse:Bash` and `pin-github-actions` at the `PreToolUse:Write`, before either ran
  (org-plan `witness/results/witness-claude-code-2026-10-12.md`). The ledger row is for the plugin-hook surface
  only: the repo-hook route and the Stop (turn-end) refusal were not witnessed.
- **`chock sync`'s "Untested" now means no live run of chock's repo hooks in this client.** A plugin witness covers
  `chock install`, not the hooks sync wires, so sync no longer counts one. Sync now calls claude_code, codex_cli
  and cursor Untested; vscode_copilot, witnessed on agent-hooks, is not.
- **`chock new` and `chock check` agree with what they print.** `chock new` now prints two
  next steps, `python -m chock sync --repo <root>` then `python -m chock check --repo <root>`
  (no `&&`, which Windows PowerShell 5.1 lacks); the old `chock check <root>` exited 2
  (`check` takes `--repo`). `chock check` ends with one line,
  `== result: PASS` or `== result: FAIL (exit <n>; see the FAIL above)`, so a failing section is no longer
  followed by a later section's `[PASS]` as the last word; the exit code is unchanged.
- **The `content_regex` template no longer flags itself.** Its gate message said the marker
  it refuses, and INDEX.md quotes the message, so committing a fresh scaffold was blocked by
  its own policy. The message now spells the marker `DO-NOT-COMMIT`, which the pattern does not
  match.
- **Codex is witnessed: `chock install --selection --client codex` no longer warns "Untested".** An install in
  Codex CLI 0.157.1 on Windows was witnessed (guard, write gate, turn-end gate, self-protection and per-policy
  on/off), so the `client` warning that chock has not witnessed an install now names only Copilot, Cursor and
  Devin. Codex still warns that its plugin hooks stay advisory until trusted in `/hooks`.
- **Copilot's plugin is witnessed.** In GitHub Copilot CLI 1.0.94 on Windows, the chock plugin refused
  `pin-github-actions` on a workflow `create` and `chock-guardrails-protect` on a shell write to
  `.chock/guardrails.json`, both at `preToolUse`, before either landed (org-plan
  `witness/results/witness-copilot-2026-10-11.md`). The ledger row is keyed `copilot`, agentseam's id for the plugin
  bundle format, and covers the plugin-hook surface in Copilot CLI only: VS Code agent mode, a toggle-file write through
  the edit tool and a delete-only `apply_patch` were not covered. `chock install --client copilot` prints the same
  warnings as before.
- **Copilot and Devin are witnessed: `chock install --selection --client copilot|devin` no longer warns "Untested".**
  Installs in GitHub Copilot CLI and Devin CLI on Windows were witnessed (org-plan
  `witness/results/witness-copilot-2026-10-08.md` and `witness/results/witness-devin-2026-10-08.md`: guard, turn-end
  gate, self-protection and per-policy on/off), so the "Untested" `client` warning now names only Cursor. Both still
  warn that a gate judges what a turn wrote only at turn end, and Devin that its hooks fail open.
- **Devin's install steps say Windows needs Developer Mode.** `devin plugins install --local` creates a symbolic link,
  so on Windows it needs Developer Mode or an elevated shell; without either it fails with "os error 1314: A required
  privilege is not held by the client".
- **`chock bundle status --adopt` refuses an invalid toggle file.** It used to record a file such as `{}` as it was,
  leaving `chock bundle on|off` refusing it with no way out but deleting it. Adopt now exits non-zero, records nothing
  and names the reset: `chock bundle status --adopt --reset` rewrites each invalid toggle file in scope as a valid
  all-on file and records it. A reset never switches anything off, leaves valid files as they are and never removes a
  folder. `chock bundle on|off` on an invalid file names the same command.
- **Copilot CLI: the write gate and the toggle-file guard now judge `create` and `apply_patch` before the write.**
  Copilot runs a plugin's `PreToolUse` hook on `Write|Edit` for its `create`, `edit`, `str_replace_editor` and
  `apply_patch` tools, but passes the tool's own arguments: `create` carries `file_text`, and `apply_patch`
  carries the patch as the bare `tool_input` string (or under `input`/`patch`). The runtime read neither, so in
  the Copilot witness run (2026-10-08) an unpinned workflow and a write of `{}` to `.chock/guardrails.json`
  landed and were refused only at turn end. Both are now read, and the turn-end check stays. `edit`
  (`old_str`/`new_str`) was already judged. An `apply_patch` that deletes a file is still not refused at
  write time; a deletion that loosens a toggle is refused at turn end. Copilot keeps its "turn end only" label
  until a witness re-run.
- **Copilot's label says the write is judged before it lands.** Copilot CLI 1.0.94 on Windows refused an
  unpinned workflow `create` at `preToolUse`, and nothing landed (org-plan
  `witness/results/witness-copilot-2026-10-11.md`). `chock install --client copilot` now reads "blocks on an
  agent's file writes and at turn end", and a client note says VS Code agent mode's write path is unmeasured.
- **Fix: Cursor's write gate on Windows judges the write inside its workspace.** Cursor sends no `cwd` and
  spells its root `/C:/...`; the gate now takes the repository root from `workspace_roots` (the one holding
  the written path), so a Write under `.github/workflows/` is judged instead of passing as outside the repository.
  The guardrails wrapper now refuses (exit 2, with the reason) when it fails before the adapter answers.
- **Cursor is witnessed: `chock install --selection --client cursor` no longer warns "Untested".** On Windows,
  Cursor refused `block-no-verify` at `beforeShellExecution` and `pin-github-actions` at the `preToolUse` write
  (org-plan `witness/results/witness-cursor-2026-10-11.md`). The `client` warning that chock has not witnessed
  an install now names no client. Cursor's admin-setting warning stays.
- **The decision log is hash-chained.** Every line on every route carries `seq` and `prev`, the
  sha256 of the line before it; the first line after a rotation names the rotated file's last.
  Writers take the log's lock, so hooks running at once never fork the chain; a line that cannot be
  chained is still written, marked `unchained`, and no verdict changes. `chock status --verify-log`
  reports the first break (file, line, expected and found) and exits 1; `--head <seq>:<sha256>`
  confirms a head kept earlier. `chock witness export` carries each log's head (`chain`, an
  additive optional key; the format stays `chock-witness-export/1`), and a person's
  git-hook overrides without the approver. It shows tampering to someone who kept a head; it does not
  stop a local admin from rewriting the whole file.
  An intact chain needs every runtime regenerated (`chock sync`); until then, an older runtime's line
  after the chain began is reported as an `unchained` break.
- **An allowed tool call is one decision-log line, not one per policy hook.** At `info`, however many
  policy hooks judge a call, its plain allow is written once, at once, by its first hook, and names no
  policy (`debug` still writes every hook's line). `chock status` counts allowed calls in total
  (`allowed_calls`), never per policy; per-policy columns show blocks, asks, warns and overrides. With no
  client call id, identical calls in the same second are one line. Every block, ask, warn, fault and
  override keeps its own line per policy. The `target` fingerprint is
  tighter: a Windows drive or UNC path on macOS or Linux is hashed as outside the repository; a shell
  program is named only when it is a common command or a plain word with no folder, digit, quote or
  redirect, else `-`; an MCP `server/tool` is redacted and cut to 128 characters; `client_type` keeps only
  `[a-z0-9_-]`, at most 32; and a path that is not UTF-8 no longer drops its line. `chock doctor` now warns
  at `info` when sessions start but no hook fires. The fingerprints are unsalted, so anyone holding the
  log can confirm a guess; docs/decision-log.md says so.
- **The decision log now says who did what on every line.** Each line carries `actor` (`agent:<client>`
  or `person`, by the agent rule a commit is judged by), the client's `session_id`, and on a tool call a
  `target` fingerprint, never content: a repository-relative path, `outside:sha256:<hex>` for a path
  outside the repository, `<program> sha256:<hex of the whole command>` for a shell command (no argument
  is ever written), or `<server>/<tool>` for an MCP call. Every allowed tool call is now logged at the
  default `info` level as one such fingerprint line, so the log can answer "what did the agent touch"; it
  was debug-only before. Redaction still runs first, files stay owner-only, and nothing leaves the machine.
- **A refusal says why, and `--selection` takes a quoted code.** A hook deny now reads `Blocked by chock policy:
  <policy>: <the guard's own line>` (for example `BLOCKED: destructive rm command targeting '.git' is not allowed
  without approval.`), the way an ask already carried its reason; exit codes and each client's JSON are unchanged.
  `chock install --selection` strips one surrounding pair of single or double quotes before decoding, because
  cmd.exe passes them through, and a code that still fails to decode says so.
- **Devin is witnessed through its plugin: the Devin plugin's posture now says "witnessed blocking on Devin CLI
  3000.11.3 (local session), Windows, 2026-10-08" instead of "not witnessed by chock".** A chock plugin installed with
  `devin plugins install --local` refused `git commit --no-verify` and an agent's `chock bundle off` before either ran;
  `pin-github-actions` let the write through and refused only at turn end; self-protection held (org-plan
  `witness/results/witness-devin-2026-10-08.md`). The ledger row is for the plugin-hook surface only: the repo-hook
  route was not witnessed, so `chock sync` still prints "Untested" for devin.
- **Security: engine hardening, round 2.** Path handling and the person-only checks are stricter.
  - The write gate, the turn-end check and the MCP gateway judge the same canonical spellings of a path.
  - Every kind of file change, deletions and moves included, reaches the gates that judge paths.
  - A policy's path gate also covers that policy's own folders.
  - A plugin gate judges from the repository top level, and the turn-end read of the worktree is bounded to regular files.
  - A guardrails member is off in a repository only when the committed toggle file says so.
  - `--check` opens a person-only command to an agent only where the command defines it.
- **Hardening: `chock eval export` writes only under `--out`.** A policy whose manifest `id` is not a valid
  policy id (`^[a-z][a-z0-9-]{2,63}$`) is reported as an error and exports nothing.
- Hardening: the frontier-standard fetch refuses a redirect to a non-https target and checks the final
  URL's scheme before reading.
- **Added and removed lines are read from the diff's structure, not by prefix.** The vendored gate runtime
  dropped every added line whose text began with `++` (and every removed line beginning with `--`) as if it
  were a file header, and `str.splitlines` cut a line at a form feed or Unicode separator so its tail lost
  its `+`; blocked content on such a line was allowed. File headers are now read only before a file's first
  hunk, hunk lines are classified by their first character and bounded by the hunk's counts, and a diff that
  git cannot produce or that does not parse refuses (exit 2). The diff is read without colour, external diff
  drivers or textconv. `chock review require` and the gate-log check list paths with `-z`, so a name with a
  space, a newline or non-ASCII is matched verbatim.
- **`chock status --only log --format md` escapes `@` and `!`** in every cell, as the runtime's own report does, so a
  logged value pasted into GitHub cannot mention a user or team or open an image.
- **The write gate reads an `apply_patch` text the way Codex does, so nothing the patch writes escapes it.**
  The patch reader cut the text at the first `*** End Patch` anywhere, even inside an added line, so the rest
  went unjudged. It matched headers without Codex's whitespace trimming: an indented `*** Add File:` after a
  delete or an add was not seen, so its file was judged under the wrong path or not at all. It placed hunks
  only by exact or trailing-space match, so a hunk Codex places by trimmed or ASCII-punctuation match left
  the file unjudged. It also read paths from the repository root rather than the agent's working directory,
  and read each file from disk even when an earlier file in the same patch had already written it. Blocked
  content on any of these paths was allowed (measured with Codex CLI 0.162.1's `apply_patch`: 12 payloads
  that Codex writes were allowed; all are now refused). The reader now ports Codex's own parser and hunk
  placement. A patch Codex would not parse is refused rather than guessed at.
- **A gate pattern cannot hang a commit or fail a hook open.** A `content_regex` or `test_integrity`
  pattern a backtracking engine can run in exponential time (`^(a+)+$` on a 60-character line) used to
  hang `git commit` on every platform, burn the client's hook timeout in the agent (which fails open) and
  wedge `chock check --history` on Windows. Now every gate pattern runs in a child interpreter the engine
  kills at a deadline (`PATTERN_SECONDS`, 10 s per judgement), on every platform: the git hook exits 2
  naming the gate, the write and tool_call paths refuse naming it, and the history scan errors naming it.
  `chock validate` and the compile step also refuse, naming the param and the pattern, a pattern whose
  nested repeats can run into each other (a linear-time check; overlapping alternation is left to the
  deadline). The vendored runtimes under `.chock/bin` are regenerated; `chock sync` rewrites them.
- **Security: the gate names no path when its compiled file cannot be read.** The message now carries the exception type, not the path or the raw error text; the gate still exits 2.
- **A changed file is judged under its own name, however git would quote it.** The vendored gate runtime lists
  changed paths with `git diff -z` and keeps each name verbatim. A staged file whose name held ESC, a newline
  or a leading space was C-quoted or stripped, could not be read back, and was allowed unjudged. A listing git
  cannot produce, or one that is not NUL-terminated UTF-8, now refuses (exit 2) instead of judging an empty
  change. Paths reach git as literal pathspecs, never globs.
- **`chock gateway` writes the decision log.** Every judged `tools/call` gets a line in
  `<repo>/.chock/log/gate-events.jsonl` with the fields every hook writes: one `allow` line per
  forwarded call (no policy), one `block` line per refusing policy (`gate-block`, `gate-ask`, or
  `fault` for a gate that cannot run), `target` `<server>/<tool>` redacted and capped at 128
  characters, and never the call's arguments. A gate that raises now refuses the call (`fault`)
  instead of stopping the gateway. A log that cannot be written changes no verdict.
- **`chock gateway` honours `chock stop`.** While a stop reaches the MCP client, every `tools/call`
  is refused with `stopped: <reason>` and logged (`block`, reason `stopped`, policy `chock-stop`);
  `initialize` and `tools/list` still pass. A stop file that cannot be read refuses.
- **goose's plugin is witnessed: `chock install --selection --client goose` no longer warns "Untested" or asks for
  evidence.** In goose 1.55.0 on Windows 11, chock's plugin refused `block-no-verify` on a `git commit --no-verify`
  shell command before it ran and `pin-github-actions` on a workflow write at the write, while `git status` ran
  (org-plan `witness/results/witness-goose-2026-10-18.md`). That held only with Git for Windows' `sh` on PATH: goose
  runs every hook with `sh -c`, and without `sh` it denied every tool call (`on_failure: block`). The goose install
  output now warns about this on Windows.
- **`chock install --client grok` no longer asks for evidence.** Grok's plugin is witnessed (org-plan
  `witness/results/witness-grok-2026-10-17.md` and `witness-grok-claude-plugin-2026-10-17.md`), so the "Evidence
  wanted ... agentseam#188" warning is gone, as for Codex, Cursor, Copilot and Devin. The fail-open warning stays.
- **Grok's plugin is witnessed: `chock install --selection --client grok` no longer warns "Untested".** In Grok Build
  1.0.62 on Windows 11, a chock plugin installed with `grok plugin install --trust` (no hook trust prompt) and enabled
  under Grok's generated name refused `block-no-verify` on a `git commit --no-verify` shell command before it ran
  (org-plan `witness/results/witness-grok-2026-10-17.md`). The ledger row is keyed `grok` and covers the guard only:
  `pin-github-actions` is advisory on Grok and the workflow write landed, as labelled, so no gate refusal is claimed.
  Grok still warns that its hooks fail open, and the agentseam evidence issue stays linked.
- **Guards learn whether the client can prompt (`CHOCK_CAN_ASK`).** A guard run by a vendored hook
  runtime now sees `CHOCK_CAN_ASK=1` when the event that fired turns an ask (exit 3) into a prompt, and
  `0` when it turns it into a block or the runtime cannot name the event: 1 at Claude Code, Copilot and
  Gemini CLI pre-tool and Cursor `beforeShellExecution`; 0 at Cursor `preToolUse`, Codex, Devin, Grok,
  Tabnine and Windsurf. It is unset everywhere else (eval replay, direct calls) and never inherited from
  the caller's environment; a guard treats unset as "can ask". Opt-in: no guard reads it yet, so no
  verdict changes.
- **A guard's exit-1 refusal stays a deny when it echoes command text:** a crash is now recognised only from the
  interpreter's own opening line (a traceback, a `File "...", line N` syntax error, bash's `<script>: line N: syntax
  error`) or from no output, never from words elsewhere in the output. Changes the vendored runtime: a person runs
  `chock sync` to render it.
- **Hardening: the bash probe takes the guard path as an argument.** `find_bash` no longer builds the guard's path
  into the shell string it runs, so a path holding shell syntax is probed as plain text.
- **Hardening: a protected path is protected in any letter case on macOS and Windows.** The write gate, the MCP
  gateway's path check and the outside-repository globs now match forbidden-path patterns and scope globs
  without regard to case on those platforms, so a protected file that does not exist yet is covered as well.
- **Hardening: the rendered runtime no longer depends on the Python patch release.** Python 3.12.0 to 3.12.x
  `ast.unparse` writes same-quote nested f-strings that are a SyntaxError on 3.11; the renderer now lowers any
  f-string holding a string literal to plain `''.join([...])` source, so the runtime is byte-identical and
  parses on 3.11 whichever supported interpreter renders it.
- **Hardening: an `off` in `.chock/guardrails.json` or `~/.chock/guardrails.json` is honoured only by a session that
  started after that file's record last changed.** A merged plugin binds each session, by the session id the session
  log keeps (else the conversation id), to the toggle files and records it first sees; if one changes during the
  session, every member stays on for the rest of it with a one-line warning, and the change applies from the next
  session. Where the client documents a session-start event, the plugin's session-start hook binds the session and
  lists every member that is off, by scope; a compaction does not rebind. The Stop-time check also refuses a turn's
  end while a file changed during the session switches a member off. A client that sends no session id honours an
  `off` only after a session start. The built-in protect member stays non-toggleable. docs/custom-policies.md and the
  "customize guardrails" skill state that a toggle is not a security boundary against an agent running as the person.
  The built-in protection also refuses an agent's write to a session's binding (`guardrails-session-*.json` under
  `.chock/state/`), by shell or Edit/Write.
- **Hardening: a hook command refuses a word a shell would read.** `hook_command` accepts plain words and
  double-quoted paths without `"`, `$`, a backtick, a backslash or a line break; any other word raises
  instead of being joined into the command line.
- **The engine's time limits now always fire before the client's hook timeout, on every hook path.** A client's
  hook timeout fails OPEN (the command runs); chock's own limits ask a person or deny. One budget,
  `ENGINE_BUDGET_SECONDS` (30 s), is now shared by the guard, the write gate, tool-call scripts and script gates,
  and one hook invocation spends it once: the bash probes, `git status` and the gate runner each get what is
  left, where a turn's end could take 30 s of `git status` then 30 s of gate (60 s) against a 45 s client
  timeout. A `git status` that does not finish at Stop now refuses with a reason on stderr, instead of reading as
  a clean worktree and allowing. The emitted timeout is the budget plus a 15 s start-up margin (45 s), in each
  client's own unit, and now also reaches the in-agent entries of Antigravity, Codex, Devin, Gemini CLI (45000 ms),
  Grok and Tabnine (45000 ms), which carried no key and ran on the client's default (Grok 5 s, Antigravity 30 s,
  Gemini 60 s, Codex 600 s). Windsurf's documented hook entry has no timeout field, so it still runs on its own
  undocumented default. Plugin packages (Claude Code, Codex, Copilot, Cursor, Devin) always carried the key. Run
  `chock sync` to rewrite installed hook configs.
  A `git status` that fails for any other reason at Stop (exit 128 "dubious ownership", git missing from PATH) now
  refuses with that reason too, where it used to read as a clean worktree and allow; only "not a git repository"
  still reads as empty. Timeout messages now report the time the call was actually allowed, not the full budget.
- **`chock incident`** prints an ordered, redacted timeline of the local decision log for a window
  (`--since`, `--until`, both routes, rotated files included): sessions, actors, policies fired,
  verdicts, target fingerprints, stops, resumes and overrides, with each hash-chain break and
  unreadable line shown in place and a per-log chain line. Plain allowed calls are counted per
  session. `--format text|md|json`; text and Markdown are terminal-inert. The approver's email is
  shown locally; `--share` leaves out `approver` and `who`. It is evidence for a report, never a report,
  and sends nothing.
- **A finding can no longer drive the terminal or the CI log through the gate's own output.** The vendored gate
  runtime's commit-time and ask refusals on stderr, its `::error`/`::warning` workflow commands and its step
  summary now apply the same rule as `chock.display.inert`: ANSI/OSC escapes (OSC 8 links, OSC 52 clipboard),
  BEL, C0/C1 controls, lone surrogates, line and paragraph separators, bidi overrides and isolates and invisible
  format characters are shown as visible escapes (ESC as `\x1b`), and a newline inside a path or finding shows
  as `\n` instead of starting a forged line. A script's own multi-line message keeps its lines; workflow-command
  data still encodes `%`, CR and LF. Verdicts, exit codes and the decision log are unchanged.
- **A logged string can no longer drive the terminal or fake a record.** `chock status --only log` (text, `--by`,
  `--format md`), `chock status --summary`, `chock doctor`, `chock witness export`'s printed lines, `chock check
  --history` paths and SARIF message text now pass every logged or repo-derived string through one sanitiser,
  `chock.display.inert`: ANSI/OSC escapes (OSC 8 links, OSC 52 clipboard), BEL, backspace, CR, C1 controls, bidi
  overrides and invisible format characters are shown as visible escapes (`\x1b`, `\u202e`), and a newline inside
  a value shows as `\n` instead of starting a forged line. Other languages pass unchanged. The log itself is not
  changed; `--follow` and `--json` stay JSON.
- **`chock install` offers the Claude Code plugin where another agent was witnessed running it.**
  `chock install --client <agent>` prints an "Also works: the Claude Code plugin" block, with that agent's
  steps for the `--client claude-code` build, only where agentseam's `loads_claude_plugins` records a
  witnessed refusal: Grok and Codex (guard and gate refused), Copilot CLI (marketplace route), VS Code
  (Chat panel only) and Devin (turn end only; its own chock plugin is the better install).
  `--client claude-code` lists those agents. Cursor is never offered: its third-party import called the
  hooks but nothing was refused. Each block warns against installing both builds (double checks), that
  such events are logged as `claude_code`, and, for Copilot, how to remove the `chock-local` marketplace
  name chock's Copilot build already registered. agentseam is pinned to main 683f95b.
- **`chock install --client openhands` (untested in OpenHands).** OpenHands gets `.plugin/plugin.json`
  plus `hooks/hooks.json`, staged in `~/.chock/marketplace/openhands/` for `openhands --plugin <path>`;
  OpenHands documents no plugin-root variable, so its hook commands name the folder by absolute path.
  chock's Claude package is not reused for OpenHands: its matchers never match OpenHands' `terminal` or
  `file_editor` and its runtime lets an OpenHands `rm -rf /` through (measured in
  `tests/test_plugin_install_targets_openhands.py`). Its warnings link its agentseam evidence issue.
  `chock plugin build --format openhands` builds the same package per policy.
- **An installed Antigravity `plugin.json` no longer carries `keywords`.** The per-member manifest
  `chock install` writes added an empty `keywords` list to every client's manifest, which Antigravity's
  closed manifest schema refuses; it is now kept only where the client's manifest has one.
- **`chock install --client goose|grok|antigravity` (untested in each client).** goose gets a manifest-less
  user plugin in `~/.agents/plugins/<name>/` with `hooks/hooks.json` and `on_failure: block` on every entry;
  grok gets a manifest-less plugin staged in `~/.chock/marketplace/grok/` for `grok plugin install <path>
  --trust`, and the install prints the enable step instead of editing grok's config; Antigravity gets
  `plugin.json` (`name`, `description`) plus `hooks.json` for `agy plugin install <path>`. Antigravity
  documents no plugin-root variable, so its hook commands name the installed folder by absolute path. The
  hook documents are agentseam's rendering; the folder layouts are chock's own record, with the vendor
  pages they were read from (`src/chock/plugin/data/stores/`), until agentseam's packaging data covers
  these agents. Labels come from agentseam's tier table, an ask gate is labelled not enforced where the
  client cannot prompt, and each client's warnings link its agentseam "evidence wanted" issue.
  `chock plugin build --format goose|grok|antigravity` builds the same packages per policy.
- **An unreadable Stop payload is refused in Antigravity's Stop grammar.** Antigravity names no event, so
  the refusal was rendered in the pre-tool grammar (`deny`), which an Antigravity Stop reads as allow. The
  runtime now answers an unreadable Stop with `continue`, from the vendor's required Stop field
  (`src/chock/data/shape_events.json`), kept only when agentseam parses it as a Stop. This also covers
  `chock sync`'s Antigravity Stop gate.
- **The guardrails toggle lookup reads goose's `working_dir` and Antigravity's `workspacePaths`.** It read
  only `cwd` and `workspace_roots`, so in those clients it looked from the hook's own working directory.
- **`chock install --client kimi-code|factory-droid` (untested in each client).** Kimi Code gets
  `kimi.plugin.json` (`name`, `version`, `description`, `skills: ./skills/`) whose `hooks` array carries
  the hook rules, staged in `~/.chock/marketplace/kimi-code/`; Kimi installs plugins from its TUI only, so
  chock prints the `/plugins install <path>` and `/reload` steps and runs nothing. Its hooks reach the
  scripts by `${KIMI_PLUGIN_ROOT}`, the variable the vendor documents, and carry chock's 45 s `timeout`
  (Kimi's default is 30 s, below the engine's own budget). Factory Droid gets `.factory-plugin/plugin.json`
  plus `hooks/hooks.json` (`${DROID_PLUGIN_ROOT}`), wrapped in a local marketplace
  `~/.chock/marketplace/factory-droid/chock-local/` with `.factory-plugin/marketplace.json`, for
  `droid plugin marketplace add <path>` then `droid plugin install <plugin>@chock-local --scope project`
  (run with `--apply` where `droid` is on PATH). Nothing is published. Labels come from agentseam's tier
  table: an ask is not enforced in either client. Each client's warnings link its agentseam evidence
  issue (#135, #184). `chock plugin build --format kimi|droid` builds the same packages per policy.
- **`chock install` builds your own policies beside catalog ones (`from: local`).** Install contains each path in
  the selection file's folder (no `..`, no symbolic links, text files only), hashes a snapshot, checks a pinned
  `sha256`, runs `chock check --only validate`, prints every file with its id, hash and the label "custom, not
  reviewed", and asks. The evals run only after you accept, because they execute the policy's code. Without a
  terminal, `--trust-local <id>=<sha256>` accepts exactly that hash; there is no `--yes`. The install marker is
  versioned (engine version and commit, accepted local hashes): an unchanged hash prints one line, a changed one
  asks again. Custom members are labelled "custom, not reviewed" in install's output, `chock bundle status` and the
  "customize guardrails" skill. The built-in self-protection in every merged plugin refuses an agent's
  `chock install --trust-local` (any spelling) and its write to an install marker (`chock.selection.json`), so an
  agent cannot accept its own code; `--trust-local` takes no abbreviation.
- **`chock new policy <id> --kind {content_regex,guard,script,rule,skill}`** writes a template that validates and
  passes its own evals; outside a catalog the id gains `my-`.
- **SEC-5's own remedy now validates.** `ambient_override: true` with an `ambient_override_reason` is in the
  manifest schema, so a sandbox-tier rule passes without claiming review.
- **`chock install --marketplace-name <name>` names the build's local marketplace.** Without it nothing changes
  (`chock-local`). A team's own build, for example `--marketplace-name acme-chock`, installs as
  `chock-guardrails@acme-chock` beside a personal `chock-guardrails@chock-local`, so adding the team folder no longer
  re-points the shared `chock-local` registration and every plugin installed from it. The marketplace file, the next
  steps, `--apply`, the removal steps and the Copilot CLI "already registered" note all use the chosen name. The name
  is lowercase letters, digits and single hyphens (at most 64); anything else is refused, and so is rebuilding a
  folder under a different name than it was built with.
- **`chock install` prints "To remove it:" after the install steps.** The agent's own plugin removal, then deleting the
  build folder (`chock bundle status` lists a build for as long as its folder exists), then the shared `chock-local`
  marketplace, only when no other chock build for that agent is still installed. Codex, Antigravity and Kimi Code print
  none yet: their remove command is not confirmed. `chock bundle status` still reads the build folders only; it cannot
  tell that an agent has uninstalled a build.
- **`chock install --selection` builds for any of the five agents: selection schema 2 and `--client`.**
  `selection.schema.json` now defines schema 2: `client` (claude-code, cursor, codex, copilot, devin),
  `bundle: {name (default chock-guardrails), version}`, and entries `{from: catalog, id, version, sha256}` or
  `{from: local, id, path, sha256?, version?}` (id must start `my-`, the prefix reserved for custom policies;
  path relative to the selection file, with no `..`, backslash, drive letter or leading `/`). A local entry is valid
  in the schema but refused at install as not yet supported.
  Schema 1 is still read and is mapped to schema 2 (bundle `chock-guardrails` 1.0.0, same version digest).
  `--client` overrides the selection's client. Each client has its own default folder
  (`~/.chock/marketplace/<client>`; Cursor `~/.cursor/plugins/local/<bundle.name>`), its own layout
  (a marketplace for Claude Code, Copilot and Codex; a plugin folder for Cursor and Devin), its own index (Codex:
  `.agents/plugins/marketplace.json`), its own steps (`--apply` runs only the client's commands, only when its
  binary is on PATH, and never edits a client's settings), label qualifiers (Codex: until its hooks are trusted;
  Devin: best-effort, fails open; Copilot and Devin: a gate judges at turn end only) and `client` warnings. Only
  Claude Code has been witnessed; the others are labelled untested. The plugin's name is `bundle.name` and its
  version `<bundle.version>+<digest12>`, so several bundles coexist per client, a second client never replaces
  the first, and install warns when a picked policy is already in another chock plugin for that client.
- **Breaking: the `bundles.yaml` route is retired.** `chock plugin build` no longer reads `bundles.yaml` or
  takes `--bundles`, writes no `chock-bundles.json`, and Claude bundles are no longer a `dependencies`
  meta-plugin: a bundle is a selection, built as one merged plugin by `chock install --selection`. Per-policy
  `chock plugin build` output is unchanged; a previously built bundle directory under `--out-dir` is now stale.
- **`chock install --selection` builds a chock.sh selection into one Claude Code plugin.** It takes a
  `chock.selection.yaml`, a URL whose `#s=` fragment carries the selection, or the bare code, checks it against
  the new `selection.schema.json` (schema 1, `client: claude-code` only), fetches the catalog at the pinned
  40-hex commit with `chock add`'s fetch code, and refuses a policy whose id is missing, whose version differs
  from `registry.yaml`, or whose sha256 differs (the `chock add --verify-sha` hash). The policies are merged into
  one plugin, `chock-guardrails`, in a local marketplace (`~/.chock/marketplace`, or `--dest`). It labels each
  policy on its own (what it does, and blocks, asks, warns or advisory on Claude Code; no aggregate grade, and
  the plugin's description carries none either), prints the selection warnings (twins, duplicates,
  allowlist-first policies, observe and advisory policies; data in `chock/install/data/warnings.json`) and the
  two `claude plugin` commands; `--apply` runs them. A re-run rebuilds beside the old directory and swaps it in.
- **Security: a selection cannot choose where its code comes from.** `chock install` refuses a
  `catalog.source` other than the official chock-catalog unless the user passes `--allow-source <exact source>`,
  and refuses a `catalog.ref` that is not on the source's `main` branch (a commit served only by a fork). The
  source and ref are printed before anything is fetched.
- **Installed content is what `verify` says it is.** `chock add` and `chock verify` refuse a pack that
  ships `__pycache__` or `.pyc`/`.pyo` (build artifacts, never catalog content), and policy scripts now
  run with `PYTHONDONTWRITEBYTECODE=1`, so running a gate no longer leaves bytecode in the pack. Each
  vendored runtime entry now hashes the shared runtime's bytes before executing them and compares that to
  its pin, instead of trusting a digest the file declares about itself. The agent-event runner exits 2 on
  stdin that is not UTF-8 instead of judging text with replacement characters. Run `chock sync` to
  refresh `.chock/bin`.
- **Hardening: the remaining hook installers write through no link.** The generic, owned-file and session-start
  installers now refuse a symlink or non-regular file anywhere on a hook config's path, as the Claude and Cursor
  installer already did, and replace the file atomically (mode 0600) instead of writing through the path.
- **Decision logging with levels, on both routes.** Every hook now logs one line per decision at a
  level a person sets: `off`, `info` (the default: blocks, asks, warns, guard faults and overrides)
  or `debug` (every call, allows included, plus a redacted, capped trace; never file contents).
  Allows are no longer written at `info`. The plugin route (`chock install`), which logged nowhere,
  writes one file per client, `~/.chock/log/<agent>/events.jsonl`, shared by every plugin there (each
  line names its `plugin`; single-append lines, rotation under a lock); the sync route keeps
  `.chock/log/gate-events.jsonl`.
  Level and rotation size (`max_bytes`, default 1 MiB, 64 KiB to 1 GiB) come from `CHOCK_LOG_LEVEL`,
  then `.chock/chock-log.json`, then `~/.chock/chock-log.json`; `CHOCK_GATE_LOG=0` is a deprecated
  alias for `off`. Every bundle refuses an agent's write to either settings file. `chock status --only log`
  reads both routes and adds `--route`, `--level`, `--verdict`, `--plugin` and `--follow`. See
  [Decision log](docs/decision-log.md).
- **`chock marketplace build` writes `llms.txt` and `.github/ISSUE_TEMPLATE/config.yml`.** A plugin
  repo is rebuilt from chock-catalog, so an issue filed there cannot be fixed there and it had no
  machine-readable summary. The build now emits an `llms.txt` (one line per published plugin, its
  posture in this client and its catalog page) and an issue config that disables blank issues and
  routes policy issues to chock-catalog, build bugs to chock and vulnerabilities to chock's private
  advisory route. `--check` reports either file missing or hand-edited. The devin tree's file says
  best-effort, never enforces.
- **`chock doctor` and a session-start heartbeat.** `chock doctor [--client X] [--repo .]` checks
  each client's hooks on the sync and plugin routes: the hooks file runs chock's runtime, the
  launcher and a Python 3.11+ are there, the runtime is the one the installed chock builds (and a
  plugin's recorded engine version and commit match), Codex-style trust, the client version
  against agentseam's witnessed ones, and when each hook surface last fired. Each line is PASS,
  WARN, FAIL or INFO with a one-line fix; it reads only, never runs a client and never uses the
  network. Where a client documents a session-start event, `chock sync` and `chock install` now
  wire a heartbeat hook that writes one `session_start` line per session at `info`; it never
  blocks. Clients without one are listed as "no heartbeat available".
- **Decision-log summary and evidence export.** `chock status --summary` reports fires per policy and
  per client, block/ask/warn/fault rates, p50/p95 hook latency with a WARN when p95 is within 25% of
  the client's hook timeout (a timeout fails open), the top guard faults, and heartbeat gaps (hook
  records with no `session_start`, and `session_start` records with no hook record). `chock witness
  export --client <c>` writes that client's records, redacted, to a local file in the shape agentseam
  evidence reports ask for, and prints the client's "evidence wanted" issue; it never uploads. See
  [Decision log](docs/decision-log.md#summary).
- **A repo-scope `off` the guard does not honour is no longer reported as off.** The session-start notice now lists an
  `off` that HEAD's copy of the toggle file does not hold as staying on until that change is committed, as
  `chock bundle status` already did, and `chock bundle off` at repo scope ends with a line saying the change applies
  only once the file is committed and from the next session. User scope is unchanged.
- **The `optimize` skill reads the decision log and witness exports as traces.** Its new
  `scripts/traces.py` (stdlib only) reads `.chock/log` JSONL lines and `chock witness export` files and
  groups misfire candidates per policy: a refusal a person later overrode with `CHOCK_ALLOW`. A stop's
  records (`reason: stopped`, `chock-stop`) and plain allowed calls never count toward a policy, and no
  approver's email is copied out. Malformed input exits 2 with one line naming the file and line.
- **A pack hashes the same on every platform and every checkout.** `compute_pack_hash` orders files by
  their posix-relative name as a string; sorting `Path` objects compared case-insensitively on Windows,
  so a pack holding `LICENSE` beside `hooks/` (catalog `base/java-security`, `base/review-like-a-red-team`)
  hashed differently there and `chock install` refused it. A local `--from <dir>` source with no `--ref`
  is now read as a clone reads it: a git checkout is cloned at its HEAD (uncommitted edits are left
  out and the commit is recorded as `source_commit`), a plain directory is copied with its text files
  normalised to LF. Every git call chock runs for a fetch sets `core.autocrlf=false` and
  `core.eol=lf`, so a clone under Windows' usual `core.autocrlf=true` no longer flips a pack to CRLF.
  The `chock add` unpinned hint names the commit to pin instead of calling it "the default branch".
- **Pack hash v2 (length-prefixed, domain-separated).** file names and contents are length-prefixed under a domain prefix, so a NUL byte in a file can no longer make two packs share a hash. Every writer (`chock.lock`, `chock-market.lock`, `chock add`, local installs) writes v2 and `chock.lock` is `lockfile_version` 2. A v1 hash is still accepted by `--verify-sha`, selection pins, `--trust-local`, `chock.lock` and marketplace locks, but only while no file in the pack holds a NUL byte; catalog provenance (`source_commit`) is kept when the old hash matches under v1. v1 acceptance lasts all of 1.x and ends in 2.0. Run `chock sync` to rewrite a lockfile as v2.
- **A gate's pattern judge says when it is ready:** its child interpreter's start-up (up to 10 s) is no longer
  counted against the 10 s a pattern gets, so a slow start is not reported as a catastrophic pattern. Changes the
  vendored runtime: a person runs `chock sync` to render it.
- Hardening: release and CI builds use the hash-pinned `setuptools` from `requirements/` with
  `--no-build-isolation`; a test fails if a workflow builds or editable-installs with isolation.
- **Hardening: `chock plugin build` in place refuses a symlink under the policy tree.** The build no longer
  writes through a link at any path it generates; it stops with an error naming the link and writes nothing.
- **Fix: a plugin's guard ships everything it imports or reads, and a script gate is never wired as a command guard.** A built guard now carries the whole of its policy's `implementations/` folder (flat helper modules, sub-packages and `data/` tables) beside it, so eight catalog guards no longer crash on every shell command in all five clients' plugins (Claude Code, Cursor and Copilot prompted on each command; Codex and Devin refused each one). A policy whose `<id>.py` is its JSON-in script gate (`hook.gate.kind: script`) no longer gets that file wired as a shell guard. `tests/test_plugin_builds_run.py` builds policies in every client format and runs every built hook on a benign command, write and turn end; set `CHOCK_CATALOG_DIR` to run it over the whole catalog.
- **A plugin package ships a policy's shell guard AND its tool_use gate when the policy has both.**
  A guard used to displace the gate in every store (`claude`, `codex`, `copilot`, `cursor`,
  `devin`), so a plugin-only install of a policy like protect-agent-config refused a shell write to
  a protected path and let an Edit or Write to the same path through, while its description and
  skill called the policy enforced. Each half now ships where the client runs it: one hooks file
  wires the guard (`--guard`) and the gate (`--gate`, plus `--stop` where the turn's end blocks),
  matching what `chock sync` installs in a repo. A gate the client cannot run is neither shipped
  nor claimed. The description states both halves' fail conditions (`Shell guard: ... Write gate:
  ...`), the skill note names both, a bundle member's line and the catalog page count each half,
  and a Stop-only gate beside a guard never reads as judging the write. Two halves that would
  write different bytes to one package path, or disagree on a hooks setting, refuse to package.
  A policy with one half packages byte for byte as before. `chock plugin build --check` reports a
  tree built before this change as stale; rebuild published plugin trees after updating chock.
- **Plugins carry the repo stop's own check.** Every `chock install` bundle and every hook-carrying
  `chock plugin build` package, in every client format (Claude Code, Codex, Copilot, Cursor, Devin, goose,
  Grok, Antigravity, Gemini CLI, OpenHands, Kimi Code, Factory Droid), now runs the runtime with
  `--stop-check` on every tool call, with no matcher and outside a bundle's member toggles, as
  `chock sync` already wires. While `chock stop` reaches the agent, a Read that no installed policy
  matches is refused on the plugin route too. Unstopped, the check allows; each installed package runs
  its own. Advisory-only packages ship no hooks and get none. The plugin repos pick it up at their next
  release.
- **Release: the tag workflow refuses a tag that is off `main` or not `v` + the version.**
  `release.yml`'s guard now also checks that the tagged commit is on `main`. The PyPI job refuses
  unless the build produced exactly that version's sdist and wheel. Each job now declares only
  the permissions it needs (workflow default `{}`). PyPI publishing stays in `release.yml`
  (trusted publisher: workflow `release.yml`, environment `pypi`) with its build-provenance
  attestation.
- **`chock stop` and `chock resume`: a person's stop on agents in one repository.** `chock stop [--agent
  <client>] [--reason ...]` writes .chock/stop.json (scope, reason, who, when); `chock resume` removes it;
  `chock status` shows it on its first line. While it exists, every tool call by an agent in scope is
  refused at Chock's pre-tool hooks, reads included and the Devin hook too, with `stopped: <reason>`, and an
  agent's commit or push is refused at the git hooks; a person's passes. Neither `CHOCK_ALLOW` nor the
  rollout level loosens it, and a file that exists but cannot be read refuses every agent. Each refusal is a
  decision-log line with reason `stopped`; the stop and the resume are logged with who and when. `chock
  init` lists the file in `.gitignore`. Sync wires one matcher-less `--stop-check` hook per client beside chock's
  others, so a stop sees every tool call whatever the policies match. Only a person changes a stop: `chock
  stop` and `chock resume` refuse in a shell with an agent marker. Limits: it reaches only agents whose hooks
  Chock wires (a `chock install` plugin has no stop check); Devin's hook is best-effort and fail-open per the vendor; it refuses the
  next action, ends no running process and revokes no credential. `chock stop` also writes a `0o600` machine
  registry entry under `~/.chock/stops/`: a hook whose client names no project root refuses while any entry is
  in force. Paths are resolved through symlinks and read from anywhere in a call's input; git hooks find the
  stop through `GIT_DIR`, `GIT_WORK_TREE` and the common dir and run only the main checkout's gate.py; a bare
  repository's stop reaches its worktrees; `CHOCK_AGENT_COMMIT=0` clears no agent marker for a stop. `chock
  resume` needs a person at a terminal (stdin and stdout TTYs) who types the repository's name. The hook reads
  each word of a shell command as a path too; it reads no input while no stop is near or registered, and caps
  its read otherwise (past the cap it refuses). Registry entries use the case-folded realpath on macOS and
  Windows. A stop holds against agents in the stopped scope. An agent running unstopped elsewhere on the same machine, with a shell, can remove the stop (for example by deleting the files); the hook and protect-agent-config refuse the common forms, not every one. Installing the git hooks writes `.chock/bin/gate.py` when it is
  missing, so a person's commit passes while a stop is in force in a repository with no policy.
- **A `CHOCK_ALLOW` override names its approver.** The override's log line carries `approver`, the git
  `user.email` of the person's shell, beside its `policy_id`. It stays in the local `0o600` log: `chock
  witness export` leaves it out, and Chock sends nothing.
- **`chock install --client gemini-cli` is retired: use `--client antigravity`.** Google replaced Gemini CLI
  with Antigravity CLI for unpaid and Google One users (2026-06-18), and Gemini CLI is not optimized for
  Gemini 4 Argon, so chock no longer builds a Gemini CLI extension. `--client gemini-cli`, or a selection
  naming it, exits 1 with one line pointing to `--client antigravity`; `chock plugin build --format gemini` is
  gone. `chock sync` still wires Gemini CLI's repo hooks (`.gemini/settings.json`) for paid users who run it.
- **Hardening: `chock review` defines checks from the base only.** With a base ref, the built-in checks and
  the checks the base's `.chock/config.yaml` declares are the whole registry. A check a pull request adds
  to its own config, or a built-in it redefines there, is neither run nor part of `command_set_hash`.
  A check a pull request both adds and requires is not required of that pull request: `chock review require`
  prints that it is required from the merge on. Without a base ref the working tree still defines.
- **`chock review emit|verify|require` print evidence-derived text inert** (attestation fields, producer id,
  failure strings), so contributor-written evidence cannot move the cursor or fake a verdict line in a terminal or CI log.
- **One shared runtime beside the per-agent entries.** `chock sync` writes `.chock/bin/_chock_runtime.py`, the
  stdlib-only guard logic every `.chock/bin/<agent>.py` loads from its own folder, and each entry shrinks to
  its vendor's adapter and dispatch. Plugin packages (`chock plugin build`, `chock install`) ship it beside
  their entry. The module is bytecode-cached, so the hook no longer recompiles about 3,400 lines on every
  call. An entry refuses every call, in its client's own grammar, when the shared runtime is missing,
  unreadable, fails to import or carries another version's digest; it never allows. Verdicts are unchanged.
- **Internal: the gate runner is a package, `chock.gate.runner`, no longer one 1,482-line file.**
  Ten modules (constants, context, actor, kinds, script, log, material, report, verdict, cli), each
  under 300 lines and with no import cycle. Every public name, and the private helpers chock's own
  code reads, is re-exported, so `from chock.gate.runner import ...` keeps working (the other private
  helpers and stdlib imports now live only in their module); `python -m chock.gate.runner` still runs
  the command line. The vendored `.chock/bin/gate.py` stays
  one stdlib-only file: `chock.gate.assemble` builds it from a prelude and the modules' numbered
  fragments, refuses to build if a declared module or fragment is missing, and its output is
  byte-identical to the old `runner.py`. No change to what any gate decides.
- The vendored runtime renders byte-identically on every supported Python. Five f-strings whose replacement fields held
  quoted strings were printed with different quotes by `ast.unparse` on Python 3.12.3 than on 3.12.13, so `chock sync`
  on one patch level failed `sync --check` on another. They are rewritten, so the next `chock sync` rewrites `.chock/bin`
  once.
- **The workflow `chock sync --ci` installs refuses a pull request that weakens the policy set.** A
  new step runs `chock check --only baseline --base "origin/$BASE_REF"` on `pull_request`, before the
  compiled gates, with the base branch passed through `env:` (never `${{ }}` in shell text) and read
  from the checkout's full history (`fetch-depth: 0`); a base that does not resolve fails the step.
  chock's own CI already ran it; adopters now get it on their next `chock sync --ci`. A
  `pull_request` run uses the pull request's own copy of the workflow, so a pull request that also
  deletes the step is not caught by it; nothing yet checks the installed workflow against the template.
- **The write-path door of a shell guard or an event script is declared and validated (DET-6).**
  `hook.script` runs only from the git hook, so it keeps its `commit`/`push`/`commit-msg` events;
  the Edit/Write door is a `hook.gate` with `tool_use` in `on` -- `kind: script` for logic, or a
  path gate (`content_regex`, `forbidden_path_regex`, `content_pattern: '(?!)'`) as
  protect-agent-config ships. New `manifest_write_path` errors: a `hook.script` event outside the
  git events (the message names both gate forms), a `'(?!)'` gate with no path (it can never
  refuse), and a guard's path gate without `tool_use`. The validator no longer crashes with a
  `KeyError` on `hook.script.on: [tool_use]`. Schema descriptions and `spec/script-backed-gates.md`
  state the pairing.
- **The per-session tool-call log redacts what it stores:** a command's first line and a path pass through the same
  scan-secrets redaction as the decision log, and URL userinfo inside a command is removed. `.chock/state` is created
  owner-only (the log files already were). Changes the vendored runtime: a person runs `chock sync` to render it.
- **`chock status` prints the policy table inert:** ids, states and coverage cells read from the repo can no longer
  move the cursor, recolour or fake a row on a terminal.
- **Command output no longer crashes on a character the stream cannot encode.** `chock check` on a
  Windows runner (stdout cp1252) raised `UnicodeEncodeError` on U+FFFD while printing eval results. The
  stdout wrapper now retries with `backslashreplace` in the stream's encoding; text the encoding can
  represent prints unchanged.
- **`chock stop --everywhere`: one stop for every agent on the machine.** It writes
  `~/.chock/stops/_everywhere.json`, and while it exists every Chock hook refuses every tool call, in every
  repository and session: the sync hooks, every plugin's `--stop-check`, the MCP gateway, and an agent's commit
  or push at the git hooks. An unreadable, corrupt or non-regular file refuses too. `chock resume --everywhere`
  is person-only (no agent shell, a TTY, the typed word `everywhere`) and lifts no per-repository stop.
  `chock status` and `chock doctor` show it; inside a repository both commands log with `"everywhere": true`.
- **A fresh clone arms itself again, from what is committed: `chock sync --committed`.** Since `chock sync` became
  person-only, the SessionStart hook could not arm a clone from inside an agent's session. `--committed` takes only
  `--repo`, runs under an agent marker, and refuses (the same person-only message, naming the file) when
  `.chock/config.yaml`, `chock.lock` or anything under `.agents/policies` differs from HEAD or HEAD cannot be read;
  otherwise it is the normal recompile. Every other `sync` form stays person-only. The SessionStart arm calls it;
  the AGENTS.md pointer block, README and docs now say a person runs `chock sync` to change what is enforced.
- **`chock sync` wires Factory Droid, goose, OpenHands and Mistral Vibe.** The agent list comes from
  agentseam's adapter registry: every adapter is a valid `supported_agents` name (`factory-droid`, `goose`,
  `openhands`, `mistral-vibe`, `cline`), and every one whose hook config sits in the repository as JSON or TOML
  gets its hook entries and a `.chock/bin/<agent>.py` runtime. Vibe's rules go in one owned block in
  `.vibe/hooks.toml`; goose's go in `.agents/plugins/chock/hooks/hooks.json`. Each answers in its own
  grammar; none can prompt, so an ask is a refusal there and `CHOCK_CAN_ASK` is 0. Cline (one executable per
  event) and Junie and Kimi Code (home-directory config) are selectable but not yet wired.
- **Sync prints each wired agent's pre-tool row from agentseam's tier table**, with its basis and date, and
  says "Untested" for an agent chock has no live witness of.
- **agentseam is pinned to main commit bebbfa6** as a direct reference until its next release.
- **Hardening: `chock sync` refuses an agent config that is a symlink.** Writing hooks into
  `.claude/settings.json` and the other merged vendor configs now goes through the same no-follow writer as
  the MCP registration: a link at the file or any directory above it stops the sync, and nothing is written.
  The merged config file is now written with owner-only permissions.
- **Canonical tagline: "A kill switch for your coding agent's wrong moves."** It replaces the old
  "guardrails" / "governance-as-code" lines in the README (tagline, hero alt, and the sub-line "Chock kills
  that action, nothing else: no suggestions, no rewrites."), `llms.txt`, the PyPI summary
  (`[project].description`), the CITATION.cff abstract, the chock and org social banners, and the generated
  marketplace description. The Devin marketplace description reads "A best-effort kill switch for your
  Devin agent's wrong moves."
- **Tagline: "Blocks your coding agent's wrong moves before they land."** It replaces "A kill switch for
  your coding agent's wrong moves.", since Chock blocks one action and never stops the agent. Changed in the
  README (tagline, hero alt; the sub-line now reads "Chock blocks that action"), `llms.txt`, the PyPI
  summary, the CITATION.cff abstract, the chock and org social banners, and the generated marketplace
  description. The Devin marketplace description reads "Blocks your Devin agent's wrong moves before they
  merge."
- **Devin marketplace description now reads "Blocks your Devin agent's wrong moves before they land."**
  Devin has hooks, so its description takes the standard tagline form in place of "before they merge."
- **A deleted guardrails toggle file no longer refuses a turn end (Codex witness, 2026-10-07).** An absent
  `.chock/guardrails.json` means every member is on, so deleting it only tightens. The turn-end check now
  passes it and drops the stale record; `chock bundle status` still reports it. Deleting the repository file
  still refuses when the user file that then governs switches a member off or has no record. A file changed,
  created with no record, unreadable or a link still refuses.
- **The turn-end checks judge every workspace root.** A Stop that names several `workspace_roots` (Cursor)
  checks the payload's `cwd` and every root inside a repository, one per repository, and reports each
  root's findings under its own name. They checked only the first root.
- **`chock status --verify-log` prints every log-derived value inert** (break fields, chain start, folder labels, the
  confirmed label), and `--head` accepts `<seq>:<sha256>@<log>` to confirm a kept head only in the log it came from.
  The printed head now carries its log and says a head needs keeping outside anything the log's writer can write.
- **Policy labels, install warnings and witness notes now use short plain sentences (VOICE-3a).** The grade text
  that `chock install` prints and the catalog's registry reads no longer chains clauses with semicolons, and no
  longer says "judged" or "fails open". A gate that runs only at turn end now reads "blocks at turn end only. It
  does not check a file write when it happens". Devin's label and the labels of clients graded from agentseam's
  tier table say "a hook error lets the action through" where they said "fails open" or "fail mode open". No
  label claims more than before, and every caveat is kept. Code that matches the old wording, such as the
  catalog's `tools/label_honesty.py`, needs the new text.
- **`chock validate` no longer warns on the `my-` prefix `chock new` adds.** INT-3 (verb-first
  ids) took `my` as the first word of every policy scaffolded outside a catalog, so
  `my-block-marker` warned "does not start with a verb". It now reads the word after the
  prefix: `my-block-marker` passes, `my-tf-destroy` still warns.
- **`chock witness export` re-keys every record's `target` fingerprint** with a random key made for that export and
  discarded, so equal targets still match inside the file but a guessed path or command cannot be confirmed offline.
- **Hardening: repo YAML cannot hang or crash the guidance server or `chock check`.** Only string entries
  of `policies.disabled` are read (an alias-built nested value is no longer stringified), and
  the guidance config's nesting limit is measured on parser events, so compact block nesting is refused
  like bracket and indent nesting.

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
