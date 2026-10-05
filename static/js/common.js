// Shared behaviour for every page: nav toggle, copy buttons, chip factory.
document.documentElement.classList.add("js");

const GLYPHS = { block: "■", ask: "◆", warn: "▲", advise: "○" };

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

export function initCopyButtons(root = document) {
  root.querySelectorAll("button.copy[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = root.querySelector(button.dataset.copyTarget);
      if (!target) return;
      const text = target.textContent;
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
        const range = document.createRange();
        range.selectNodeContents(target);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      }
    });
  });
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

initNavToggle();
initCopyButtons();
