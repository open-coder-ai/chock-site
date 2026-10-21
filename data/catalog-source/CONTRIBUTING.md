## The three rules

All are mechanical, and all are checked by CI rather than by a reviewer's memory.

**1. A policy claims only what it can do.** If it does not exit non-zero, it is advisory,
and the tooling labels it that way whatever the manifest says. 25 of the 72
policies here are advisory, and the README says so in its third paragraph rather than its
appendix. Do not raise a claim your mechanism cannot support.

**2. Evals are the argument.** A gate whose declared behaviour does not match its suite
fails CI. Derived cases alone are not enough — attestation needs at least one authored case
that could have failed.

**3. A new or changed policy ships its adoption transcript.** Run

```bash
python tools/gen_adoption_transcript.py --policy <your-policy-id>
```

and commit `docs/<id>/adoption.md` in the same PR. The tool adopts your policy into an
empty repository — init, copy, recompile, install-hooks, validate, eval — and records what
the tools printed. CI re-runs the same adoption and diffs: pasted or edited output fails,
because the transcript's value is that it *cannot* be written by hand. A PR touching a
policy without its transcript fails with exactly this command.

## Layout

One folder per policy under `base/<id>/`:

```
base/<id>/
  manifest.yaml           identity, and either a gate or rule text
  implementations/*.sh    guard script, for policies consulted before a command runs
  evals/suite.yaml        the cases that decide whether the claim holds
```

`docs/<id>/README.md` is generated — edit `manifest.yaml` and
`docs/policy-prose.yaml`, then run `python tools/gen_policy_docs.py`.

## What CI runs

Two things, kept apart on purpose:

- **What this repo runs** — the subset of `base/` that applies to this repository, installed in
  `.agents/policies/` to govern the catalog itself (four do not apply here: `chock-mise`,
  `java-security`, `no-a11y-regression` and `rtk-dangerous-actions-blocker`): the repo protects itself the same way it asks adopters to.
  The compliance and agentic-security packs stay uninstalled — by their own doctrine they
  only earn their place where they apply. This repo is a Chock adopter, and the first
  commit after adoption was rejected by `protect-main-branch`.
- **What this repo ships** — every published policy, staged into a throwaway repo the way an
  adopter installs them (where CI also re-derives the README's OWASP coverage claim).

Runs fewer than it ships: a catalog should publish more than it is bound by.

**Pull requests change sources; docs and images lag until the release.** A PR changes
`base/<id>/**`, tests, tools and lib, and regenerates only what adopters read straight from
main: the touched policy's `plugin.json`, `SKILL.md`, manifest and `registry.yaml` row. CI
checks those. The README counts and rows, the `docs/` pages, figures, brand card, coverage
matrix and adoption transcripts are not checked on a PR and may be stale on main. The owner's
release regenerates them in one PR. The nightly workflow runs their checks against main
(`python tools/regen_all.py --drift`), lists the stale files in the job summary, and fails
while any is stale. `python tools/regen_all.py` still refreshes everything locally.
