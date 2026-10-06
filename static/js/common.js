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

// The selection object (plan 8.1) for a set of picked ids; the builder and its start screen share it.
export function buildSelection(site, picked) {
  const ids = [...picked].sort();
  const policies = new Map(site.policies.map((p) => [p.id, p]));
  const catalog = { source: site.catalog.source, ref: site.catalog.ref };
  if (site.catalog.release) catalog.release = site.catalog.release;
  const selection = { schema: 1, client: "claude-code", catalog };
  const preset = site.presets.find((p) => sameMembers(p.members, ids));
  if (preset) selection.preset = preset.id;
  selection.policies = ids.map((id) => {
    const p = policies.get(id);
    return { id, version: p.version, sha256: p.sha256 };
  });
  return selection;
}

// The install command for a selection: the engine's command template with the code filled in.
export function installCommand(site, selection) {
  const code = encodeSelection(selection);
  return { code, command: site.command.replace("__CODE__", () => code) };
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
