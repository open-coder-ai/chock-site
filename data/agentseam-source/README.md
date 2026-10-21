## How it works

An adapter per agent owns three things: payload parsing, the response dialect and the config shape.
Adapters are data (`src/agentseam/data/vendors/<agent>.json`, validated against `schema.json`) plus a
small family module when a vendor speaks a new dialect. The matrix is data too, and
`matrix.enforcement_level(agent, event)` is the authority for every grade below.

*324 cells (27 agents by 12 events), from `matrix.enforcement_level()` run at `a100491`: 203 none, 74 detect, 45 best-effort, 2 enforceable, 0 enforced.*

| Level | Meaning | Agents at `pre_tool` today |
|---|---|---|
| enforced | the agent blocks, and fails closed if the hook dies | none |
| enforceable | it blocks and *can* be told to fail closed, but doesn't by default | 1: Cursor |
| best-effort | it blocks, but fails *open* (a crashed hook allows) | 16: Claude Code, VS Code Copilot, Codex CLI, Gemini CLI, Windsurf, Devin, Grok CLI, Antigravity, Kimi Code, Junie, Tabnine, goose, OpenHands, Factory Droid, Mistral Vibe, Cline |
| detect | observable after the fact only; prevention is not available | 0 (74 cells at other events) |
| none | nothing agentseam can gate: no hook surface, or no adapter yet (`unadapted`) | 10: aider and Zed (no hook surface); Amp, Copilot CLI, DeepSeek Harness, Kilo Code, Kiro, OpenCode, Replit, Roo Code (`unadapted`) |

A row is only claimed when a `verified: {basis, version, date}` record backs it. Run `agentseam doctor` to
see what is wired on this machine and flag rows not re-verified in 90 days. Grading never exceeds
evidence: `enforcement_level()` caps every grade by what its own basis can support, so a `vendor-docs`
row cannot back `enforced`. A pre-tool guard is one layer, not the whole defence: pair it with a git hook or
CI gate that the agent cannot skip.
