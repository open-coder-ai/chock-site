// loadPageBeacon (plan AN-2): when the Cloudflare Web Analytics beacon is added to a page, and when not.
// Run by tests/test_beacon.py with `node --test`.
import assert from "node:assert/strict";
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { pathToFileURL } from "node:url";

// The build ships the generated allowlist next to common.js as js/allowlist.js; do the same in a temp folder.
const here = new URL(".", import.meta.url).pathname;
const folder = mkdtempSync(join(tmpdir(), "beacon-"));
copyFileSync(join(here, "../../static/js/common.js"), join(folder, "common.js"));
copyFileSync(join(here, "../../functions/api/_allowlist.js"), join(folder, "allowlist.js"));

// common.js touches the page when imported, so give it a minimal one first.
const none = () => null;
const page = { documentElement: { classList: { add() {} }, style: { setProperty() {} } } };
page.querySelector = none;
page.querySelectorAll = () => [];
page.getElementById = none;
globalThis.document = page;
globalThis.window = {};
globalThis.location = { hostname: "chock.sh", search: "" };
const { loadPageBeacon } = await import(pathToFileURL(join(folder, "common.js")).href);

const TOKEN = "0123456789abcdef0123456789abcdef";

// A fake document: an optional token meta, and the scripts appended to <head>.
function fakeDoc(token) {
  const scripts = [];
  return {
    scripts,
    querySelector(selector) {
      if (selector.startsWith("meta")) {
        return token === undefined ? null : { getAttribute: () => token };
      }
      return scripts.length ? scripts[0] : null;
    },
    createElement: () => ({ attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } }),
    head: { appendChild: (el) => scripts.push(el) },
  };
}

const nav = (extra = {}) => ({ globalPrivacyControl: false, doNotTrack: null, ...extra });
const where = (hostname = "chock.sh", search = "") => ({ hostname, search });

test("a token with tracking allowed adds exactly one deferred beacon script", () => {
  const doc = fakeDoc(TOKEN);
  assert.equal(loadPageBeacon(doc, nav(), where(), {}), true);
  assert.equal(doc.scripts.length, 1);
  const [script] = doc.scripts;
  assert.equal(script.src, "https://static.cloudflareinsights.com/beacon.min.js");
  assert.equal(script.defer, true);
  assert.deepEqual(JSON.parse(script.attrs["data-cf-beacon"]), { token: TOKEN });
  assert.equal(loadPageBeacon(doc, nav(), where(), {}), false);
  assert.equal(doc.scripts.length, 1);
});

test("an empty or missing token loads nothing", () => {
  for (const token of ["", undefined]) {
    const doc = fakeDoc(token);
    assert.equal(loadPageBeacon(doc, nav(), where(), {}), false);
    assert.equal(doc.scripts.length, 0);
  }
});

test("a token that is not 32 hex characters loads nothing", () => {
  for (const token of ["abc", TOKEN.toUpperCase(), `${TOKEN}"}`, `${TOKEN}0`]) {
    const doc = fakeDoc(token);
    assert.equal(loadPageBeacon(doc, nav(), where(), {}), false, token);
    assert.equal(doc.scripts.length, 0);
  }
});

test("Global Privacy Control loads nothing", () => {
  const doc = fakeDoc(TOKEN);
  assert.equal(loadPageBeacon(doc, nav({ globalPrivacyControl: true }), where(), {}), false);
  assert.equal(doc.scripts.length, 0);
});

test("Do Not Track loads nothing, from navigator or window", () => {
  for (const [n, w] of [[nav({ doNotTrack: "1" }), {}], [nav(), { doNotTrack: "1" }]]) {
    const doc = fakeDoc(TOKEN);
    assert.equal(loadPageBeacon(doc, n, where(), w), false);
    assert.equal(doc.scripts.length, 0);
  }
});

test("a local host loads nothing unless ?track=1", () => {
  for (const host of ["localhost", "127.0.0.1", "[::1]"]) {
    const off = fakeDoc(TOKEN);
    assert.equal(loadPageBeacon(off, nav(), where(host), {}), false, host);
    assert.equal(off.scripts.length, 0);
    const on = fakeDoc(TOKEN);
    assert.equal(loadPageBeacon(on, nav(), where(host, "?track=1"), {}), true, host);
    assert.equal(on.scripts.length, 1);
  }
});

test("it never throws", () => {
  assert.equal(loadPageBeacon({}, nav(), where(), {}), false);
  assert.equal(loadPageBeacon(null, nav(), where(), {}), false);
});
