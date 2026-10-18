// Shared behaviour for every page: nav toggle, copy buttons, chip factory, event counts.
import { EVENTS, VALUE } from "./allowlist.js";

document.documentElement.classList.add("js");

const GLYPHS = { block: "■", ask: "◆", warn: "▲", advise: "○", commit: "■", agent: "◆" };

// Display only: the text with its first character uppercased; the source keeps its spelling.
export function sentenceStart(text) {
  const s = String(text ?? "");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function labelChip(keyword, word, meaning) {
  const chip = document.createElement("span");
  chip.className = `label label-${keyword}`;
  word = sentenceStart(word);
  chip.title = `${word}: ${meaning}`;
  const glyph = document.createElement("span");
  glyph.className = "glyph";
  glyph.setAttribute("aria-hidden", "true");
  glyph.textContent = GLYPHS[keyword] || "";
  chip.appendChild(glyph);
  chip.appendChild(document.createTextNode(word));
  return chip;
}

export function announce(text) {
  const live = document.getElementById("live");
  if (live) live.textContent = text;
}

// Copy `text`; on failure select `fallback` (an element) and say how to copy by hand.
export async function copyText(button, text, fallback) {
  try {
    await navigator.clipboard.writeText(text);
    const original = button.textContent;
    button.textContent = "Copied";
    announce("Copied");
    window.setTimeout(() => {
      button.textContent = original;
    }, 1600);
  } catch {
    announce("Press Ctrl+C / Cmd+C to copy");
    if (fallback && fallback.select) {
      fallback.focus();
      fallback.select();
    } else if (fallback) {
      const range = document.createRange();
      range.selectNodeContents(fallback);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }
}

export function initCopyButtons(root = document) {
  root.querySelectorAll("button.copy[data-copy-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = root.querySelector(button.dataset.copyTarget);
      if (target) copyText(button, target.textContent, target);
    });
  });
}

// Selection code: base64url of UTF-8 JSON, no padding (what chock.install.selection reads).
export function encodeSelection(obj) {
  const bytes = new TextEncoder().encode(JSON.stringify(obj));
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

export function decodeSelection(code) {
  const b64 = code.replaceAll("-", "+").replaceAll("_", "/");
  const bin = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0))));
}

export function sameMembers(a, b) {
  return a.length === b.length && a.every((id) => b.includes(id));
}

// The selection object (schema 2) for a set of picked ids and one client; the builder and its
// start screen share it.
export function buildSelection(site, picked, client = site.builder_clients.default) {
  const ids = [...picked].sort();
  const policies = new Map(site.policies.map((p) => [p.id, p]));
  const catalog = { source: site.catalog.source, ref: site.catalog.ref };
  if (site.catalog.release) catalog.release = site.catalog.release;
  const selection = {
    schema: 2,
    client,
    bundle: { version: site.builder_clients.bundle_version },
    catalog,
  };
  const preset = site.presets.find((p) => sameMembers(p.members, ids));
  if (preset) selection.preset = preset.id;
  selection.policies = ids.map((id) => {
    const p = policies.get(id);
    return { from: "catalog", id, version: p.version, sha256: p.sha256 };
  });
  return selection;
}

// The install command for a selection: the command for its client's witness state, filled in one pass.
export function installCommand(site, selection) {
  const code = encodeSelection(selection);
  const clients = site.builder_clients;
  const template = clients.commands[clients.clients[selection.client].witness];
  const values = { CODE: code, CLIENT: selection.client };
  const command = template.replace(/__([A-Z]+)__/g, (match, key) =>
    Object.hasOwn(values, key) ? values[key] : match,
  );
  return { code, command };
}

// A share link carries the client and the policy ids only: #client=<id>&p=<id>,<id>.
export function shareFragment(client, ids) {
  return `#client=${client}&p=${[...ids].sort().join(",")}`;
}

// A link notice echoes only short catalog-shaped ids, and at most SHOWN_IDS of them.
const ECHO_ID = /^[a-z0-9.-]{1,64}$/;
const SHOWN_IDS = 5;

// The ids for a notice: the echoable ones, then `hidden(n)` for the n it leaves out.
export function idList(ids, hidden) {
  const shown = ids.filter((id) => ECHO_ID.test(id)).slice(0, SHOWN_IDS);
  const rest = ids.length - shown.length;
  if (rest) shown.push(hidden(rest));
  return shown.join(", ");
}

// The client and ids a share fragment names, ids in order without repeats; null for any other fragment.
// `ids` is null for a bare #client=<id>, which picks the agent and nothing else.
export function parseShareFragment(hash) {
  const match = /^#client=([a-z0-9-]+)(?:&p=([^&]*))?$/.exec(hash);
  if (!match) return null;
  if (match[2] === undefined) return { client: match[1], ids: null };
  let raw = match[2];
  try {
    raw = decodeURIComponent(raw);
  } catch {
    // keep the raw text; unknown ids are reported by the caller
  }
  const ids = [];
  for (const part of raw.split(",")) {
    const id = part.trim();
    if (id && !ids.includes(id)) ids.push(id);
  }
  return { client: match[1], ids };
}

// ----- event counts (plan AN-1) -----

const LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]"];

// Whether this visit may send counts: never with Global Privacy Control or Do Not Track,
// and on a local host only with ?track=1.
export function trackingAllowed(nav = navigator, loc = location, win = window) {
  if (nav.globalPrivacyControl === true) return false;
  if (nav.doNotTrack === "1" || win.doNotTrack === "1") return false;
  if (LOCAL_HOSTS.includes(loc.hostname)) {
    return new URLSearchParams(loc.search).get("track") === "1";
  }
  return true;
}

// The JSON body for an allowlisted event carrying exactly its keys, each an id-shaped value;
// null for anything else, so a bad call sends nothing.
export function eventBody(name, props = {}) {
  if (typeof name !== "string" || !Object.hasOwn(EVENTS, name)) return null;
  const allowed = EVENTS[name];
  if (Object.keys(props).some((key) => !allowed.includes(key))) return null;
  const clean = {};
  for (const key of allowed) {
    const value = Object.hasOwn(props, key) ? props[key] : undefined;
    if (typeof value !== "string" || !VALUE.test(value)) return null;
    clean[key] = value;
  }
  return JSON.stringify({ name, props: clean });
}

// Count one site event with a same-origin beacon. It never throws and never waits.
export function track(name, props = {}) {
  try {
    if (!trackingAllowed()) return;
    const body = eventBody(name, props);
    if (body === null || typeof navigator.sendBeacon !== "function") return;
    navigator.sendBeacon("/api/event", new Blob([body], { type: "application/json" }));
  } catch {
    // A count must never break the page.
  }
}

function initNavToggle() {
  const button = document.querySelector(".nav-toggle");
  const nav = document.getElementById("nav-links");
  if (!button || !nav) return;
  button.addEventListener("click", () => {
    const open = nav.classList.toggle("nav-open");
    button.setAttribute("aria-expanded", String(open));
  });
}

// Sticky panels park just under the header; its real height is measured so a
// wrapped nav or a different font size never leaves a gap or an overlap.
function initStickyTop() {
  const header = document.querySelector("body > header");
  if (!header) return;
  const set = () =>
    document.documentElement.style.setProperty(
      "--sticky-top",
      `${header.offsetHeight}px`,
    );
  set();
  if (typeof ResizeObserver === "function") {
    new ResizeObserver(set).observe(header);
  }
}

initNavToggle();
initStickyTop();
initCopyButtons();
