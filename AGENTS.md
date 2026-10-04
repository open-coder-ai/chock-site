# Agent instructions

Rules for this repo, from `plan/chock-site-implementation.md` section 2 in open-coder-ai/org-plan:

1. **Python 3.12.** Format and lint with `ruff`. Never run a blanket `ruff --fix`: fix each finding by hand.
2. **Docstrings:** one line per module, class and function. Comments only where the code is not obvious.
3. **Templates are files** under `templates/`, with `__TOKEN__` placeholders filled in **one pass**: one `re.sub` over the template with a function that looks each token up. Never call `str.replace` once per token, because a value containing `__OTHER__` would be filled by a later token, which allows HTML injection. A template token without a value, or a value without a token, raises an error. Never use f-strings or `.format` to build HTML. Every value put into HTML goes through `html.escape` first, except a value that is itself a rendered template.
4. **Facts are data, not code.** Texts, links, presets and message wording live in `data/*.json` or `data/*.yaml`. Python and JS read them.
5. **JavaScript:**
   - vanilla, ES2020, no libraries, no npm, no build step;
   - never use `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `eval`, `new Function`, or `setTimeout` with a string;
   - build elements with `document.createElement` and set text with `textContent`.
6. **Readable by agents:** every page has a `.md` twin and structured data, and agent-facing text states facts and asks the user before anything is run (section 6.8).
7. **No third-party requests.** No CDN, web font, analytics, iframe or external image. Links (`<a href="https://github.com/...">`) are fine. Everything a page *loads* comes from the same site.
8. **Every page** carries the CSP meta tag in section 6.2. No inline `<script>` and no inline `style=""` or `<style>`, because the CSP blocks them.
9. **Tests:** never skip, xfail or delete a failing test. Fix the code. If you think a test is wrong, say so in the PR and leave it failing.
10. **Git:**
    - one PR per milestone (section 9);
    - commit with `git commit -s` (sign-off line);
    - never force-push, never rewrite history, never merge your own PR. The owner merges.
11. **No secrets, tokens or personal data** in the repo, commits or PR text.
12. **Measured or "unmeasured".** Every number in a PR body is one you measured, or the word "unmeasured". Never estimate.
