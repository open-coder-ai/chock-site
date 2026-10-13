## Typical workflows

**Onboard and prove enforcement**

```bash
chock init .
chock add protect-main-branch
git checkout main && git commit -m x   # blocked by protect-main-branch
```

**Author, validate, compile a new guard**

```bash
chock new policy block-console-log
# …edit manifest.yaml (hook.gate) + evals…
chock check
chock compile block-console-log
```

**CI pipeline (see `.github/workflows/ci.yml`)**

```bash
ruff check . && ruff format --check .
chock check
chock sync --repo . --check
chock registry scan   # then diff to detect drift
pytest -q
```
