## What happens when the guard cannot decide

The levels above grade the **outer** boundary: what the client does when chock's hook never
runs or dies outright. There is an inner one too — what the hook says when it *did* run and
could not reach a verdict — and the two answers are not the same. `gate/guard_runner.py`
distinguishes six such causes and answers only one of them with an allow.

| Cause | What chock returns | Why |
| :--- | :--- | :--- |
| The command will not tokenize (unbalanced quotes, trailing backslash, PowerShell quoting) | the guard's own verdict | The guard still runs: argv is a whitespace split (`CHOCK_ARGV_FALLBACK=1`) and `CHOCK_RAW_COMMAND` carries the exact string. `rm -rf / #'` is valid bash and invalid shlex, so a guard that reads the raw command must get the chance to refuse it. |
| The command is empty after tokenizing | allow | There is nothing to check. |
| No bash on the machine can resolve the guard | **ask** | No guard ran. The prompt names the fix: install Git for Windows (it ships bash), or put bash on PATH. |
| The guard the hook names is not on disk | **deny** | The hook config names it, so its absence is a broken install, not nothing to check. The reason says to run `chock sync --repo .`. |
| The guard crashed, exited a code that is none of 0, 1 or 3, or exited 1 with no reason or a traceback / syntax error | **ask** | The control was installed, reachable and runnable, and still produced no answer. (Exit 3 is not this: it is the guard asking on purpose, and its own first line is the prompt. Exit 1 blocks only with a reason on stderr, as `spec/script-backed-gates.md` states.) |
| The guard hit its 30-second timeout | **ask** | Same: the control ran and did not decide. |

A guard that fails refuses or asks; it never reports an allow it never established.

**The engine's time limits always fire before the client's.** A client's hook timeout fails **open** (the command runs); the engine's own limits ask a person or deny. So chock keeps one budget, `ENGINE_BUDGET_SECONDS` (30 s, `gate/budget.py`), per hook invocation: the bash probes, `git status`, the guard, the gate runner and a tool-call script all draw on the same deadline, and each subprocess gets only what is left. A `git status` that does not finish at the turn's end is a refusal, never a clean worktree. The timeout written into the client's hook config is that budget plus a 15 s interpreter start-up margin (`TIMEOUT_SECONDS`, 45 s), in each client's own unit.

| Surface | Clients | Timeout written |
| :--- | :--- | :--- |
| In-agent (`chock sync`: `.claude/`, `.cursor/`, `.codex/`, `.github/hooks/`, ...) | Claude Code, Codex, Copilot, Cursor, Devin, Antigravity, Gemini CLI, Grok, Tabnine | yes, every hook entry |
| In-agent | Windsurf | **no key**: its documented hook entry takes `command`, `powershell`, `show_output` and `working_directory` only, so its own default (not documented) applies |
| Plugin package (`hooks.json`) | Claude Code, Codex, Copilot, Cursor, Devin | yes, every hook entry |

| Client | Field | Unit | Written | Client default when the key is absent |
| :--- | :--- | :--- | :--- | :--- |
| Claude Code, Codex, Devin, Antigravity, Grok | `timeout` | seconds | 45 | Codex 600 s; Devin 600 s (command hooks); Antigravity 30 s; Grok 5 s |
| Gemini CLI, Tabnine | `timeout` | milliseconds | 45000 | 60000 (60 s) both |
| Copilot | `timeout` and `timeoutSec` | seconds | 45 | not checked |
| Cursor | `timeout` (with `failClosed`) | seconds | 45 | not checked |
| Windsurf | none | n/a | n/a | undocumented |

A default below 45 s is exactly the hole this closes: Grok's 5 s and Antigravity's 30 s would end the hook before the engine's own 30 s limit and the command would run unchecked. `tests/test_hook_timeout_budget.py` walks every emitted hooks document and fails on a hook entry that lacks a timeout above the budget, unless its client is in the no-key allow-list (`NO_TIMEOUT_KEY_VENDORS`). Sources are in `src/chock/data/hook_timeouts.json`.

**What an `ask` becomes depends on the client, and no client turns it into a silent allow.**

| Client | Gate chock installs | An `ask` on the wire |
| :--- | :--- | :--- |
| Claude Code | PreToolUse, via the settings fragment `install-hooks` merges | `permissionDecision: "ask"` — prompts the user to confirm |
| VS Code agent mode / Copilot CLI | PreToolUse, via the agent-hooks file | `permissionDecision: "ask"` — forces a confirmation, and overrides the client's own auto-approve |
| Cursor | `beforeShellExecution`, via the Cursor hooks file | `{"permission": "ask"}` — honoured at this gate. Cursor's generic `preToolUse` accepts the value but does not enforce it, which is one reason chock installs the shell gate instead |
| Codex CLI (hand-wired only) | PreToolUse | **deny.** Codex's own parser rejects `ask` as unsupported and then fails open on the response it rejected, so agentseam's adapter degrades it to a deny rather than emit a value that would silently permit the call. A guard broken on every command therefore blocks on Codex where the others prompt |

Each row is cited to vendor source or vendor documentation at a named ref, so a reader can
recheck it rather than take this table's word:

- **Claude Code** — `code.claude.com/docs/en/hooks`, read 2026-08-31, `PreToolUse`
  `hookSpecificOutput` field table: *"`"ask"` prompts the user to confirm."* Claude Code is
  not open source, so this is documentation, not source.
- **VS Code agent mode** — `microsoft/vscode` at
  `718038e170df9c66a15087cebda424d9c7f051ff`,
  `src/vs/workbench/contrib/chat/browser/tools/languageModelToolsService.ts`.
  `resolveAutoConfirmFromHook` (`:877-930`) synthesises a confirmation and sets
  `allowAutoConfirm: false`; `:622-627` carries the comment *"A preToolUse hook that returned
  `ask` explicitly forces a confirmation, so never let `preApproved` override it."*
- **Cursor** — **not verified from a vendor artifact.** The claim rests on agentseam's
  recorded doc-basis verification (2026-08-26), which distinguishes `preToolUse` (accepts
  `ask`, does not enforce it) from `beforeShellExecution` (honours it). Second-hand, and
  labelled as such rather than presented as checked.
- **Codex CLI** — `openai/codex` at `32f48598a0609a882e5847f0d3e35d6d67f375bc`.
  `codex-rs/hooks/src/engine/output_parser.rs:458-460` returns *"PreToolUse hook returned
  unsupported permissionDecision:ask"*; `:144` computes a block reason only when nothing was
  rejected, and `codex-rs/hooks/src/events/pre_tool_use.rs:234-244` sets `should_block` in the
  non-rejected arm alone — so a literal `ask` there would let the call through.

**This raises no coverage grade.** A control is only as strong as its worst degradation, and
the empty command above still allows — so chock's in-agent controls stay at the level the
ladder gives a control that degrades to allowing until that grade is re-derived deliberately.
