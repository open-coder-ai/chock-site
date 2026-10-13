## The levels

For each policy × agent, the compiler records one of eight levels in `.chock/coverage.json`.
The first four come from the **in-agent ladder** — agentseam's own honest, per-agent vocabulary
(`agentseam.matrix.enforcement_level`, owner decision #9) for an installed, in-agent pre-execution
control, plus one level of chock's own — because a hook that fails OPEN on a crash is a materially
weaker promise than one that fails closed, and an adopter deciding on trust needs to see the difference.

| Level | Meaning |
| :--- | :--- |
| **`enforced`** | An installed, hard, pre-execution in-agent control that fails CLOSED — a crashed hook still blocks. |
| **`enforceable`** | Installed and blocks, and CAN be told to fail closed, but does not by default — what an adopter may claim depends on how the hook was installed. |
| **`fail-to-ask`** | Installed and blocks, and when the control itself cannot decide the action does **not** proceed unattended — it is put to a human. The host may still fail open if the hook never runs at all, which is why this sits below `enforceable`. **Chock does not earn this level today**; see below. |
| **`best-effort`** | Installed and blocks, but fails OPEN — a crashed hook silently allows. claude_code's PreToolUse is this tier today. |
| **`enforced-at-commit`** | The policy emitted a git-hook (installed automatically) or a CI gate whose workflow `install-ci` has actually written — hard at commit time or over the PR's commit range, advisory in-agent. Chock's own commit-time mechanism, outside agentseam's per-agent-hook model. |
| **`advisory`** | Only the ambient rule applies — compiled prose the agent is asked to follow. Also outside agentseam's model: an ambient rule is not a lifecycle hook of any kind. |
| **`none`** | Nothing the policy emitted reaches this agent. |
| **`disabled`** | The policy is listed in `policies.disabled` and produces no artifacts or hooks. |
