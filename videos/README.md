# Videos

Each `<name>.tape` here is a [VHS](https://github.com/charmbracelet/vhs) script. VHS types its
commands into a real shell and records the terminal to `static/video/<name>.mp4`, with a poster
`static/video/<name>.png` taken at the end. The pages list the commands a video shows from its
tape (`sitegen/videos.py`), so the list and the video come from the same file.

`static/video/<name>.json` records what a render ran: the sha256 of the tape, the MP4 and the
poster, the MP4's size, and the chock and chock-catalog commits. `tests/test_videos.py` fails
when a tape changes without a new render, a file differs from its record, or an MP4 is over
3,000,000 bytes.

## Render

In CI: run the `videos` workflow from the Actions tab, download its `videos` artifact, review
every video, and commit `static/video/`.

Locally, on Linux, with chock at `.framework-ref` installed, `vhs`, `ttyd` and `ffmpeg` on PATH,
and a writable `/work` (the tapes use `/work/demo` so printed paths are stable). Run outside an
agent session, or with no agent variable such as `CLAUDECODE` or `AI_AGENT` in the environment:
they change what chock's hooks print.

```bash
vhs videos/own-policy.tape
vhs videos/adopt-policy.tape      # needs the network: chock add fetches the catalog
python -m sitegen.videos --sidecar own-policy
python -m sitegen.videos --sidecar adopt-policy --catalog "$(cat .catalog-ref)"
python -m sitegen.videos --check
```

A render is not byte-for-byte repeatable, so the check compares hashes against the committed
render rather than rendering again.
