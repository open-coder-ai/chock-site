// A select-only combobox (WAI-ARIA APG pattern) drawn over a native <select>, which stays the value.
import { sentenceStart } from "./common.js";

const PAGE = 10;
const TYPE_RESET_MS = 500;

// Replace `select` on screen with a button and listbox; returns { sync, focus }.
// The native control stays in the DOM (hidden): its value and "change" event are unchanged,
// and without JS it is what the visitor gets.
export function enhanceSelect(select) {
  const label = document.querySelector(`label[for="${select.id}"]`);
  if (label && !label.id) label.id = `${select.id}-label`;

  const wrap = document.createElement("div");
  wrap.className = "combo";
  const button = document.createElement("button");
  button.type = "button";
  button.id = `${select.id}-combo`;
  button.className = "combo-button";
  button.setAttribute("role", "combobox");
  button.setAttribute("aria-haspopup", "listbox");
  button.setAttribute("aria-expanded", "false");
  const value = document.createElement("span");
  value.className = "combo-value";
  const chevron = document.createElement("span");
  chevron.className = "combo-chevron";
  chevron.setAttribute("aria-hidden", "true");
  button.append(value, chevron);

  const list = document.createElement("ul");
  list.id = `${select.id}-list`;
  list.className = "combo-list";
  list.setAttribute("role", "listbox");
  list.tabIndex = -1;
  list.hidden = true;
  button.setAttribute("aria-controls", list.id);
  if (label) {
    button.setAttribute("aria-labelledby", label.id);
    list.setAttribute("aria-labelledby", label.id);
    label.htmlFor = button.id;
  }

  // "Git hygiene · 6": the count after the last " · " is shown muted.
  const items = [...select.options].map((option, i) => {
    const item = document.createElement("li");
    item.id = `${list.id}-${i}`;
    item.className = "combo-option";
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", "false");
    const text = sentenceStart(option.textContent.trim());
    const split = /^(.*) · (\d+)$/.exec(text);
    const name = document.createElement("span");
    name.className = "combo-name";
    name.textContent = split ? split[1] : text;
    item.appendChild(name);
    if (split) {
      const count = document.createElement("span");
      count.className = "combo-count";
      count.textContent = ` · ${split[2]}`;
      item.appendChild(count);
    }
    list.appendChild(item);
    return { item, text: text.toLowerCase() };
  });

  select.hidden = true;
  select.tabIndex = -1;
  select.after(wrap);
  wrap.append(button, list);

  let active = 0;
  let typed = "";
  let typedAt = 0;

  const isOpen = () => button.getAttribute("aria-expanded") === "true";

  function setActive(i) {
    active = Math.max(0, Math.min(items.length - 1, i));
    items.forEach(({ item }, j) => {
      item.classList.toggle("is-active", j === active);
      item.setAttribute("aria-selected", String(j === active));
    });
    button.setAttribute("aria-activedescendant", items[active].item.id);
    items[active].item.scrollIntoView({ block: "nearest" });
  }

  // Show the native select's current value; call after code sets `select.value`.
  function sync() {
    const i = Math.max(0, select.selectedIndex);
    value.textContent = sentenceStart(select.options[i] ? select.options[i].textContent.trim() : "");
    items.forEach(({ item }, j) => item.classList.toggle("is-current", j === i));
    if (!isOpen()) active = i;
  }

  function open(at = Math.max(0, select.selectedIndex)) {
    if (!isOpen()) {
      list.hidden = false;
      wrap.classList.add("is-open");
      button.setAttribute("aria-expanded", "true");
    }
    setActive(at);
  }

  function close() {
    if (!isOpen()) return;
    list.hidden = true;
    wrap.classList.remove("is-open");
    button.setAttribute("aria-expanded", "false");
    button.removeAttribute("aria-activedescendant");
  }

  // The listener may revert the value (a declined confirm), so re-read it after.
  function choose(i) {
    close();
    button.focus();
    if (i !== select.selectedIndex) {
      select.selectedIndex = i;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    sync();
  }

  // Type-ahead: the next option whose text starts with what was typed in the last half second.
  function typeAhead(key) {
    const now = Date.now();
    typed = now - typedAt > TYPE_RESET_MS ? key : typed + key;
    typedAt = now;
    const same = [...typed].every((c) => c === typed[0]);
    const needle = same ? typed[0] : typed;
    const from = same || typed.length === 1 ? active + 1 : active;
    for (let n = 0; n < items.length; n += 1) {
      const j = (from + n) % items.length;
      if (items[j].text.startsWith(needle)) return j;
    }
    return -1;
  }

  button.addEventListener("click", () => {
    if (isOpen()) close();
    else open();
  });

  button.addEventListener("keydown", (event) => {
    const { key, altKey, ctrlKey, metaKey } = event;
    if (!isOpen()) {
      if (key === "ArrowDown" || key === "ArrowUp" || key === "Enter" || key === " ") open();
      else if (key === "Home") open(0);
      else if (key === "End") open(items.length - 1);
      else if (key.length === 1 && !ctrlKey && !metaKey && !altKey) {
        open();
        const j = typeAhead(key.toLowerCase());
        if (j >= 0) setActive(j);
      } else return;
      event.preventDefault();
      return;
    }
    if (key === "ArrowDown" && !altKey) setActive(active + 1);
    else if (key === "ArrowUp" && altKey) choose(active);
    else if (key === "ArrowUp") setActive(active - 1);
    else if (key === "Home") setActive(0);
    else if (key === "End") setActive(items.length - 1);
    else if (key === "PageDown") setActive(active + PAGE);
    else if (key === "PageUp") setActive(active - PAGE);
    else if (key === "Enter") choose(active);
    else if (key === " " && Date.now() - typedAt > TYPE_RESET_MS) choose(active);
    else if (key === "Escape") close();
    else if (key === "Tab") {
      choose(active);
      return;
    } else if (key.length === 1 && !ctrlKey && !metaKey && !altKey) {
      const j = typeAhead(key.toLowerCase());
      if (j >= 0) setActive(j);
    } else return;
    event.preventDefault();
  });

  // Keep focus on the button while the pointer is in the list.
  list.addEventListener("mousedown", (event) => event.preventDefault());
  list.addEventListener("click", (event) => {
    const item = event.target.closest(".combo-option");
    if (item) choose(items.findIndex((x) => x.item === item));
  });
  list.addEventListener("mousemove", (event) => {
    const item = event.target.closest(".combo-option");
    const j = items.findIndex((x) => x.item === item);
    if (j >= 0 && j !== active) setActive(j);
  });
  button.addEventListener("blur", close);
  document.addEventListener("pointerdown", (event) => {
    if (isOpen() && !wrap.contains(event.target)) close();
  });
  if (label) {
    label.addEventListener("click", (event) => {
      event.preventDefault();
      button.focus();
    });
  }

  sync();
  return { sync, focus: () => button.focus() };
}
