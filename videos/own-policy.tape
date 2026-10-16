# DOCS-6 video 1: write your own policy in your own repository (/docs/write/own-policy/ and
# the home page). Every command below runs for real; the page lists the shown commands from
# this file. Render with chock at .framework-ref on PATH (see videos/README.md):
#   vhs videos/own-policy.tape
# then record the sidecar: python -m sitegen.videos --sidecar own-policy

Output static/video/own-policy.mp4

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 640
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set Padding 24
Set WaitTimeout 300s

# Hidden setup: a throwaway repository at a fixed path, so printed paths are stable.
Hide
Type "rm -rf /work/demo /work/home && mkdir -p /work/demo /work/home && export HOME=/work/home && cd /work/demo"
Enter
Type "git init -q -b main . && git config --global user.name Demo && git config --global user.email demo@example.com && clear"
Enter
Wait
Show

Type "chock init ."
Enter
Wait
Sleep 2s
Type "chock new policy block-marker --kind content_regex"
Enter
Wait
Sleep 2s
Type "chock sync --repo ."
Enter
Wait
Sleep 4s
Type "chock check --repo ."
Enter
Wait
Sleep 3s
Type "git add -A && git commit -q -m 'Add my-block-marker'"
Enter
Wait
Sleep 1s
Type "clear"
Enter
Wait
Type "echo 'x = 1  # DO NOT COMMIT' > notes.py && git add notes.py"
Enter
Wait
Type "git commit -q -m 'Add notes'"
Enter
Wait
Sleep 3s
Type "echo 'x = 1' > notes.py && git add notes.py"
Enter
Wait
Type "git commit -q -m 'Add notes'"
Enter
Wait
Sleep 1s
Type "git log --oneline"
Enter
Wait
Sleep 3s
Screenshot static/video/own-policy.png
