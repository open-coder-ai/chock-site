## Guardrails, not guarantees

Tiers: `commit` is a git hook or CI gate that exits non-zero. `in-agent` is the agent's pre-tool hook: best-effort, and it fails open. `advisory` is rule text the agent reads. No agent reaches `enforced` today.

OWASP mappings are partial and the engine is frozen at the commit above. Chock does not stop every attack: it closes common, known entry points before they ship.
