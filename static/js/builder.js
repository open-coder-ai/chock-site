// The builder: pick an agent and policies, then read the command, share link and selection file.
// Everything runs in the browser. The agent and the picks live in the URL fragment, which browsers
// never send to a server.
import {
  announce,
  buildSelection as selectionFor,
  copyText,
  decodeSelection,
  encodeSelection,
  idList,
  installCommand,
  labelChip,
  parseShareFragment,
  sameMembers,
  sentenceStart,
  shareFragment,
  track,
} from "./common.js";
import { commandOutputs, initQuiz } from "./quiz.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

// Texts from site.json use {name} for runtime values.
const fill = (text, values) =>
  text.replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match));
// The engine's warning rules use __NAME__ tokens, filled in one pass.
const fillTokens = (text, values) =>
  text.replace(/__([A-Z]+)__/g, (match, key) => (key in values ? values[key] : match));

async function loadSite() {
  const response = await fetch("/data/site.json");
  return response.json();
}

// These fragments open the full builder; with none of them the start screen shows first.
// A bare #client=<id> only picks the agent.
const FULL_FRAGMENT = /^#((s|preset|add)=|client=[a-z0-9-]+&p=)/;

async function main() {
  const quizEl = $("#quiz");
  const fullEl = $("#builder-full");
  const showQuiz = (on) => {
    quizEl.hidden = !on;
    fullEl.hidden = on;
  };
  showQuiz(!FULL_FRAGMENT.test(location.hash));
  const site = await loadSite();
  const T = site.builder_texts;
  const policies = new Map(site.policies.map((p) => [p.id, p]));
  const presets = site.presets;
  const C = site.builder_clients;
  let client = C.default;
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
  const bar = $("#mobile-bar");
  const clientInputs = $$("#client-picker input[name='client']");
  const clientParts = $$("[data-client]");
  const labelOn = new Set();
  let notesKey = "";
  let noteCount = 0;

  // ----- the selection object (plan 8.1) -----

  function buildSelection() {
    return selectionFor(site, picked, client);
  }

  // ----- the agent (BV-S1): each policy's own label on it, its command and its steps -----

  // Each policy's label on every agent lives once, in site.policies[].agent_labels.
  const agentLabels = new Map(site.policies.map((p) => [p.id, p.agent_labels]));
  const labelOf = (id) => agentLabels.get(id)[client];

  const gradesAgent = $("#builder-grades-agent");

  function renderClient() {
    gradesAgent.textContent = fill(T.grades_for, { name: C.clients[client].name });
    for (const input of clientInputs) input.checked = input.value === client;
    for (const part of clientParts) part.hidden = part.dataset.client !== client;
    for (const row of rows) {
      const label = labelOf(row.dataset.policyId);
      row.dataset.label = label.keyword;
      const word =
        label.keyword === C.ungraded ? C.texts.ungraded_word : site.label_words.coding[label.keyword];
      const meaning = C.clients[client].meanings[label.keyword];
      $(".label", row).replaceWith(labelChip(label.keyword, word, meaning));
      $(".bsays", row).textContent = sentenceStart(label.says);
    }
  }

  // `redrawQuiz` is false when the quiz's own agent question made the change: it already shows it.
  function setClient(next, redrawQuiz = true) {
    client = next;
    renderClient();
    applyFilters();
    render();
    if (redrawQuiz) quiz.refresh();
  }

  // ----- warnings (plan 8.3) -----

  function warnings() {
    const out = [];
    // A `<key>:many` text, when there is one, is the plural form for more than one policy.
    const text = (key, values, count = 1) => {
      const many = count > 1 && Object.hasOwn(site.warning_texts, `${key}:many`);
      const template = site.warning_texts[many ? `${key}:many` : key];
      if (template) out.push(fillTokens(template, values));
    };
    for (const rule of site.warning_rules) {
      if (rule.kind === "grade") {
        const ids = [...picked].filter((id) => labelOf(id).keyword === rule.grade).sort();
        if (ids.length) text(`grade:${rule.grade}`, { PRESENT: ids.join(", ") }, ids.length);
        continue;
      }
      if (rule.kind === "client") {
        if (picked.size && rule.clients.includes(client)) text("client", { SAYS: rule.says });
        continue;
      }
      // chock install checks this one against the plugins already installed; a browser cannot.
      if (rule.kind === "overlap") continue;
      const here = rule.policies.filter((id) => picked.has(id));
      const absent = rule.policies.filter((id) => !picked.has(id));
      if (!here.length) continue;
      if (rule.kind === "missing_partner" && absent.length) {
        text("missing_partner", { PRESENT: here.join(", "), ABSENT: absent.join(", ") }, here.length);
      } else if (rule.kind === "all_present" && !absent.length) {
        text("all_present", { PRESENT: here.join(" and ") });
      } else if (rule.kind === "file_absent") {
        text("file_absent", { PRESENT: here.join(", "), FILE: rule.file }, here.length);
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
      says.textContent = sentenceStart(labelOf(p.id).says);
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
    noteCount = items.length;
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
    const { code, command } = installCommand(site, buildSelection());
    const url = `${location.origin}${location.pathname}${shareFragment(client, picked)}`;
    codeEl.textContent = command;
    codeEl.dataset.selectionCode = code;
    shareEl.value = url;
    shareEl.setAttribute("data-selection-url", url);
    showTab(activeTab);
  }

  // The phone bar: count, notes and Copy command; hidden while nothing is picked.
  function renderBar() {
    bar.hidden = picked.size === 0;
    let text = selCount.textContent;
    if (noteCount) {
      text += ` ${noteCount === 1 ? T.bar_notes_one : fill(T.bar_notes_many, { n: noteCount })}`;
    }
    $("#mb-count").textContent = text;
  }

  function syncStart() {
    const ids = [...picked];
    const match = presets.find((p) => sameMembers(p.members, ids));
    start.value = match ? match.id : "";
  }

  function writeFragment() {
    const base = `${location.pathname}${location.search}`;
    let next = base;
    if (picked.size) next = `${base}#s=${encodeSelection(buildSelection())}`;
    else if (client !== C.default) next = `${base}#client=${client}`;
    history.replaceState(null, "", next);
  }

  function render(writeUrl = true) {
    for (const box of $$(".bmember input[type='checkbox']")) box.checked = picked.has(box.value);
    selCount.textContent = picked.size === 1 ? T.count_one : fill(T.count_many, { n: picked.size });
    // The author page reads the same fragment form, so the link carries the picks along.
    const authorLink = $("#author-link");
    if (authorLink) authorLink.href = `/coding/author/${shareFragment(client, picked)}`;
    // The report page pre-fills the agent from its query (report.js checks it again).
    const reportLink = $("#report-link");
    if (reportLink) {
      const query = new URLSearchParams({ agent: client, page: location.pathname });
      reportLink.href = `/report/?${query}`;
    }
    renderSelectionList();
    renderNotes();
    renderOutputs();
    renderBar();
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
    if (preset) track("preset-picked", { preset: preset.id });
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
    track("install-copied", { agent: client });
  });
  $("#copy-share").addEventListener("click", (event) => {
    copyText(event.currentTarget, shareEl.value, shareEl);
    track("share-copied");
  });
  $("#mb-copy").addEventListener("click", (event) => {
    copyText(event.currentTarget, codeEl.textContent, codeEl);
    track("install-copied", { agent: client });
  });
  // A real hash jump would fire hashchange; scroll and focus the panel instead.
  $("#mb-jump").addEventListener("click", (event) => {
    event.preventDefault();
    const heading = $("#your-selection");
    heading.tabIndex = -1;
    heading.scrollIntoView();
    heading.focus();
  });
  $("#download-file").addEventListener("click", () => {
    const body = `${JSON.stringify(buildSelection(), null, 2)}\n`;
    const url = URL.createObjectURL(new Blob([body], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = T.download_name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    track("selection-downloaded");
  });

  // ----- the fragment on load -----

  const shownIds = (ids) =>
    idList(ids, (n) => fill(n === 1 ? T.ids_hidden_one : T.ids_hidden_many, { n }));

  function notAvailable(ids) {
    return { text: fill(T.not_available, { ids: shownIds(ids) }) };
  }

  function restore(ids) {
    const known = ids.filter((id) => policies.has(id));
    const dropped = ids.filter((id) => !policies.has(id));
    picked = new Set(known);
    if (dropped.length) notices.push(notAvailable(dropped));
  }

  const knownClient = (id) => Object.hasOwn(C.clients, id);

  // Returns false when the fragment must stay as it was (nothing was applied).
  function loadFragment() {
    const shared = parseShareFragment(location.hash);
    if (shared) {
      if (!knownClient(shared.client)) {
        notices.push({ text: fill(T.client_unknown, { id: shownIds([shared.client]) }) });
        return false;
      }
      client = shared.client;
      if (shared.ids) restore(shared.ids);
      return true;
    }
    const found = /^(s|preset|add)=(.*)$/.exec(location.hash.slice(1));
    if (!found) return true;
    const [, key, value] = found;
    if (key === "preset") {
      const preset = presets.find((p) => p.id === value);
      if (preset) picked = new Set(preset.members);
      else notices.push({ text: fill(T.preset_unknown, { id: shownIds([value]) }) });
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
    // Schema 1 named claude-code only; schema 2 names the agent it was built for.
    if (typeof selection.client === "string" && knownClient(selection.client)) client = selection.client;
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
    client = C.default;
    const writeUrl = loadFragment();
    renderNotices();
    renderClient();
    applyFilters();
    render(writeUrl);
  }

  for (const input of clientInputs) {
    input.addEventListener("change", () => {
      if (!input.checked) return;
      setClient(input.value);
      announce(fill(T.client_chosen, { name: C.clients[client].name }));
    });
  }

  const rowOf = new Map(rows.map((row) => [row.dataset.policyId, row]));
  const quiz = initQuiz({
    site,
    chipFor: (id) => $(".label", rowOf.get(id)),
    keywordOf: (id) => labelOf(id).keyword,
    agent: { get: () => client, set: (id) => setClient(id, false) },
    outputs: (ids, context) => commandOutputs(site, context.T, ids, client),
    onFinish: () => track("quiz-finished"),
    onSkip: () => {
      showQuiz(false);
      start.focus();
    },
  });

  window.addEventListener("hashchange", () => {
    if (!FULL_FRAGMENT.test(location.hash)) return;
    showQuiz(false);
    applyFragment();
    quiz.refresh();
  });
  applyFragment();
  quiz.refresh();
}

main();
