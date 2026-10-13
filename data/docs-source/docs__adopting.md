## Golden rule: customize in these places only

| Want to change | Do this | Never edit |
| :--- | :--- | :--- |
| Protected branch names | `.chock/config.yaml` → `defaults.protected_branches` | the installed policy manifest |
| Disable a policy | `.chock/config.yaml` → `policies.disabled` | deleting the policy folder |
| Add a team policy | `chock new policy <id>` | editing an unrelated policy |
| Add a skill or adapter | `chock new` or `install-skills` | generated adapter files |

Customizing only in your own policies and config means `git merge upstream/main` stays clean.

## How to verify a fresh clone enforces

After `git clone` in a fresh directory, the committed artifacts are present but the git hooks
are not — `.git/hooks/` is never cloned, so the repo enforces **nothing** until the hooks are
reinstalled:

1. Run `chock sync --repo .` to install the hooks from the committed artifacts.
2. `ls .chock/bin/gate.py` should exist.
3. `ls .chock/compiled/scan-secrets/git-hook/gate.json` should exist.
4. Commit a file containing a credential. `scan-secrets` should block it and print the policy message.

`chock init` and `chock sync` write these un-ignore lines to your `.gitignore`, so a global ignore
rule cannot keep the gate out of your commits. The `bin/` in the Visual Studio, .NET and Java
templates is the usual culprit: it matches `.chock/bin/`, and every agent hook then names a file a
clone does not have. `chock check` reports a hook target that is missing or git-ignored. If your
own `.gitignore` has a broad `.chock/` rule, keep the lines below after it:

```gitignore
!.chock/bin/
!.chock/bin/**
!.chock/compiled/
!.chock/compiled/**
```
