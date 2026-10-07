// Shared behaviour for every page: nav toggle, copy buttons, chip factory.
document.documentElement.classList.add("js");

const GLYPHS = { block: "■", ask: "◆", warn: "▲", advise: "○", commit: "■", agent: "◆" };

export function labelChip(keyword, word, meaning) {
  const chip = document.createElement("span");
  chip.className = `label label-${keyword}`;
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
