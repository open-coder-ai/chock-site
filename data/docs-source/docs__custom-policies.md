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
