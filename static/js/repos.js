// The Git repositories builder: the shared start screen (quiz.js, section "repos"), then one block of
// commands for the picked policies. Everything runs in the browser. The catalog commit and every
// sha256 come from site.json, which the site build wrote; a share link (#p=) carries policy ids only.
import { copyText, labelChip } from "./common.js";
import { initQuiz } from "./quiz.js";

const $ = (selector, root = document) => root.querySelector(selector);

// {name} placeholders, filled in one pass; a name without a value stays as written.
const fill = (text, values) =>
  text.replace(/\{(\w+)\}/g, (match, key) => (Object.hasOwn(values, key) ? String(values[key]) : match));

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// The ids a `#p=a,b,c` fragment names that the catalog has, and the others it names; null without `#p=`.
export function parseShare(hash, known) {
  const match = /^#p=(.*)$/.exec(hash);
  if (!match) return null;
  let raw = match[1];
  try {
    raw = decodeURIComponent(raw);
  } catch {
    // keep the raw text; unknown ids are dropped below
  }
  const ids = [];
  const unknown = [];
  for (const part of raw.split(",")) {
    const id = part.trim();
    if (!id) continue;
    const list = known.has(id) ? ids : unknown;
    if (!list.includes(id)) list.push(id);
  }
  return { ids, unknown };
}

// The setup commands for picked ids: init, one add per policy sorted by id, sync, commit.
export function commandLines(site, ids, ci) {
  const byId = new Map(site.policies.map((p) => [p.id, p]));
  const commands = site.repos.commands;
  const lines = [commands.init];
  for (const id of [...ids].sort()) {
    lines.push(fill(commands.add, { id, ref: site.catalog.ref, sha256: byId.get(id).sha256 }));
  }
  lines.push(ci ? commands.sync_ci : commands.sync);
  lines.push(commands.commit);
  return lines;
}

export function scriptText(site, lines) {
  return `${[...site.repos.commands.script_header, ...lines].join("\n")}\n`;
}

function saveFile(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/x-shellscript" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function main() {
  const site = await (await fetch("/data/site.json")).json();
  const repos = site.repos;
  const T = repos.quiz.texts;
  const known = new Set(site.policies.map((p) => p.id));
  const tiers = new Map(repos.tiers.map((tier) => [tier.key, tier]));
  const hostQuestion = repos.quiz.questions.find((q) => q.id === "host");
  const noticeBox = $("#link-notice");
  let host = null;
  let ci = false;

  function notify(texts) {
    noticeBox.replaceChildren(
      ...texts.map((text) => {
        const card = element("div", "note-card");
        card.appendChild(element("p", "", text));
        return card;
      }),
    );
  }

  function unknownText(unknown) {
    const shown = unknown.slice(0, 5).map((id) => (id.length > 40 ? `${id.slice(0, 40)}…` : id));
    const more = unknown.length > 5 ? `, ${fill(T.unknown_more, { n: unknown.length - 5 })}` : "";
    return fill(T.unknown, { ids: shown.join(", ") + more });
  }

  // The result's output: the commands, Copy, Download and the share link.
  function outputs(ids, { answers }) {
    if (host !== answers.host) {
      host = answers.host;
      ci = hostQuestion.options.find((o) => o.id === host).ci;
    }
    const box = element("div", "quiz-command");
    box.appendChild(element("h3", "quiz-command-title", T.command_label));
    const toggle = element("label", "quiz-ci");
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = ci;
    toggle.append(check, element("span", "", T.ci_label));
    box.appendChild(toggle);
    const pre = element("pre");
    const codeEl = element("code", "language-bash");
    codeEl.dataset.quizCommand = "";
    pre.appendChild(codeEl);
    box.appendChild(pre);

    const actions = element("div", "quiz-actions");
    const copy = element("button", "button button-primary", T.copy);
    copy.type = "button";
    const download = element("button", "button button-secondary", T.download);
    download.type = "button";
    const share = element("button", "button button-secondary", T.share);
    share.type = "button";
    actions.append(copy, download, share);
    box.appendChild(actions);

    const shareUrl = `${location.origin}${location.pathname}#p=${[...ids].sort().join(",")}`;
    const shareLabel = element("label", "visually-hidden", T.share);
    shareLabel.htmlFor = "quiz-share-url";
    const shareInput = element("input", "share-url");
    shareInput.id = "quiz-share-url";
    shareInput.type = "text";
    shareInput.readOnly = true;
    shareInput.value = shareUrl;
    box.append(shareLabel, shareInput);

    let lines = [];
    const update = () => {
      lines = commandLines(site, ids, ci);
      codeEl.textContent = lines.join("\n");
    };
    check.addEventListener("change", () => {
      ci = check.checked;
      update();
    });
    copy.addEventListener("click", () => copyText(copy, lines.join("\n"), codeEl));
    download.addEventListener("click", () => {
      saveFile(repos.commands.script_name, scriptText(site, lines));
    });
    share.addEventListener("click", () => copyText(share, shareUrl, shareInput));
    update();
    return box;
  }

  const chipFor = (id) => {
    const tier = tiers.get(repos.tier_of[id]);
    return labelChip(tier.key, tier.word, tier.meaning);
  };

  // A share link: unknown ids are dropped and named; the known ones open the result directly.
  function readShare() {
    const share = parseShare(location.hash, known);
    if (!share) return null;
    const notes = [];
    if (share.unknown.length) notes.push(unknownText(share.unknown));
    if (share.ids.length) notes.push(T.shared_note);
    notify(notes);
    return share.ids.length ? share.ids : null;
  }

  const sharedIds = readShare();
  $("#quiz").hidden = false;
  const quiz = initQuiz({ site, section: "repos", chipFor, outputs, picks: sharedIds });
  window.addEventListener("hashchange", () => {
    const ids = readShare();
    if (ids) quiz.openShared(ids);
  });
}

main();
