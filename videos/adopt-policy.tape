# DOCS-6 video 2: adopt a catalog policy in your own repository (/docs/catalog/adopt/).
# Every command below runs for real; the page lists the shown commands from this file.
# `chock add` fetches the catalog from GitHub at the pinned commit, so rendering needs the
# network. Render with chock at .framework-ref on PATH (see videos/README.md):
#   vhs videos/adopt-policy.tape
# then record the sidecar: python -m sitegen.videos --sidecar adopt-policy

Output static/video/adopt-policy.mp4

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
Type "chock add protect-main-branch --ref c568b6bcfede1c3791d17741c5cabaa802917d47"
Enter
Wait
Sleep 3s
Type "chock sync --repo ."
Enter
Wait
Sleep 4s
Type "clear"
Enter
Wait
Type "git add -A && git commit -q -m 'Adopt chock'"
Enter
Wait
Sleep 3s
Type "git switch -c adopt-chock"
Enter
Wait
Type "git commit -q -m 'Adopt chock'"
Enter
Wait
Sleep 1s
Type "git log --oneline"
Enter
Wait
Sleep 3s
Screenshot static/video/adopt-policy.png
