## What Chock does not do — stated plainly

- **Agent identity, tokens, and spend budgets.** Identity platforms and gateways own
  runtime credentials and quotas. Chock's `gateway` surface is reserved for repo-scoped
  budget/egress backstops and claims nothing today.
- **Runtime semantic filtering between agents.** Judging message intent mid-loop puts a
  model in the enforcement path; Chock's position is deterministic checks or honest
  `advisory`, never probabilistic "enforcement."
- **Passive endpoint telemetry.** Watching an agent after the fact is an EDR product's
  job; Chock's value is the deterministic slice *before* commit, push, or execution.
- **Model-layer failures.** Judgment, tone, and social behavior cannot be gated from a
  repo. Rules cover the expressible slice as `advisory`, and this page will not dress
  that up as enforcement.

If a row here ever disagrees with what the compiler reports for your repo, the compiler
is right and this page has drifted — please [open an issue](https://github.com/open-coder-ai/chock/issues).
