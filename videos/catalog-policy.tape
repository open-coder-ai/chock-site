# DOCS-6 video 3: add a new policy to chock-catalog (/docs/catalog/contribute/).
# Every command below runs for real; the page lists the shown commands from this file.
# The hidden setup clones the catalog at .catalog-ref and installs the engine the catalog
# pins in its own .framework-ref, as its CI does, so rendering needs the network and python3.12.
#   vhs videos/catalog-policy.tape
# then record the sidecar: python -m sitegen.videos --sidecar catalog-policy

Output static/video/catalog-policy.mp4

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 640
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set Padding 24
Set WaitTimeout 600s

# Hidden setup: the catalog at the pinned commit, and its engine in a virtual environment.
Hide
Type "rm -rf /work/catalog /work/venv /work/home && mkdir -p /work/home && export HOME=/work/home"
Enter
Type "git config --global user.name Demo && git config --global user.email demo@example.com"
Enter
Type "git clone -q https://github.com/open-coder-ai/chock-catalog /work/catalog && cd /work/catalog && git checkout -q c568b6bcfede1c3791d17741c5cabaa802917d47"
Enter
Wait
Type "python3.12 -m venv /work/venv && export PATH=/work/venv/bin:$PATH"
Enter
Wait
Type `pip install -q "chock @ git+https://github.com/open-coder-ai/chock@$(cat .framework-ref)" && pip install -q --require-hashes -r requirements/test.txt && clear`
Enter
Wait
Show

Type "git switch -c add-block-marker"
Enter
Wait
Type "chock new policy block-marker --kind content_regex --repo ."
Enter
Wait
Sleep 2s
Type "mv .agents/policies/block-marker base/block-marker"
Enter
Wait
Type "git restore .agents/policies/INDEX.md .agents/policies/INDEX-extended.md .chock/registry.json"
Enter
Wait
Type "clear"
Enter
Wait
Type "cat >> docs/policy-prose.yaml <<'EOF'"
Enter
Type "block-marker:"
Enter
Type "  solves: >"
Enter
Type "    A line marked DO-NOT-COMMIT reaching the repository."
Enter
Type "  customise: >"
Enter
Type "    `params.content_pattern` is the regular expression an added line must not match."
Enter
Type "EOF"
Enter
Wait
Type "python - <<'EOF'"
Enter
Type "from pathlib import Path"
Enter
Type 'readme = Path("README.md")'
Enter
Type 'anchor = "| [`protect-main-branch`](docs/protect-main-branch/) |"'
Enter
Type 'row = "| [`block-marker`](docs/block-marker/) | lines marked DO-NOT-COMMIT | 4/4 |"'
Enter
Type "lines = readme.read_text().splitlines(keepends=True)"
Enter
Type "at = next(i for i, line in enumerate(lines) if line.startswith(anchor))"
Enter
Type "lines.insert(at + 1, row + chr(10))"
Enter
Type 'readme.write_text("".join(lines))'
Enter
Type "EOF"
Enter
Wait
Sleep 1s
Type "clear"
Enter
Wait
Type "python tools/regen_all.py --fast"
Enter
Wait
Sleep 4s
Type "git add base/block-marker && git commit -q -m 'Add block-marker'"
Enter
Wait
Type "python tools/gen_policy_docs.py"
Enter
Wait
Sleep 1s
Type "clear"
Enter
Wait
Type "python tools/regen_all.py --fast"
Enter
Wait
Sleep 4s
Type "git status --short"
Enter
Wait
Sleep 4s
Screenshot static/video/catalog-policy.png
