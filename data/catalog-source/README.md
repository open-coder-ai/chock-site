### Installing this is running code

A policy here is not inert data. A declarative policy compiles to a git hook that runs on every commit in your repository; a policy shipping an `implementations/` guard becomes a guard script consulted before your agent runs a command; `java-security` and `no-a11y-regression` run their own program at commit and when the agent writes; `firecrawl-fallback-only` and `token-efficiency` run theirs before a matching tool call. Either way, `chock add` installs executable content over `git clone`. There is no signing key, so pin and verify when the catalog is not one you control:

```bash
chock add scan-secrets --ref <commit-sha> --verify-sha <sha256>
```

This catalog has tags, but a tag can move: pin a full commit SHA. `--ref` refuses a commit that is on no branch or tag of the catalog; `--verify-sha` refuses the install unless the fetched pack hashes to the value you name.

Two limits worth knowing before you rely on any of this: `git commit --no-verify` skips every git hook, and git hooks are not cloned, so a fresh clone enforces nothing until someone runs `chock sync`. [SECURITY.md](SECURITY.md) has the rest.
