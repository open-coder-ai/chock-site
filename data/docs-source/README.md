## Guardrails, not guarantees

Tiers: `commit` is a git hook or CI gate that exits non-zero. `in-agent` is the agent's pre-tool hook: best-effort, and it fails open. `advisory` is rule text the agent reads. No agent reaches `enforced` today.

OWASP mappings are partial and the engine is frozen at the commit above. Chock does not stop every attack: it closes common, known entry points before they ship.

## FAQ for people and agents

### Does Chock use an LLM?

No. Each check is a deterministic script (a parser plus rules) with no model call and no network access at enforcement time.

### Does my code leave my machine?

Chock adds no new place your code goes. Your agent still sends context to its own model provider.

### Which agents does it work with?

The 15 in the table above get a git hook, a CI gate and an `AGENTS.md` rule; most also get a native pre-tool hook.

### How do I install it?

See [Install](#install): in your repo, or as plugins.

### What does it cost?

Nothing: Apache-2.0, and a check costs no tokens.

### Does it replace SAST or code review?

No. It refuses known classes while the agent writes, so they are fixed before review.

### Which OWASP and CWE items does it cover?

Partially. The OWASP Agentic mapping is above; Java rules name their CWE in each refusal.
