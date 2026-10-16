## Anatomy of a policy folder

```text
.agents/policies/block-console-log/
├── manifest.yaml            # manifest — always present
├── skill/                   # optional: body.md, and any file the packaged skill should ship
└── evals/
    └── suite.yaml         # trigger / negative / behavior / adversarial cases
```
