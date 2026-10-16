## Levels

| Level | Writes |
| :--- | :--- |
| `off` | nothing |
| `info` (default) | one line each time a policy fires: block, ask, warn, a guard fault, or an override or rollout level that let a finding through; and one line per allowed agent tool call, carrying only its `target` fingerprint. However many policy hooks judge that call, its allow is one line, written at once by the first hook to run and naming no policy (no `policy_id`, `plugin` or match fields): an allowed call is the call's, not any one policy's. A call is known by the client's `tool_use_id`, else by session, second and `target`, so with no id two identical calls in one second are one line. Every block, ask, warn, fault and override keeps its own line per policy |
| `debug` | every hook call (one allow line per policy hook), the turn's end included, plus a `trace`: wire event, tool, matched rule (or "no rule matched"), the guard's exit code, per-stage timings, and the command or path cut to 200 characters with every value the scan-secrets policy would block replaced by `[redacted]` |

`chock status` counts allowed tool calls once each, in total (`allowed_calls`), and never toward a
policy: its per-policy columns show what a policy decided, its blocks, asks, warns and overrides.

Each line carries `ts`, `route`, `level`, `agent`, `client` (when the payload names one), `event`,
`policy_id`, `surface`, `verdict`, `reason`, `duration_ms`, `can_ask`, `actor`, `session_id` (the
client's session id, when the payload carries one) and, on a tool call, `target`. The sync route adds
`chock_version` (left out when the hook's Python has no chock installed). The plugin route adds
`plugin` and `plugin_version` instead, never `chock_version`: a plugin runs its own bundled Python, not chock. On the sync route a compiled gate's line is written by `gate.py`
and keeps its own fields (`kind`, `match_count`, `matches`, `rules`), plus `actor`, and `session_id`
and `target` from the hook that ran it. A git hook's line carries `actor` only: a commit is no tool call.

## Heartbeat

Where the client documents a session-start event, chock wires one more hook there (the runtime,
with no flags) on both routes, and it writes one line per session at `info`:

```json
{"ts": "...", "event": "session_start", "route": "sync", "agent": "codex_cli", "session_id": "...", "chock_version": "0.15.2", "level": "info"}
```

The plugin route's line carries `plugin` and `plugin_version` instead of `chock_version`. The
hook never refuses and never blocks the session; a heartbeat that cannot be written is dropped.
Most clients fail open when a hook crashes or never loads, so a session with no heartbeat is the
sign of a hook that did not run: `chock doctor` reports it. Antigravity, Mistral Vibe and
Windsurf document no session-start event, so they have no heartbeat.

## Settings (a person's, only)

```json
{"level": "debug", "max_bytes": 4194304}
```

One file per scope, both optional, each named `chock-log.json` inside a `.chock` folder:

1. the environment: `CHOCK_LOG_LEVEL=off|info|debug` in the shell the agent client was started from;
2. the repository: `<repo>/.chock/chock-log.json`;
3. the user: `~/.chock/chock-log.json`;
4. the default: `info`, `max_bytes` 1048576 (1 MiB).

The first that sets a value wins. `max_bytes` must be a whole number from 65536 (64 KiB) to
1073741824 (1 GiB); a value outside that range, an unknown level or key, or unreadable JSON is
ignored and named by `chock status --only log`. `CHOCK_GATE_LOG=0` still works: it is a deprecated
alias for `CHOCK_LOG_LEVEL=off`.

An agent cannot change the level. A hook's environment comes from the client, not from the
command an agent writes, so `CHOCK_LOG_LEVEL=off rm -rf build` changes nothing. Every chock bundle
refuses an agent's write to either settings file, raising or lowering, through a shell command (best
effort) or an Edit/Write (`chock-guardrails-protect`). A client with no chock bundle installed has
no such refusal: there the settings files are protected only by whatever policies the repository
itself installs. Edit the file yourself, in your own editor or shell.

Logging never changes a verdict, never raises and never blocks: a line that cannot be written is
dropped silently.

## Reading it

```bash
chock status --only log                       # both routes, per policy
chock status --only log --route plugin --plugin <name> --verdict block --since 7
chock status --only log --level debug --json  # allows included
chock status --only log --follow              # print new lines as they are written
```

## Hash chain

Each line carries `seq`, its place in its file's chain, and `prev`, the sha256 of the line before it
(that line's exact bytes, without the newline). A log's first line names 64 zeros. After a rotation the
new file's first line names the rotated file's last, so the chain runs across both files. Every route
writes through the same journal: runtime hooks, git hooks, the MCP gateway, `chock stop` and
`chock resume`, and overrides.

A writer waits up to one second for the lock. A line it cannot chain (the lock stayed held, or the last
line could not be read) is still written, with `unchained` naming why. A chaining failure never
changes a verdict.

```bash
chock status --verify-log [--route sync|plugin] [--json]   # exit 0 intact, 1 at a break
chock status --verify-log --head <seq>:<sha256>            # confirm a head you kept is still there
```

It walks each log (rotated file first) and reports the first break: the file, the line, and the
expected and found `prev` or `seq`. An edited, deleted, inserted or reordered line breaks the link of
the line after it. History that is missing or rotated away is not a break: the walk reports
`chain starts at <hash> (seq N)`. Lines written before chaining existed are counted, then the chain
starts. A line written after that by a runtime that does not chain yet (until `chock sync` regenerates
it, or the plugin is reinstalled) is a break of kind `unchained`. The break names the line and says why: a runtime without chaining wrote it, or a writer timed out on the
lock. **An intact chain needs every runtime regenerated** (`chock sync`, or reinstalling the plugin) once this
version is installed; until then, lines from older runtimes break it.

What it shows, and what it does not:

- It shows a change made after the fact to someone who kept an earlier head (`seq` and `sha256`, as
  `--verify-log` prints it and `chock witness export` carries it): `--head` fails once that record
  changes, even when every later hash was recomputed.
- It does not stop anyone who can write the file. A local admin, or any process running as you, can
  rewrite the whole file and every hash, and the walk then passes. Without a kept head, the chain
  shows only edits that left the later links alone.
- Deleting the newest lines, or the oldest lines of the oldest file, leaves no break; only a kept head
  shows the first.
- It makes no claim about any regulation or standard.

## Stop and override

While a stop is in force (`chock stop`, [Stop](stop.md)),
each call it refuses is a `block` line with `"reason": "stopped"` and the fields above (`actor`,
`session_id`, `target`). A pre-tool refusal names the hook's policy; a commit or push refused at
the git dispatcher names `chock-stop`. `chock stop` and `chock resume` each write one `chock-stop`
line, event `repo_stop` or `repo_resume`, with `scope`, `who` (git `user.email`) and `when`.
With `--everywhere`, run inside a repository, the line also carries `"everywhere": true`.

A person's `CHOCK_ALLOW` override is an `allow` line with `"override": "CHOCK_ALLOW"`, the
`policy_id` it answered, and `approver`: the git `user.email` of the shell that ran it.

`approver` and `who` name a person. They stay in this local log (created `0o600`): Chock sends
nothing over the network, and `chock witness export` leaves both out.
