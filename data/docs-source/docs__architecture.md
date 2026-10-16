## The components

| Component | Path | Role |
| :--- | :--- | :--- |
| **CLI** | `src/chock/cli.py` | One entry point; dispatches to each activity |
| **Scaffold** | `src/chock/scaffold/` | `init` / `new` / `install-skills` (deterministic) |
| **Compiler** | `src/chock/compile/` | Surfaces + per-surface emitters + coverage |
| **Validation** | `src/chock/validation/` | Spec/schema/budget/security/eval checks |
| **Registry** | `src/chock/registry/` | Artifact index + content hashes |
| **Lockfile** | `src/chock/lock.py` | Reproducible, hash-pinned installs |
| **Hooks installer** | `src/chock/hooks/` | Git dispatcher + policy wrappers |
| **Gate build** | `src/chock/gate/build.py` | Loads `hook.gate` from `manifest.yaml` and bakes `gate.json` |
| **Vendored runner** | `src/chock/gate/runner/` | Self-contained runtime that `chock.gate.assemble` builds into one file, `.chock/bin/gate.py` |
| **CI installer** | `src/chock/scaffold/install_ci.py` | Writes the GitHub Actions workflow that runs `ci-gate` |
| **Policies** | `.agents/policies/<id>/` | Installed from a catalog; owned by the adopter, never shipped |
| **Spec** | `spec/` | Neutral format, JSON schemas, enforcement matrix |

## Pointer model

`AGENTS.md` holds a single managed pointer to `.agents/policies/INDEX.md`. `chock sync`
compiles every active rule (full text), every gate, and every skill into that index, capped by
`index.max_tokens` in `.chock/config.yaml`. `INDEX.md` is the ambient attention surface for
the agent; git hooks remain the guaranteed enforcement floor. The pointer is constant
so adapters never have to be rewritten when rules change.

## The CLI is a package manager, not a runtime

The deterministic parts (scaffold, compile, validate, install) live in the **CLI**. The generative
parts — authoring a bespoke policy from an interview — live in **skills** that the CLI *installs into
your own agent* and that your agent runs. Chock ships no LLM of its own.

See [Core Concepts](concepts.md) for the vocabulary and [Enforcement Surfaces](enforcement-surfaces.md)
for the coverage model in detail.
