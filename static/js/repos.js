// The Git repositories builder: the shared start screen (quiz.js, section "repos"), then one block of
// commands for the picked policies. Everything runs in the browser. The catalog commit and every
// sha256 come from site.json, which the site build wrote; a share link (#p=) carries policy ids, the host and the CI choice.
import { copyText, labelChip } from "./common.js";
import { initQuiz } from "./quiz.js";

const $ = (selector, root = document) => root.querySelector(selector);

// {name} placeholders, filled in one pass; a name without a value stays as written.
const fill = (text, values) =>
  text.replace(/\{(\w+)\}/g, (match, key) => (Object.hasOwn(values, key) ? String(values[key]) : match));

// One value as a single POSIX sh argument: Python's shlex.quote rule, the twin of sitegen/repodata.py
// shell_arg (tests/e2e/test_repos.py pins them equal). Safe characters stay as written; anything else is
// wrapped in single quotes, with each single quote closed, escaped and reopened.
export function shellArg(value) {
  const text = String(value);
  if (text === "") return "''";
  if (/^[\w@%+=:,./-]+$/.test(text)) return text;
  return `'${text.replace(/'/g, `'"'"'`)}'`;
}

// A command line: `fill` with every value passed through shellArg (sitegen/repodata.py shell_line).
export function shellLine(template, values) {
  const quoted = {};
  for (const [key, value] of Object.entries(values)) quoted[key] = shellArg(value);
  return fill(template, quoted);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// The ids a `#p=a,b,c&host=github&ci=1` fragment names that the catalog has, and the others it names, plus
// its host (one of `hosts`, else null) and CI choice (true, false or null); null without `#p=`.
export function parseShare(hash, known, hosts = []) {
  const match = /^#p=(.*?)(?:&host=([a-z0-9-]+))?(?:&ci=([01]))?$/.exec(hash);
  if (!match) return null;
  const host = hosts.includes(match[2]) ? match[2] : null;
  const ci = host && match[3] ? match[3] === "1" : null;
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
  return { ids, unknown, host, ci };
}

// The setup commands for picked ids: init, one add per policy sorted by id, sync, then the review note. Every value
// is shell-quoted, so an id, ref or sha256 is one argument whatever characters it carries.
export function commandLines(site, ids, ci) {
  const byId = new Map(site.policies.map((p) => [p.id, p]));
  const commands = site.repos.commands;
  const lines = [commands.init];
  for (const id of [...ids].sort()) {
    lines.push(shellLine(commands.add, { id, ref: site.catalog.ref, sha256: byId.get(id).sha256 }));
  }
  lines.push(ci ? commands.sync_ci : commands.sync);
  lines.push(commands.review);
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
  const hostIds = hostQuestion.options.map((o) => o.id);
  let host = null;
  let ci = false;
  let pinned = null;
  let answeredHost = null;

  const hostCi = (id) => hostQuestion.options.find((o) => o.id === id).ci;

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
    if (pinned) {
      ({ host, ci } = pinned);
      pinned = null;
      answeredHost = answers.host;
    } else if (answeredHost !== answers.host) {
      answeredHost = answers.host;
      host = answeredHost;
      ci = hostCi(host);
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

    const shareFor = () =>
      `${location.origin}${location.pathname}#p=${[...ids].sort().join(",")}&host=${host}&ci=${ci ? 1 : 0}`;
    let shareUrl = shareFor();
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
      shareUrl = shareFor();
      shareInput.value = shareUrl;
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
    const share = parseShare(location.hash, known, hostIds);
    if (!share) return null;
    const notes = [];
    if (share.unknown.length) notes.push(unknownText(share.unknown));
    if (share.ids.length) notes.push(T.shared_note);
    notify(notes);
    if (share.ids.length && share.host) pinned = { host: share.host, ci: share.ci ?? hostCi(share.host) };
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
