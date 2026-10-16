## Everywhere: one stop for the machine

```bash
chock stop   --everywhere [--reason "<why>"]
chock resume --everywhere
```

`stop --everywhere` writes `~/.chock/stops/_everywhere.json` (`0o600`, beside the per-repository entries; no
sha256 name starts with `_`). While it exists every Chock hook on the machine refuses every tool call, whatever
its repository, session or client: the sync hooks, every plugin's `--stop-check`, the gateway, and an agent's
commit or push at the git hooks. The refusal says the machine is stopped and that `chock resume --everywhere`
lifts it. `--agent` is refused with it: the scope is every agent. A file there that is not a regular file (a
folder, a symlink), or cannot be read or parsed, refuses too (fail closed).

At the git hooks only the main checkout's `.chock/bin/gate.py` tells an agent from a person, so the machine-wide
stop never refuses a commit blind: in a bare repository, a checkout without `gate.py`, or with no python on `PATH`,
it is left to the pre-tool hook, and a person's commit passes. A repository's own stop still refuses there.

`resume --everywhere` is person-only, as `resume` is: it refuses an agent's shell (logged), needs stdin and
stdout to be a TTY, and asks for the word `everywhere` to be typed. It removes that file only; a
per-repository stop stays in force, and its output says so. `chock status` and `chock doctor` lead with
`STOPPED EVERYWHERE` while it is in force. Run inside a repository, `stop` and `resume` write the same log
lines as the per-repository ones, with `"everywhere": true`; outside every repository they write none. Nothing
is sent over the network.

Unstopped, the hooks' fast path is unchanged: the registry folder they already list is the only look.

`chock sync` wires one hook of its own per client, `--stop-check`, with no matcher and whatever
policies are installed, so the stop sees every tool call, reads included. The plugin route carries
the same entry, in every client format (Devin's included):

| Route | Stop check |
| --- | --- |
| `chock sync` | one per client, beside chock's other entries |
| `chock install` bundle | one per bundle; member toggles never reach it |
| `chock plugin build` package (the marketplace route) | one per package that ships hooks |
| an advisory-only package (skill text, no hooks) | none, as `chock sync` wires none where it wires nothing |
| `chock gateway run` (MCP) | in the gateway, before its gates: every `tools/call` |

The gateway refuses each `tools/call` while a stop reaches it (an MCP error, `stopped: <reason>`); it
forwards `initialize`, `tools/list` and every other method, so the client can still connect and list
tools. It judges a stop in its `--repo`, its working directory, and every folder `initialize` names
(`roots`, `workspaceFolders`), each resolved to its repository (the nearest folder holding `.git`) as the pre-tool hook does. The client is
the MCP `clientInfo.name` read as a client id (`claude-code` is `claude_code`; `codex-mcp-client` is
`codex`, reached by a stop on `codex_cli`); a name that is no client's is reached by every stop.
`clientInfo.name` is the client's own claim. A stop file it cannot read, or a check that fails, refuses.

With several packages installed, each runs its own check on every tool call. Unstopped it allows and
logs nothing of its own beyond the call's one allow line. `chock status` shows a stop on its first line. Every refusal, the stop and
the resume are logged ([Decision log](decision-log.md#stop-and-override)). The file is local state:
`chock init` lists it in `.gitignore`, and CI never reads it.

**Limits.**

- It reaches only agents whose hooks Chock wires and that the client runs. An agent with no hook is
  stopped at commit and push only.
- Devin's hook is best-effort: the vendor runs it fail-open, so a hook that errors or times out lets
  the call through.
- It refuses the *next* action. It does not end a process already running (a background shell, a
  spawned server), and it revokes no credential.
- A person, or an agent working outside this repository's hooks, is not affected. Such an agent can also
  delete .chock/stop.json or `~/.chock/stops` directly: both are protected only from agents whose calls a
  hook judges. An agent with an unrestricted shell on a client without hooks is not stopped.
- A stop holds against agents in the stopped scope. An agent running unstopped elsewhere on the same machine, with a shell, can remove the stop (for example by deleting the files); the hook and protect-agent-config refuse the common forms, not every one. `stop --everywhere` leaves no hook-wired agent unstopped; an agent with no Chock hook is not reached by it.
- The terminal check is best-effort: an agent that can run a shell may give `resume` a pseudo-terminal
  (`script`, `expect`) and type the name. The hook refuses a call naming a stopped repository, and
  protect-agent-config refuses writes to any `.chock/` folder or `~/.chock/stops` (it does not refuse the
  `chock resume` command itself, measured against chock-catalog `ca0ddc9`), but
  an agent whose command hides the path (built at run time) is stopped only by those hooks' reach.
- The registry lives under the home folder. An agent whose hook runs with another `HOME`, or that deletes
  `~/.chock/stops` from a session no hook-judged stop reaches, skips the machine-wide registry: hooks that
  cannot place their session then see no stop, and a stop elsewhere is found only through the paths a call
  names.
- A plugin built before the registry existed does not read it: there the stop reaches only calls that
  touch the stopped repository.
