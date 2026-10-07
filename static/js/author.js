// The author page (BV-S2): an interview whose answers fill the copied chock kind
// templates, an advanced view that edits the generated files, catalog picks that
// join the selection, and a readable POSIX setup script the visitor downloads,
// reads and runs. The page never compiles a policy or runs generated code.
import {
  announce,
  copyText,
  decodeSelection,
  labelChip,
  parseShareFragment,
  shareFragment,
} from "./common.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const fill = (text, values) =>
  text.replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match));

const DRAFT_KEY = "chock.author.draft.v1";
// An id is my-<slug>: the my- prefix is reserved for local policies (selection schema).
const ID_RE = /^my-[a-z0-9-]{1,60}$/;
// Control, format, surrogate and private-use characters can hide what a terminal shows.
const HIDDEN = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}]/u;

async function loadJson(path) {
  const response = await fetch(path);
  return response.json();
}

// ----- quoting -----

// A YAML single-quoted scalar: only ' escapes (by doubling).
const sq = (text) => `'${text.replaceAll("'", "''")}'`;

// A YAML double-quoted scalar body: backslash escapes for the special and the hidden.
function dq(text) {
  return text.replace(/[\\"\n\t\r\p{Cc}\p{Cf}\p{Cs}\p{Co}]/gu, (ch) => {
    if (ch === "\\") return "\\\\";
    if (ch === '"') return '\\"';
    if (ch === "\n") return "\\n";
    if (ch === "\t") return "\\t";
    if (ch === "\r") return "\\r";
    const point = ch.codePointAt(0);
    if (point <= 0xff) return `\\x${point.toString(16).padStart(2, "0")}`;
    if (point <= 0xffff) return `\\u${point.toString(16).padStart(4, "0")}`;
    return `\\U${point.toString(16).padStart(8, "0")}`;
  });
}

// A plain scalar when the text is safe on a YAML line, else a single-quoted one.
function yamlStr(text) {
  if (/[\n\t]/.test(text)) return `"${dq(text)}"`;
  const plain = /^[^[\]{}'"\s&*!|>%@`][^#\n]*$/.test(text) && !text.includes(": ") && !/ #/.test(text) && !/\s$/.test(text);
  return plain ? text : sq(text);
}

// A Python "..." literal: backslash escapes, no f-string interpolation.
const pyStr = (text) => `"${text.replace(/[\\"]/g, "\\$&")}"`;

// A Python f-string payload: { and } doubled, " and \ escaped.
const fEsc = (text) => text.replace(/[{}]/g, (ch) => ch + ch).replace(/[\\"]/g, "\\$&");

// ----- the generated text -----

function slugify(name) {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug.startsWith("my-") ? slug : `my-${slug}`;
}

// The engine's __NAME__: title-cased words of the id after the my- prefix.
function nameOf(id) {
  return id
    .replace(/^my-/, "")
    .split("-")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

// Word-wrap for the >-folded YAML blocks.
function wrap(text, width) {
  const out = [];
  let line = "";
  for (const word of text.split(/\s+/)) {
    if (line && line.length + word.length + 1 > width) {
      out.push(line);
      line = "";
    }
    line = line ? `${line} ${word}` : word;
  }
  if (line) out.push(line);
  return out;
}

// The guard's BLOCK pattern: the answer's words in order, any whitespace between,
// a word edge on each end that begins and ends on a word character.
function guardRegex(stop) {
  const words = stop.trim().split(/\s+/).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  let pattern = words.join("\\s+");
  if (/\w/.test(stop.trim()[0])) pattern = `\\b${pattern}`;
  if (/\w/.test(stop.trim().slice(-1))) pattern += "\\b";
  return pattern;
}

// content_regex's pattern: every character literal, spaces as [ ] so the pattern
// never matches its own text.
function contentRegex(stop) {
  return Array.from(stop.trim())
    .map((ch) => (ch === " " ? "[ ]" : ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    .join("");
}

// Eval file contents never carry the refused marker literally: inside each marker
// occurrence spaces become \x20; with no space the first character hex-escapes.
function dqContent(text, marker) {
  if (!marker) return `"${dq(text)}"`;
  const parts = text.split(marker);
  const mangled = marker.includes(" ")
    ? marker.replaceAll(" ", "\\x20")
    : `\\x${marker.codePointAt(0).toString(16).padStart(2, "0")}${marker.slice(1)}`;
  return `"${parts.map(dq).join(mangled)}"`;
}

// The comma-separated file names of a script policy.
function refuseNames(c) {
  return c.answers.stop
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
}

const DESCRIPTIONS = {
  content_regex: (c) =>
    `Refuses an added line that contains "${c.answers.stop}", at commit and when the agent writes a file.`,
  guard: (c) =>
    `Refuses a shell command matching "${c.answers.stop}" before the agent runs it. ` +
    "Best effort: a renamed binary or an alias gets past it.",
  script: (c) =>
    `Refuses a change that writes a file named ${refuseNames(c).join(", ")}, at commit and ` +
    "when the agent writes a file.",
  rule: () => "A rule the agent reads in its context; nothing enforces it.",
  skill: (c) => c.answers.stop,
};

const RULE_TEXT = {
  guard: (c) => `    never(run): ${c.answers.stop}`,
  rule: (c) =>
    `    never: ${c.answers.stop}` +
    (c.answers.message ? `\n    instead: ${c.answers.message}` : ""),
  skill: (c) => `    on(${c.answers.stop}): follow(skill ${c.id})`,
};

// The `execute:` body for one eval case, named by the case's `execute` in author.yaml.
const EXECUTE = {
  content_regex: {
    refuse_commit: (c) =>
      `files:\n  'notes.py': ${dqContent(`${c.answers.refuse_example}\n`, c.answers.stop)}\nexpect: block`,
    pass_commit: (c) =>
      `files:\n  'notes.py': ${dqContent(`${c.answers.pass_example}\n`, c.answers.stop)}\nexpect: allow`,
    refuse_write: (c) =>
      `event: tool_use\nwrites:\n  'notes.py': ${dqContent(`${c.answers.refuse_example}\n`, c.answers.stop)}\nexpect: block`,
    pass_write: (c) =>
      `event: tool_use\nwrites:\n  'notes.py': ${dqContent(`${c.answers.pass_example}\n`, c.answers.stop)}\nexpect: allow`,
  },
  guard: {
    refuse_cmd: (c) => `command: ${yamlStr(c.answers.stop)}\nexpect: block`,
    refuse_sudo: (c) => `command: ${yamlStr(`sudo ${c.answers.stop}`)}\nexpect: block`,
    refuse_shc: (c) => `command: ${yamlStr(`sh -c "${c.answers.stop}"`)}\nexpect: block`,
    pass_cmd: (c) => `command: ${yamlStr(c.answers.pass_example)}\nexpect: allow`,
  },
  script: {
    refuse_commit: (c) =>
      `files:\n  ${sq(c.answers.refuse_example)}: "{}\\n"\nexpect: block`,
    pass_commit: (c) =>
      `files:\n  ${sq(c.answers.pass_example)}: "x = 1\\n"\nexpect: allow`,
    refuse_write: (c) =>
      `event: tool_use\nwrites:\n  ${sq(c.answers.refuse_example)}: "{}\\n"\nexpect: block`,
    pass_write: (c) =>
      `event: tool_use\nwrites:\n  ${sq(c.answers.pass_example)}: "x = 1\\n"\nexpect: allow`,
  },
};

// The eval suite's case list, built from data/author.yaml's per-kind cases.
function evalCases(ctx) {
  return ctx.spec.evals
    .map((test, i) => {
      let out =
        `  - id: tc-${String(i + 1).padStart(3, "0")}\n` +
        `    category: ${test.category}\n` +
        `    prompt: ${yamlStr(fill(test.prompt, ctx.answers))}\n` +
        `    expect: ${yamlStr(fill(test.expect, ctx.answers))}\n`;
      if (test.execute)
        out += `    execute:\n${EXECUTE[ctx.kind][test.execute](ctx).replace(/^/gm, "      ")}\n`;
      return out;
    })
    .join("");
}

// Builders named by each edit's `put`; ctx carries kind, id, name, answers, spec, cfg.
const BUILDERS = {
  description: (c) =>
    `description: >\n${wrap(DESCRIPTIONS[c.kind](c), 90)
      .map((l) => `  ${l}`)
      .join("\n")}`,
  message: (c) =>
    `    message: >\n${wrap(`${c.id}: ${c.answers.message}`, 84)
      .map((l) => `      ${l}`)
      .join("\n")}`,
  content_pattern: (c) =>
    `      content_pattern: '${contentRegex(c.answers.stop).replaceAll("'", "''")}'`,
  evals: (c) => `  cases:\n${evalCases(c).replace(/\n$/, "")}`,
  rule_text: (c) => RULE_TEXT[c.kind](c),
  body: (c) =>
    `## Procedure\n\n${c.answers.message
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s, i) => `${i + 1}. ${s}`)
      .join("\n")}\n`,
  guard_comment: () =>
    "#: A command matching BLOCK is refused; spacing differences still match. Built from your answer.",
  block_pattern: (c) => `BLOCK = re.compile(${pyStr(guardRegex(c.answers.stop))})`,
  guard_message: (c) => `        print(${pyStr(`${c.id}: ${c.answers.message}`)}, file=sys.stderr)`,
  script_comment: () => "#: A write whose file name is in REFUSE is refused before it lands.",
  refuse_set: (c) => `REFUSE = {${refuseNames(c).map(pyStr).join(", ")}}`,
  script_message: (c) =>
    `        print(f"${fEsc(`${c.id}: `)}{', '.join(refused)}${fEsc(` ${c.answers.message}`)}", file=sys.stderr)`,
  drop: () => "",
};

// ----- template fill and edits -----

function fillTokens(text, tokens) {
  for (const [token, value] of Object.entries(tokens)) text = text.replaceAll(token, value);
  return text;
}

// One edit op: `find` replaces the anchor's first occurrence; `lines` removes the
// anchor line and any following more-indented lines; `from` replaces to end of file.
// Builders return the replacement text without a trailing newline.
function applyEdit(text, edit, tokens, ctx) {
  const op = ["find", "lines", "from"].find((key) => edit[key]);
  const anchor = fillTokens(edit[op], tokens);
  const put = BUILDERS[edit.put](ctx);
  if (op === "find") return text.replace(anchor, put);
  const lines = text.split("\n");
  const at = lines.findIndex((line) => line.includes(anchor));
  if (at === -1) return text;
  if (op === "from") return `${lines.slice(0, at).join("\n")}\n${put}\n`;
  const indent = lines[at].match(/^ */)[0].length;
  let end = at + 1;
  while (end < lines.length && (lines[end].match(/^ */)[0].length > indent || !lines[end].trim()))
    end += 1;
  lines.splice(at, end - at, ...(put === "" ? [] : [put]));
  return lines.join("\n");
}

// The kind's files after token fill and the edit plan: [{path, text}] inside the policy folder.
function buildFiles(spec, ctx, tokens) {
  return Object.entries(spec.files).map(([path, text]) => ({
    path: fillTokens(path, tokens),
    text: spec.edits
      .filter((edit) => edit.file === path)
      .reduce((body, edit) => applyEdit(body, edit, tokens, ctx), fillTokens(text, tokens)),
  }));
}

// ----- chock.lock.compute_pack_hash in the browser -----

async function sha256bytes(parts) {
  const total = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const part of parts) {
    total.set(part, at);
    at += part.length;
  }
  const digest = await crypto.subtle.digest("SHA-256", total);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

// The text a file's quoted heredoc writes: it always ends in a newline.
const asWritten = (text) => (text.endsWith("\n") ? text : `${text}\n`);

// The pack hash over a policy's {path, text} files, sorted by POSIX path as the engine sorts.
function packHash(files) {
  const enc = new TextEncoder();
  const parts = [];
  for (const file of [...files].sort((a, b) => (a.path < b.path ? -1 : 1)))
    parts.push(
      enc.encode(file.path),
      new Uint8Array([0]),
      enc.encode(asWritten(file.text)),
      new Uint8Array([0]),
    );
  return sha256bytes(parts);
}

const scriptHash = (text) => sha256bytes([new TextEncoder().encode(text)]);

// ----- the selection file -----

// A schema-2 selection: the local policy first, then the catalog picks.
function selectionYaml(hash, ctx, site, picked, client) {
  const lines = [
    "schema: 2",
    `client: ${client}`,
    "bundle:",
    `  name: ${ctx.cfg.bundle_name}`,
    `  version: ${sq(ctx.version)}`,
  ];
  if (picked.size) {
    const catalog = site.catalog;
    lines.push("catalog:", `  source: ${yamlStr(catalog.source)}`, `  ref: ${catalog.ref}`);
    if (catalog.release) lines.push(`  release: ${sq(catalog.release)}`);
  }
  lines.push(
    "policies:",
    "- from: local",
    `  id: ${ctx.id}`,
    `  path: .agents/policies/${ctx.id}`,
    `  sha256: ${hash}`,
    `  version: ${sq(ctx.version)}`,
  );
  const byId = new Map(site.policies.map((p) => [p.id, p]));
  for (const id of [...picked].sort()) {
    const policy = byId.get(id);
    lines.push(
      "- from: catalog",
      `  id: ${id}`,
      `  version: ${sq(policy.version)}`,
      `  sha256: ${policy.sha256}`,
    );
  }
  return `${lines.join("\n")}\n`;
}

// ----- the setup script -----

// A quoted-heredoc delimiter that never occurs in the content.
function heredocDelim(text, base) {
  let delim = base;
  while (text.includes(delim)) delim += "_X";
  return delim;
}

// The POSIX script: asks, writes the files, chock check, then chock install
// (install mode adds --apply where the agent's own install step was witnessed).
function buildScript(files, selection, hash, ctx, site, client, clients) {
  const cfg = ctx.cfg;
  const lines = [
    "#!/bin/sh",
    `# Written by chock.sh/coding/author/ for the policy ${ctx.id}.`,
    "#",
    "# In order, it:",
    "#   1. asks you for the agent, the folder, and build-only or install;",
    "#   2. writes chock.selection.yaml and the policy files under that folder",
    "#      (every file below is a quoted heredoc, readable in full);",
    "#   3. runs chock check --repo <folder> --only validate,evals and stops on failure;",
    "#   4. runs chock install --selection <folder>/chock.selection.yaml",
    "#      --client <agent> --trust-local <id>=<sha256>; the sha256 pins exactly",
    "#      the policy code in this script, which you accepted by reading it;",
    "#   5. answering install also passes --apply, the agent's own install step,",
    "#      but only where that step has been witnessed; otherwise it says so.",
    "#",
    "# Nothing is fetched from the network except chock's own pinned catalog fetch,",
    "# and only when catalog policies are in the selection. Read it before running.",
    "set -eu",
    "",
    "# --- the questions -----------------------------------------------------------",
  ];
  const ids = clients.join(", ");
  // Single-quoted and double-quoted shell literals.
  const shQ = (text) => `'${text.replaceAll("'", "'\"'\"'")}'`;
  const shDq = (text) => text.replace(/["\\$`]/g, "\\$&");
  lines.push(
    `printf '%s ' ${shQ(`${cfg.agent_prompt} (${ids}) [${client}]:`)}`,
    "read -r AGENT",
    `AGENT=\${AGENT:-${client}}`,
    `case "$AGENT" in ${clients.join("|")}) ;; *) echo "Unknown agent: $AGENT" >&2; exit 1;; esac`,
    "",
    `printf '%s ' ${shQ(`${cfg.folder_prompt} [${cfg.default_folder}]:`)}`,
    "read -r FOLDER",
    `FOLDER=\${FOLDER:-${cfg.default_folder}}`,
    `printf '%s' "$FOLDER" | LC_ALL=C grep -q '[^ -~]' && { echo "The folder must be printable ASCII." >&2; exit 1; } || true`,
    `case "$FOLDER" in -*) echo "The folder must not start with -." >&2; exit 1;; esac`,
    "",
    `printf '%s ' ${shQ(`${cfg.mode_prompt} [${cfg.default_mode}]:`)}`,
    "read -r MODE",
    `MODE=\${MODE:-${cfg.default_mode}}`,
    `case "$MODE" in build|install) ;; *) echo "Answer build or install." >&2; exit 1;; esac`,
    "",
    "# --- the files ---------------------------------------------------------------",
    `mkdir -p "$FOLDER/.agents/policies/${ctx.id}"`,
  );
  const dirs = [
    ...new Set(files.map((f) => f.path.split("/").slice(0, -1).join("/")).filter(Boolean)),
  ];
  for (const dir of dirs) lines.push(`mkdir -p "$FOLDER/.agents/policies/${ctx.id}/${dir}"`);
  const selDelim = heredocDelim(selection, "CHOCK_SELECTION_YAML");
  lines.push(
    `cat > "$FOLDER/chock.selection.yaml" <<'${selDelim}'`,
    selection.replace(/\n$/, ""),
    selDelim,
  );
  files.forEach((file, i) => {
    const delim = heredocDelim(file.text, `CHOCK_FILE_${i + 1}`);
    lines.push(
      `cat > "$FOLDER/.agents/policies/${ctx.id}/${file.path}" <<'${delim}'`,
      file.text.replace(/\n$/, ""),
      delim,
    );
    if (file.path.startsWith("implementations/"))
      lines.push(`chmod +x "$FOLDER/.agents/policies/${ctx.id}/${file.path}"`);
  });
  lines.push(
    "",
    "# --- the checks --------------------------------------------------------------",
    'chock check --repo "$FOLDER" --only validate,evals',
    "",
    "# --- the plugin --------------------------------------------------------------",
  );
  const witnessed = clients.filter((id) => site.builder_clients.clients[id].witness === "witnessed");
  const note = ctx.untested.split("{agent}").map(shDq).join("$AGENT");
  lines.push(
    'APPLY=""',
    'if [ "$MODE" = "install" ]; then',
    '  case "$AGENT" in',
    ...(witnessed.length ? [`    ${witnessed.join("|")}) APPLY="--apply" ;;`] : []),
    `    *) echo "${note}" ;;`,
    "  esac",
    "fi",
    `chock install --selection "$FOLDER/chock.selection.yaml" --client "$AGENT" --trust-local ${ctx.id}=${hash} $APPLY`,
    'echo "Done."',
    "",
  );
  return lines.join("\n");
}

// ----- validation -----

function validate(ctx, T) {
  const errors = [];
  if (!ID_RE.test(ctx.id)) errors.push(T.id_invalid);
  for (const field of ctx.spec.fields)
    if (!field.optional && !ctx.answers[field.key]?.trim()) errors.push(T.required);
  const hidden = Object.values(ctx.answers).some((a) => HIDDEN.test(a.replace(/[\n\t]/g, "")));
  if (hidden) errors.push(T.control_chars);
  if (errors.length) return errors;
  const { stop, refuse_example, pass_example } = ctx.answers;
  if (ctx.kind === "content_regex") {
    if (!refuse_example.includes(stop)) errors.push(T.refuse_match);
    if (pass_example.includes(stop)) errors.push(T.pass_match);
  }
  if (ctx.kind === "guard") {
    const regex = new RegExp(guardRegex(stop));
    if (!regex.test(refuse_example)) errors.push(T.refuse_pattern);
    if (regex.test(pass_example)) errors.push(T.pass_pattern);
  }
  if (ctx.kind === "script") {
    if (/[\r\n\t]/.test(refuse_example) || /[\r\n\t]/.test(pass_example))
      errors.push(T.control_chars);
    const names = refuseNames(ctx);
    const base = (path) => path.trim().split("/").filter(Boolean).pop() || "";
    if (!names.includes(base(refuse_example))) errors.push(T.refuse_name);
    if (names.includes(base(pass_example))) errors.push(T.pass_name);
  }
  if (ctx.kind in RULE_TEXT && RULE_TEXT[ctx.kind](ctx).trim().length > 500)
    errors.push(T.rule_too_long);
  return errors;
}

// ----- the page -----

async function main() {
  const [site, author] = await Promise.all([
    loadJson("/data/site.json"),
    loadJson("/data/author.json"),
  ]);
  const T = author.texts;
  const cfg = author.script;
  const kinds = author.kinds;
  const policies = new Map(
    site.policies.filter((p) => p.track === "coding").map((p) => [p.id, p]),
  );
  const C = site.builder_clients;
  const clients = C.order;
  let client = C.default;
  let kind = Object.keys(kinds)[0];
  let name = "";
  let answers = {};
  let picked = new Set();
  let overrides = {};
  let files = [];
  let script = "";

  const nameInput = $("#author-name");
  const fieldsBox = $("#author-fields");
  const filesBox = $("#author-files");
  const catalogList = $("#author-catalog-list");
  const catalogSearch = $("#author-catalog-search");
  const errorsBox = $("#author-errors");
  const errorList = $("#author-error-list");
  const selEl = $("#author-selection");
  const scriptEl = $("#author-script");
  const shaEl = $("#author-sha");
  const noticeBox = $("#link-notice");
  const downloadBtn = $("#author-download");
  const copyBtn = $("#author-copy");
  const shareBtn = $("#author-share");
  const shareUrl = $("#author-share-url");
  const clientInputs = $$("#client-picker input[name='client']");

  const notice = (text) => {
    const card = document.createElement("p");
    card.className = "note-card";
    card.textContent = text;
    noticeBox.replaceChildren(card);
  };

  // ----- draft -----

  let draftTimer = 0;
  function saveDraft() {
    window.clearTimeout(draftTimer);
    draftTimer = window.setTimeout(() => {
      try {
        localStorage.setItem(
          DRAFT_KEY,
          JSON.stringify({ kind, name, answers, picked: [...picked], client, overrides }),
        );
      } catch {
        // A full or blocked localStorage is not an error worth showing.
      }
    }, 300);
  }

  function loadDraft() {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  // ----- the interview -----

  function renderFields() {
    fieldsBox.replaceChildren(
      ...kinds[kind].fields.map((field) => {
        const div = document.createElement("div");
        div.className = "field author-field";
        const label = document.createElement("label");
        label.htmlFor = `af-${field.key}`;
        label.textContent = field.label;
        div.appendChild(label);
        const input = field.area
          ? document.createElement("textarea")
          : document.createElement("input");
        input.id = `af-${field.key}`;
        input.dataset.key = field.key;
        if (!field.area) input.type = "text";
        input.autocomplete = "off";
        input.spellcheck = false;
        if (field.area) input.rows = 3;
        input.placeholder = field.example || "";
        input.value = answers[field.key] || "";
        input.addEventListener("input", () => {
          answers[field.key] = input.value;
          schedule(true);
        });
        div.appendChild(input);
        const hint = document.createElement("p");
        hint.className = "hint";
        hint.textContent = field.hint;
        div.appendChild(hint);
        return div;
      }),
    );
  }

  function renderCatalog() {
    const q = catalogSearch.value.trim().toLowerCase();
    catalogList.replaceChildren(
      ...[...policies.values()]
        .filter(
          (p) => !q || `${p.id} ${p.name} ${p.description}`.toLowerCase().includes(q),
        )
        .map((p) => {
          const label = document.createElement("label");
          label.className = "amember";
          const box = document.createElement("input");
          box.type = "checkbox";
          box.value = p.id;
          box.checked = picked.has(p.id);
          box.addEventListener("change", () => {
            if (box.checked) picked.add(p.id);
            else picked.delete(p.id);
            writeShare();
            schedule(false);
          });
          label.appendChild(box);
          label.appendChild(labelChip(p.keyword, site.label_words.coding[p.keyword], C.meanings[p.keyword]));
          const nameEl = document.createElement("span");
          nameEl.className = "amember-name";
          nameEl.textContent = `${p.name} — ${p.says}`;
          label.appendChild(nameEl);
          return label;
        }),
    );
  }

  // ----- the file view -----

  function buildFileBox(file) {
    const wrapEl = document.createElement("div");
    wrapEl.className = "afile";
    const head = document.createElement("div");
    head.className = "afile-head";
    const code = document.createElement("code");
    code.textContent = file.path;
    head.appendChild(code);
    const edited = document.createElement("span");
    edited.className = "afile-edited";
    edited.textContent = T.file_edited;
    edited.hidden = !(file.path in overrides);
    head.appendChild(edited);
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "linkish areset";
    reset.textContent = T.advanced_reset;
    reset.hidden = !(file.path in overrides);
    reset.addEventListener("click", () => {
      delete overrides[file.path];
      schedule(true);
    });
    head.appendChild(reset);
    wrapEl.appendChild(head);
    const area = document.createElement("textarea");
    area.className = "afile-text";
    area.setAttribute("aria-label", file.path);
    area.spellcheck = false;
    area.rows = Math.min(16, file.text.split("\n").length + 1);
    area.value = file.text;
    area.addEventListener("input", () => {
      overrides[file.path] = area.value;
      schedule(false);
    });
    wrapEl.appendChild(area);
    return wrapEl;
  }

  // Rebuild the editors: fresh rows on a kind change, synced text on an answer change.
  function renderFiles(fresh) {
    if (fresh) {
      filesBox.replaceChildren(...files.map(buildFileBox));
      return;
    }
    const boxes = new Map($$(".afile", filesBox).map((box) => [$("code", box).textContent, box]));
    for (const file of files) {
      const box = boxes.get(file.path);
      if (!box) continue;
      const area = $(".afile-text", box);
      const isEdited = file.path in overrides;
      $(".afile-edited", box).hidden = !isEdited;
      $(".areset", box).hidden = !isEdited;
      if (!isEdited && area.value !== file.text) area.value = file.text;
    }
  }

  // ----- generation -----

  function ctx() {
    const id = slugify(name);
    return {
      kind,
      id,
      name: nameOf(id),
      answers,
      spec: kinds[kind],
      cfg,
      untested: T.untested_note,
      version: "0.1.0",
    };
  }

  async function update(freshFiles) {
    const c = ctx();
    const tokens = {
      __ID__: c.id,
      __NAME__: c.name,
      __DATE__: new Date().toISOString().slice(0, 10),
    };
    files = buildFiles(c.spec, c, tokens);
    for (const file of files) if (file.path in overrides) file.text = overrides[file.path];
    renderFiles(freshFiles);
    const errors = validate(c, T);
    errorsBox.hidden = errors.length === 0;
    errorList.replaceChildren(
      ...[...new Set(errors)].map((text) => {
        const item = document.createElement("li");
        item.textContent = text;
        return item;
      }),
    );
    downloadBtn.disabled = copyBtn.disabled = errors.length > 0;
    if (errors.length) {
      selEl.textContent = T.not_ready;
      scriptEl.textContent = T.not_ready;
      shaEl.textContent = "";
      script = "";
      saveDraft();
      return;
    }
    const hash = await packHash(files);
    const selYaml = selectionYaml(hash, c, site, picked, client);
    selEl.textContent = selYaml;
    script = buildScript(files, selYaml, hash, c, site, client, clients);
    scriptEl.textContent = script;
    shaEl.textContent = await scriptHash(script);
    saveDraft();
  }

  // Interviews re-render on every keystroke; coalesce bursts into one update.
  let running = false;
  let queuedFresh = null;
  function schedule(freshFiles) {
    queuedFresh = freshFiles || queuedFresh;
    if (running) return;
    running = true;
    (async () => {
      try {
        do {
          const fresh = queuedFresh === true;
          queuedFresh = null;
          await update(fresh);
        } while (queuedFresh !== null);
      } catch (err) {
        errorsBox.hidden = false;
        const item = document.createElement("li");
        item.textContent = String(err && err.message ? err.message : err);
        errorList.replaceChildren(item);
      } finally {
        running = false;
      }
    })();
  }

  // ----- events -----

  for (const radio of $$("input[name='author-kind']")) {
    radio.addEventListener("change", () => {
      if (!radio.checked) return;
      kind = radio.value;
      answers = {};
      overrides = {};
      renderFields();
      schedule(true);
    });
  }

  nameInput.addEventListener("input", () => {
    name = nameInput.value;
    schedule(true);
  });

  catalogSearch.addEventListener("input", renderCatalog);

  for (const input of clientInputs) {
    input.addEventListener("change", () => {
      if (!input.checked) return;
      client = input.value;
      writeShare();
      schedule(false);
    });
  }

  function writeShare() {
    shareUrl.value = `${location.origin}${location.pathname}${shareFragment(client, picked)}`;
  }

  downloadBtn.addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([script], { type: "text/x-sh" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = cfg.file_name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  copyBtn.addEventListener("click", (event) => {
    copyText(event.currentTarget, script, scriptEl);
  });

  shareBtn.addEventListener("click", (event) => {
    shareUrl.hidden = false;
    copyText(event.currentTarget, shareUrl.value, shareUrl);
  });

  $("#author-clear").addEventListener("click", () => {
    try {
      localStorage.removeItem(DRAFT_KEY);
    } catch {
      // Nothing stored: still reset the page.
    }
    kind = Object.keys(kinds)[0];
    name = "";
    answers = {};
    picked = new Set();
    overrides = {};
    nameInput.value = "";
    for (const radio of $$("input[name='author-kind']")) radio.checked = radio.value === kind;
    renderFields();
    renderCatalog();
    writeShare();
    $("#author-clear-done").hidden = false;
    announce(T.clear_done);
    schedule(true);
  });

  // ----- first paint -----

  const draft = loadDraft();
  if (draft) {
    if (draft.kind in kinds) kind = draft.kind;
    if (typeof draft.name === "string") name = draft.name;
    if (draft.answers && typeof draft.answers === "object") answers = draft.answers;
    if (Array.isArray(draft.picked))
      picked = new Set(draft.picked.filter((id) => policies.has(id)));
    if (draft.overrides && typeof draft.overrides === "object") overrides = draft.overrides;
    if (C.clients[draft.client]) client = draft.client;
  }
  const shared = parseShareFragment(location.hash);
  if (shared) {
    if (C.clients[shared.client]) client = shared.client;
    if (shared.ids) {
      const unknown = shared.ids.filter((id) => !policies.has(id));
      picked = new Set(shared.ids.filter((id) => policies.has(id)));
      if (unknown.length) notice(fill(T.unknown_catalog, { ids: unknown.join(", ") }));
    }
  }
  // The builder's own fragment is the schema-2 selection code: #s=<base64url>.
  const coded = /^#s=(.+)$/.exec(location.hash);
  if (coded) {
    let selection = null;
    try {
      selection = decodeSelection(coded[1]);
    } catch {
      selection = null;
    }
    const entries =
      selection && Array.isArray(selection.policies) ? selection.policies : null;
    if (!entries || !entries.every((entry) => entry && typeof entry.id === "string")) {
      notice(T.link_unreadable);
    } else {
      if (C.clients[selection.client]) client = selection.client;
      const catalogIds = entries
        .filter((entry) => entry.from !== "local")
        .map((entry) => entry.id);
      const unknown = catalogIds.filter((id) => !policies.has(id));
      picked = new Set(catalogIds.filter((id) => policies.has(id)));
      if (unknown.length) notice(fill(T.unknown_catalog, { ids: unknown.join(", ") }));
    }
  }
  nameInput.value = name;
  for (const radio of $$("input[name='author-kind']")) radio.checked = radio.value === kind;
  for (const input of clientInputs) input.checked = input.value === client;
  renderFields();
  renderCatalog();
  writeShare();
  schedule(true);
}

main();
