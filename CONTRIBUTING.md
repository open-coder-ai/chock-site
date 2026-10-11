# Contributing

See `AGENTS.md` for the repo rules and `README.md` for the layout and the manual setup.

## Test the site locally

One script builds and serves the site at its pinned catalog (`.catalog-ref`) and
engine (`.framework-ref`), the same way CI does. Run it from the root of a chock-site
checkout.

**Prerequisites:** Git, and Python 3.12 (on Windows, the python.org installer with the
`py` launcher). No admin rights are needed. The script installs nothing outside the
checkout: it clones chock-catalog into `.catalog`, creates `.venv`, and builds into
`dist/`, all git-ignored.

**Windows (PowerShell 5.1 or 7):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local-test.ps1
```

**Linux and macOS:**

```bash
bash scripts/local-test.sh
```

It then serves http://127.0.0.1:8000/ and opens it in your browser. Press Ctrl+C to stop.
Running it again updates `.catalog` and `.venv` to the current pins.

### Options

| PowerShell | bash | What it does |
|---|---|---|
| `-RunTests` | `--test` | Run the unit tests, then install Playwright's Chromium and run the browser (e2e) tests, before serving. |
| `-Port N` | `--port N` | Serve on port `N` instead of 8000. |
| `-NoServe` | `--no-serve` | Build `dist/` and exit (CI runs this). |
| `-NoOpen` | `--no-open` | Serve without opening a browser. |

### Engine check

The script prints a command that runs the pinned chock engine on a selection code
from the site's builder:

```text
<.venv python> -m chock install --selection '<code from the builder>' --client codex --dest <temp folder>/chock-try
```

Without `--apply` it only builds the plugin into that folder; your agent configuration
is not touched.
