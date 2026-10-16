## 2. Add it to a selection

A schema-2 selection names it with `from: local` and a path relative to the selection file's own folder:

```yaml
schema: 2
client: claude-code
bundle: {name: chock-guardrails, version: 1.0.0}
catalog: {source: https://github.com/open-coder-ai/chock-catalog, ref: <40-hex commit>}
policies:
  - {from: catalog, id: block-destructive-commands, version: <version>, sha256: <64-hex>}
  - {from: local, id: my-tf-destroy, path: .agents/policies/my-tf-destroy}
```

`sha256` is optional on a local entry; when present, the folder must hash to it. A selection with only local
entries needs no `catalog`. A link or a `#s=` code never carries a local policy: install refuses one, because only a
file has a folder beside it.

## 4. Labels

Each custom member reads `custom, not reviewed; <what its hooks do>` in install's output, in `chock bundle status`
and in the plugin's "customize guardrails" skill. Switch one off like any member: `chock bundle off <id>`.

To propose a policy to the catalog instead, follow the catalog's CONTRIBUTING steps and drop the `my-` prefix.

## 1. Start from a template

```bash
chock new policy <id> --kind {content_regex|guard|script|rule|skill} [--root <folder>]
```

| Kind | What it does | Files besides `manifest.yaml` and `evals/suite.yaml` |
| :--- | :--- | :--- |
| `content_regex` | Refuses an added line matching a pattern, at commit and on the agent's writes | — |
| `guard` | Refuses or asks about a shell command before the agent runs it | `implementations/<id>.py` |
| `script` | Runs your script on the files a commit or write changes; its exit code decides | `implementations/check.py` |
| `rule` | Text the agent reads in its context; nothing enforces it | — |
| `skill` | A skill the agent loads when a request matches it | `skill/body.md` |

Outside a catalog (a folder with no `registry.yaml`) the id gains the reserved `my-` prefix, so it never collides
with a catalog id. The policy lands in `<folder>/.agents/policies/<id>/`. Each template validates and passes its own
evals as written; edit it, then check it:

```bash
chock check --repo <folder> --only validate,evals
```

A `rule`, `guard` or `skill` puts text in the agent's context, which SEC-5 allows below `trust_tier: community` only
with `ambient_override: true` and an `ambient_override_reason`. The templates set the reason to
"authored by the installing user".
