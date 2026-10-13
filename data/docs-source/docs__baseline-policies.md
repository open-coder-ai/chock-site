## Customising a policy

Because an installed policy is yours, the first option is simply **edit it**. Change the regex, add
your own token formats, drop rules you disagree with. Re-copying from the catalog is an explicit act;
nothing does it behind your back.

Config overlays remain useful for things you want to change without touching the manifest:

```yaml
policies:
  disabled: [block-no-verify]        # fully disable a policy
  overrides:
    scan-secrets:
      enforcement: advise            # downgrade to ambient rule only
    protect-main-branch:
      surfaces: [ambient-rule]       # or scope by explicit surfaces
```

- `disabled` removes the policy's compiled artifacts and git-hook wiring.
- `overrides.<id>.surfaces` becomes the `targets` passed to `compile_policy`.
- `overrides.<id>.enforcement: advise` is shorthand for `surfaces: [ambient-rule]`.
- A policy marked `mandatory: true` cannot be disabled; the CLI and `chock check` both
  refuse.

Some values are reachable from config without editing the manifest — `protect-main-branch` reads
`chock.defaults.protected_branches` via its `config_key`. Recompile after changing config, and
the compiled gate, the block message and the advisory text all follow.

Use `chock disable <id>` and `chock enable <id>` for ergonomic toggles, or
`chock status` to see the current state and coverage.

See [Authoring Policies](authoring-policies.md) to write your own and
[Enforcement Surfaces](enforcement-surfaces.md) for where each guard actually holds.
