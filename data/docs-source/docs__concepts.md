## Policy

The unit of governance. A **policy** is a self-contained folder under `.agents/policies/<id>/` that
says "here is a rule, and here is how it's enforced and proven." Every policy has a `manifest.yaml`
manifest; depending on its type it also carries a script, a gate, and evals.

## Gate

A hook's `hook.gate` in `manifest.yaml` selects a deterministic **kind** (`content_regex`, `forbidden_ref`,
`dependency_allowlist`, `test_integrity`, `script` for a check the policy's own program makes, or
`egress_allowlist` at the gateway), its
`params`, the events it runs on (`on: [commit|push|tool_use|tool_call]`), its `action`
(`block` by default, or `ask` or `warn`), and the message shown when it fires. `tool_call`
gates any tool by name. `chock compile` flattens it to `gate.json`, which the vendored `.chock/bin/gate.py`
runner enforces at git-hook time. See [Gate DSL](../spec/gate-dsl.md).

## Enforcement surface

*Where* a compiled control runs. Chock models nine: `ambient-rule`, `git-hook`,
`ci-gate`, `pre-tool-use`, `stop`, `agent-hooks`, `managed-setting`, `gateway`,
`mcp-gateway`.
Different agents support different surfaces, `gateway`
is modeled but not emitted yet, and some surfaces need an explicit installer before they enforce
anything — see [Enforcement Surfaces](enforcement-surfaces.md).
