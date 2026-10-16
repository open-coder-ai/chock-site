## Procedure

1. classify(request) using `references/taxonomy.md`; present user_facing_class: hook, rule, skill (single-purpose capability), subagent, multi-agent workflow / orchestrator. Map user selection to internal_class: hook → hook, rule → rule, skill → skill, subagent → subagent, multi-agent workflow / orchestrator → workflow skill. announce(internal_class, enforcement, deterministic_parts → script placement, reason, effects). For multi-agent workflow / orchestrator, default the display name to `Orchestrator / <Pattern Name>`; invoked skills retain regular names. determinism_scan: split deterministic_parts from judgment_parts; route mechanical parts to a code/hybrid skill with a committed script, never bury them in prose inside an NL skill. if stakes ∈ {security, compliance}: enforce ∈ {verify, block}. if any effect ∈ {writes_external, irreversible}: enforce ∈ {verify, block} AND add approval wiring.

2. interview(`references/interview.md`, target); default target: `<repo_root>/generated/`; never generate inside the invoking framework's own `.agents/` or `subagents/` folders; skip answered questions.

3. if code referenced: mine 3–5 call sites into `examples/`; convert prompts per `references/authoring-techniques.md` §D; set `security.processes_external_content: true` when the skill processes external/repo/user content.

4. draft evals FIRST: trigger + negative_trigger; add adversarial case for stakes or processes_external_content; add behavior case for non-none effects (enforce ≥ verify + approval).

5. generate using `assets/templates/`; construct paths with OS separators (never concatenate raw strings). Scaffold the full folder structure per `references/scaffold-layout.md`; placeholder files are required during scaffolding and must be marked with `<!-- SCAFFOLD: replace or delete before review -->`. Multi-agent workflows also follow `references/multi-agent-scaffold.md`; advanced patterns (failure handling, checkpoint/resume, dry-run, rollback) in `references/orchestration-patterns.md`. Agentic skills apply token/context/memory optimization per `references/agentic-optimization.md`.
   - set status: draft, trust_tier: sandbox; body = activation surface; depth → `references/`
   - default SKILL.md `## Rules` starts with a YAGNI rule: confirmed requirements only, delete unused

6. wire: install hooks for block gates, add ambient lines for rules, optional AGENTS.md fallback section; comment `compiled by chock`.

7. clean temporaries; verify only deliverable + wiring remain.

8. self-check: run `chock check --repo <repo_root>` and `npx skills-ref validate <folder>`; fix failures.

9. hand off: report folder, wiring, smoke test, promotion via PR; suggest `validate` after edits.
