// The builder: pick policies, then read the command, share link and selection file.
// Everything runs in the browser. The picks live in the URL fragment, which browsers
// never send to a server.
import { announce, copyText, decodeSelection, encodeSelection } from "./common.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

// Texts from site.json use {name} for runtime values.
const fill = (text, values) =>
  text.replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match));
// The engine's warning rules use __NAME__ tokens, filled in one pass.
const fillTokens = (text, values) =>
  text.replace(/__([A-Z]+)__/g, (match, key) => (key in values ? values[key] : match));

function sameMembers(a, b) {
  return a.length === b.length && a.every((id) => b.includes(id));
}

async function loadSite() {
  const response = await fetch("/data/site.json");
  return response.json();
}

async function main() {
  const site = await loadSite();
  const T = site.builder_texts;
  const policies = new Map(site.policies.map((p) => [p.id, p]));
  const presets = site.presets;
  let picked = new Set();
  let notices = [];
  let activeTab = "command";

  const rows = $$(".bmember[data-policy-id]");
  const groups = $$(".bgroup");
  const chips = $$(".chip[data-facet='label']");
  const search = $("#builder-search");
  const start = $("#builder-start");
  const status = $("#builder-status");
  const noticeBox = $("#link-notice");
  const selCount = $(".sel-count");
  const selList = $(".sel-list");
  const emptyNode = $(".empty", selList);
  const notesBox = $(".notes");
  const needOne = $("#need-one");
  const tabs = $$("[role='tab']");
  const panels = $$("[role='tabpanel']");
  const codeEl = $("[data-selection-code]");
  const shareEl = $("#share-url");
  const labelOn = new Set();
  let notesKey = "";

  // ----- the selection object (plan 8.1) -----

  function buildSelection() {
    const ids = [...picked].sort();
    const catalog = { source: site.catalog.source, ref: site.catalog.ref };
    if (site.catalog.release) catalog.release = site.catalog.release;
    const selection = { schema: 1, client: "claude-code", catalog };
    const preset = presets.find((p) => sameMembers(p.members, ids));
    if (preset) selection.preset = preset.id;
    selection.policies = ids.map((id) => {
      const p = policies.get(id);
      return { id, version: p.version, sha256: p.sha256 };
    });
    return selection;
  }

  // ----- warnings (plan 8.3) -----

  function warnings() {
    const out = [];
    const text = (key, values) => {
      const template = site.warning_texts[key];
      if (template) out.push(fillTokens(template, values));
    };
    for (const rule of site.warning_rules) {
      if (rule.kind === "grade") {
        const ids = [...picked].filter((id) => policies.get(id).keyword === rule.grade).sort();
        if (ids.length) text(`grade:${rule.grade}`, { PRESENT: ids.join(", ") });
        continue;
      }
      const here = rule.policies.filter((id) => picked.has(id));
      const absent = rule.policies.filter((id) => !picked.has(id));
      if (!here.length) continue;
      if (rule.kind === "missing_partner" && absent.length) {
        text("missing_partner", { PRESENT: here.join(", "), ABSENT: absent.join(", ") });
      } else if (rule.kind === "all_present" && !absent.length) {
        text("all_present", { PRESENT: here.join(" and ") });
      } else if (rule.kind === "file_absent") {
        text("file_absent", { PRESENT: here.join(", "), FILE: rule.file });
      }
    }
    return out;
  }

  // ----- rendering -----

  function renderNotices() {
    noticeBox.replaceChildren(
      ...notices.map((notice) => {
        const card = document.createElement("div");
        card.className = "note-card";
        const message = document.createElement("p");
        message.textContent = notice.text;
        card.appendChild(message);
        if (notice.actions) {
          const actions = document.createElement("div");
          actions.className = "notice-actions";
          for (const action of notice.actions) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "button button-small button-secondary";
            button.textContent = action.label;
            button.addEventListener("click", action.run);
            actions.appendChild(button);
          }
          card.appendChild(actions);
        }
        return card;
      }),
    );
  }

  function renderSelectionList() {
    const sorted = [...picked].map((id) => policies.get(id)).sort((a, b) => a.name.localeCompare(b.name));
    if (!sorted.length) {
      selList.replaceChildren(emptyNode);
      return;
    }
    const list = document.createElement("ul");
    list.className = "sel-items";
    for (const p of sorted) {
      const item = document.createElement("li");
      item.className = "sel-item";
      item.dataset.policyId = p.id;
      const chip = $(`.bmember[data-policy-id='${p.id}'] .label`);
      if (chip) item.appendChild(chip.cloneNode(true));
      const name = document.createElement("span");
      name.className = "sel-name";
      name.textContent = p.name;
      item.appendChild(name);
      const says = document.createElement("span");
      says.className = "sel-says";
      says.textContent = p.says;
      item.appendChild(says);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove";
      remove.textContent = T.remove;
      remove.setAttribute("aria-label", fill(T.remove_label, { name: p.name }));
      remove.addEventListener("click", () => removePick(p));
      item.appendChild(remove);
      list.appendChild(item);
    }
    selList.replaceChildren(list);
  }

  function renderNotes() {
    const items = warnings();
    const key = items.join("\n");
    if (key === notesKey) return;
    notesKey = key;
    notesBox.replaceChildren(
      ...items.map((message) => {
        const card = document.createElement("p");
        card.className = "note-card";
        card.textContent = message;
        return card;
      }),
    );
  }

  function showTab(name) {
    activeTab = name;
    const active = picked.size > 0;
    for (const tab of tabs) {
      const on = active && tab.id === `tab-${name}`;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
    }
    for (const panel of panels) panel.hidden = !(active && panel.id === `panel-${name}`);
  }

  function renderOutputs() {
    const active = picked.size > 0;
    needOne.hidden = active;
    for (const tab of tabs) tab.disabled = !active;
    if (!active) {
      codeEl.textContent = "";
      codeEl.removeAttribute("data-selection-code");
      shareEl.value = "";
      shareEl.removeAttribute("data-selection-url");
      showTab(activeTab);
      return;
    }
    const code = encodeSelection(buildSelection());
    const url = `${location.origin}${location.pathname}#s=${code}`;
    codeEl.textContent = site.command.replace("__CODE__", () => code);
    codeEl.dataset.selectionCode = code;
    shareEl.value = url;
    shareEl.setAttribute("data-selection-url", url);
    showTab(activeTab);
  }

  function syncStart() {
    const ids = [...picked];
    const match = presets.find((p) => sameMembers(p.members, ids));
    start.value = match ? match.id : "";
  }

  function writeFragment() {
    const base = `${location.pathname}${location.search}`;
    const next = picked.size ? `${base}#s=${encodeSelection(buildSelection())}` : base;
    history.replaceState(null, "", next);
  }

  function render(writeUrl = true) {
    for (const box of $$(".bmember input[type='checkbox']")) box.checked = picked.has(box.value);
    selCount.textContent = picked.size === 1 ? T.count_one : fill(T.count_many, { n: picked.size });
    renderSelectionList();
    renderNotes();
    renderOutputs();
    syncStart();
    if (writeUrl) writeFragment();
  }

  // ----- filters -----

  const descriptions = new Map(site.policies.map((p) => [p.id, p.description.toLowerCase()]));

  function rowMatches(row, withLabel) {
    if (withLabel && labelOn.size && !labelOn.has(row.dataset.label)) return false;
    const q = search.value.trim().toLowerCase();
    if (!q) return true;
    const haystack = `${row.dataset.policyId} ${row.textContent.toLowerCase()} ${descriptions.get(row.dataset.policyId) || ""}`;
    return haystack.includes(q);
  }

  function applyFilters() {
    const shown = new Set();
    for (const row of rows) {
      const visible = rowMatches(row, true);
      row.classList.toggle("hidden", !visible);
      if (visible) shown.add(row.dataset.policyId);
    }
    for (const group of groups) {
      group.classList.toggle("hidden", !$$(".bmember:not(.hidden)", group).length);
    }
    for (const chip of chips) {
      const count = new Set(
        rows
          .filter((row) => row.dataset.label === chip.dataset.value && rowMatches(row, false))
          .map((row) => row.dataset.policyId),
      ).size;
      $(".chip-count", chip).textContent = String(count);
    }
    status.textContent = fill(T.showing, { shown: shown.size, total: policies.size });
  }

  for (const chip of chips) {
    chip.addEventListener("click", () => {
      const value = chip.dataset.value;
      if (labelOn.has(value)) labelOn.delete(value);
      else labelOn.add(value);
      chip.setAttribute("aria-pressed", String(labelOn.has(value)));
      applyFilters();
    });
  }
  search.addEventListener("input", applyFilters);

  // ----- changing the picks -----

  function dropPendingNotices() {
    notices = notices.filter((notice) => !notice.pending);
    renderNotices();
  }

  function removePick(policy) {
    const buttons = $$(".sel-item .remove");
    const index = buttons.findIndex((button) => button.closest(".sel-item").dataset.policyId === policy.id);
    picked.delete(policy.id);
    dropPendingNotices();
    render();
    announce(fill(T.removed, { name: policy.name }));
    const left = $$(".sel-item .remove");
    (left[Math.min(index, left.length - 1)] || start).focus();
  }

  $(".groups").addEventListener("change", (event) => {
    const box = event.target;
    if (!(box instanceof HTMLInputElement) || box.type !== "checkbox") return;
    const policy = policies.get(box.value);
    if (box.checked) picked.add(box.value);
    else picked.delete(box.value);
    dropPendingNotices();
    render();
    announce(fill(box.checked ? T.added : T.removed, { name: policy.name }));
  });

  start.addEventListener("change", () => {
    const preset = presets.find((p) => p.id === start.value);
    const next = new Set(preset ? preset.members : []);
    const lost = [...picked].some((id) => !next.has(id));
    if (lost && !window.confirm(T.confirm_replace)) {
      syncStart();
      return;
    }
    picked = next;
    dropPendingNotices();
    render();
    announce(preset ? fill(T.preset_applied, { title: preset.title }) : T.cleared);
  });

  selList.addEventListener("click", (event) => {
    if (event.target === emptyNode) start.focus();
  });

  // ----- outputs: tabs, copy, download -----

  for (const tab of tabs) {
    tab.addEventListener("click", () => showTab(tab.id.replace("tab-", "")));
    tab.addEventListener("keydown", (event) => {
      const enabled = tabs.filter((t) => !t.disabled);
      const at = enabled.indexOf(tab);
      let next = null;
      if (event.key === "ArrowRight") next = enabled[(at + 1) % enabled.length];
      else if (event.key === "ArrowLeft") next = enabled[(at - 1 + enabled.length) % enabled.length];
      else if (event.key === "Home") next = enabled[0];
      else if (event.key === "End") next = enabled[enabled.length - 1];
      if (!next) return;
      event.preventDefault();
      showTab(next.id.replace("tab-", ""));
      next.focus();
    });
  }

  $("#copy-command").addEventListener("click", (event) => {
    copyText(event.currentTarget, codeEl.textContent, codeEl);
  });
  $("#copy-share").addEventListener("click", (event) => {
    copyText(event.currentTarget, shareEl.value, shareEl);
  });
  $("#download-file").addEventListener("click", () => {
    const body = `${JSON.stringify(buildSelection(), null, 2)}\n`;
    const url = URL.createObjectURL(new Blob([body], { type: "application/x-yaml" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = T.download_name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  // ----- the fragment on load -----

  function notAvailable(ids) {
    return { text: fill(T.not_available, { ids: ids.join(", ") }) };
  }

  function restore(ids) {
    const known = ids.filter((id) => policies.has(id));
    const dropped = ids.filter((id) => !policies.has(id));
    picked = new Set(known);
    if (dropped.length) notices.push(notAvailable(dropped));
  }

  // Returns false when the fragment must stay as it was (nothing was applied).
  function loadFragment() {
    const found = /^(s|preset|add)=(.*)$/.exec(location.hash.slice(1));
    if (!found) return true;
    const [, key, value] = found;
    if (key === "preset") {
      const preset = presets.find((p) => p.id === value);
      if (preset) picked = new Set(preset.members);
      else notices.push({ text: fill(T.preset_unknown, { id: value }) });
      return true;
    }
    if (key === "add") {
      if (policies.has(value)) picked = new Set([value]);
      else notices.push(notAvailable([value]));
      return true;
    }
    let selection = null;
    try {
      selection = decodeSelection(value);
    } catch {
      selection = null;
    }
    const entries = selection && Array.isArray(selection.policies) ? selection.policies : null;
    if (!entries || !entries.every((entry) => entry && typeof entry.id === "string")) {
      notices.push({ text: T.link_unreadable });
      return false;
    }
    const ids = entries.map((entry) => entry.id);
    const theirs = selection.catalog && typeof selection.catalog.ref === "string" ? selection.catalog.ref : "";
    if (theirs === site.catalog.ref) {
      restore(ids);
      return true;
    }
    notices.push({
      pending: true,
      text: fill(T.ref_mismatch, { theirs: theirs.slice(0, 12), ours: site.catalog.ref.slice(0, 12) }),
      actions: [
        {
          label: T.use_same,
          run: () => {
            dropPendingNotices();
            restore(ids);
            renderNotices();
            render();
          },
        },
        {
          label: T.start_fresh,
          run: () => {
            dropPendingNotices();
            render();
          },
        },
      ],
    });
    return false;
  }

  // On load, and when the visitor pastes another link into this tab.
  function applyFragment() {
    picked = new Set();
    notices = [];
    const writeUrl = loadFragment();
    renderNotices();
    applyFilters();
    render(writeUrl);
  }

  window.addEventListener("hashchange", applyFragment);
  applyFragment();
}

main();
