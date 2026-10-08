// Generated from data/analytics.yaml by `python -m sitegen allowlist`. Do not edit.
export const KEYS = Object.freeze(["agent", "kind", "preset", "policy", "form"]);
export const VALUE = new RegExp("^[a-z0-9.-]{1,64}$");
export const MAX_BODY = 1024;
export const EVENTS = Object.freeze({
  "install-copied": Object.freeze(["agent"]),
  "share-copied": Object.freeze([]),
  "selection-downloaded": Object.freeze([]),
  "quiz-finished": Object.freeze([]),
  "preset-picked": Object.freeze(["preset"]),
  "author-script-downloaded": Object.freeze(["kind", "agent"]),
  "report-form-opened": Object.freeze(["form"]),
  "policy-build-clicked": Object.freeze(["policy", "agent"]),
});
