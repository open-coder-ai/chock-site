## Top-level claim

**An adopter repo using Chock knows exactly which policies are enforced, by which
mechanism, on which agent — and cannot silently lose that enforcement.**

Deliberately, the claim is about *truthful, tamper-evident* enforcement, not total
prevention. Chock is a governance layer, not a sandbox: a determined human with a
terminal can bypass git hooks, and an agent outside every wired surface sees only
advisory text. The design goal is that every such gap is *stated* — in the coverage
report, in SECURITY.md, in this page — never papered over. Overclaiming is treated as
the highest-severity failure the project can ship, because one discovered overclaim
discredits every honest number.

## Residual risks, stated

- **No catalog signing.** `chock add` is trust-on-first-use with hash pinning —
  detection, not prevention, of a compromised catalog (SECURITY.md states this in
  full; signing is roadmap work, not quietly assumed).
- **Hooks are bypassable outside gated agents.** `--no-verify` works for humans; the
  CI gate is the backstop and it is opt-in. The coverage report never credits an
  agent surface that is not installed.
- **Guards are best-effort filters**, not a security boundary: quoting tricks,
  aliases, and novel encodings can evade a pattern-based guard. Their value is
  raising the cost of casual violation and producing an audit trail, and their
  guard scripts say so in their own headers.
- **Fail-open hosts.** Some agent hosts ignore unexpected hook exits; where Chock
  emits for such a host, the emitted description states the fail posture rather
  than implying parity.

Each of these is a documented limit with a stated mitigation path — the assurance the
project offers is that the map matches the territory, including the holes.
