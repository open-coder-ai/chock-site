// The builder's start screen: three questions, then a result with the real install command.
// The questions and their answers come from data/quiz.yaml (site.json "quiz"); the command is
// built by common.js, exactly as the full builder builds it. The Git repositories builder reuses
// this module with section "repos": same flow, its own questions, tiers and outputs.
import { announce, buildSelection, copyText, installCommand } from "./common.js";

const LABEL_ORDER = ["block", "ask", "warn", "advise"];

// What differs between sections: the quiz data, the label words, their order and each policy's keyword.
export function sectionConfig(site, section = "coding") {
  if (section === "repos") {
    return {
      quiz: site.repos.quiz,
      words: site.label_words.repos,
      order: site.repos.tiers.map((tier) => tier.key),
      keywordOf: (id) => site.repos.tier_of[id],
    };
  }
  const byId = new Map(site.policies.map((p) => [p.id, p]));
  const clients = site.builder_clients;
  return {
    quiz: site.quiz,
    words: { ...site.label_words.coding, [clients.ungraded]: clients.texts.ungraded_word },
    order: LABEL_ORDER,
    ungraded: clients.ungraded,
    keywordOf: (id) => byId.get(id).keyword,
  };
}

const fill = (text, values) =>
  text.replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match));

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// The default answer of every question: the option marked `default`, or nothing for a multi question.
export function defaultAnswers(quiz) {
  const answers = {};
  for (const question of quiz.questions) {
    if (question.kind === "multi") answers[question.id] = [];
    else answers[question.id] = question.options.find((o) => o.default).id;
  }
  return answers;
}

// The picks for a set of answers: each policy once, with every worry that reached it.
// Presets are read in the order the worries and their presets are listed in the data. A policy the
// catalog does not grade on the chosen agent has no strictness to filter on, so it stays in.
export function quizPicks(quiz, site, answers, keywordOf, ungraded = null) {
  const presets = new Map(site.presets.map((p) => [p.id, p]));
  const worries = quiz.questions.find((q) => q.id === "worries");
  const strictness = quiz.questions.find((q) => q.id === "strictness");
  const allowed = new Set(strictness.options.find((o) => o.id === answers.strictness).allow);
  const picks = new Map();
  for (const worry of worries.options) {
    if (!answers.worries.includes(worry.id)) continue;
    for (const presetId of worry.presets) {
      for (const id of presets.get(presetId).members) {
        const keyword = keywordOf(id);
        if (keyword !== ungraded && !allowed.has(keyword)) continue;
        if (!picks.has(id)) picks.set(id, []);
        if (!picks.get(id).includes(worry.label)) picks.get(id).push(worry.label);
      }
    }
  }
  return [...picks].map(([id, why]) => ({ id, why }));
}

// The label mix of some policy ids as one line: "3 blocks · 1 asks · ...", plus "2 not graded" if any.
export function mixLine(quiz, ids, { words, order, keywordOf, ungraded }) {
  const keys = ungraded ? [...order, ungraded] : order;
  const counts = Object.fromEntries(keys.map((key) => [key, 0]));
  for (const id of ids) counts[keywordOf(id)] += 1;
  return keys
    .filter((key) => key !== ungraded || counts[key])
    .map((key) => fill(quiz.texts.mix, { n: counts[key], word: words[key] }))
    .join(quiz.texts.mix_separator);
}

// The coding result's output: the install command for the client, Copy, and the way into the full builder.
export function commandOutputs(site, T, ids, client = site.builder_clients.default) {
  const { code, command } = installCommand(site, buildSelection(site, ids, client));
  const box = element("div", "quiz-command");
  box.appendChild(element("h3", "quiz-command-title", T.command_label));
  const about = site.builder_clients.clients[client];
  if (about.witness === "untested") {
    const line = element("p", "client-untested");
    line.appendChild(element("strong", "", about.untested_label));
    line.appendChild(document.createTextNode(` ${about.untested_line} `));
    const link = element("a", "", site.builder_clients.texts.report);
    link.href = about.report;
    line.append(link, ".");
    box.appendChild(line);
  }
  const pre = element("pre");
  const codeEl = element("code", "language-bash", command);
  codeEl.dataset.quizCommand = "";
  pre.appendChild(codeEl);
  box.appendChild(pre);
  const actions = element("div", "quiz-actions");
  const copy = element("button", "button button-primary", T.copy);
  copy.type = "button";
  copy.addEventListener("click", () => copyText(copy, command, codeEl));
  const open = element("a", "button button-secondary", T.open_full);
  open.id = "quiz-open";
  open.href = `#s=${code}`;
  actions.append(copy, open);
  box.appendChild(actions);
  return box;
}

// `outputs(ids, context)` returns the node shown under the picks; `picks` (an array of ids) skips the
// questions and opens the result with exactly those policies (a share link); `keywordOf` replaces the
// section's label lookup (the coding builder passes the picked client's labels); `agent` ({get, set})
// ties the "agent" question to the builder's agent picker, so both always show one choice.
export function initQuiz({
  site,
  section = "coding",
  chipFor,
  onSkip,
  outputs,
  picks: sharedPicks,
  keywordOf,
  agent,
}) {
  const config = sectionConfig(site, section);
  if (keywordOf) config.keywordOf = keywordOf;
  const quiz = config.quiz;
  const T = quiz.texts;
  const makeOutputs = outputs || ((ids) => commandOutputs(site, T, ids));
  const names = new Map(site.policies.map((p) => [p.id, p.name]));
  const total = quiz.questions.length;
  const bars = document.getElementById("quiz-bars");
  const stepEl = document.getElementById("quiz-step");
  const titleEl = document.getElementById("quiz-title");
  const body = document.getElementById("quiz-body");
  const back = document.getElementById("quiz-back");
  const next = document.getElementById("quiz-next");
  let step = sharedPicks ? total + 1 : 1;
  let answers = defaultAnswers(quiz);
  let removed = new Set();
  let shared = sharedPicks || null;

  function currentPicks() {
    const all = shared
      ? shared.map((id) => ({ id, why: [] }))
      : quizPicks(quiz, site, answers, config.keywordOf, config.ungraded);
    return all.filter((pick) => !removed.has(pick.id));
  }

  function renderBars() {
    bars.replaceChildren(
      ...Array.from({ length: total + 1 }, (_, i) => element("span", i < step ? "quiz-bar on" : "quiz-bar")),
    );
  }

  // ----- a question -----

  const linked = (question) => Boolean(agent) && question.id === "agent";
  const answerOf = (question) => (linked(question) ? agent.get() : answers[question.id]);

  function selectedOption(question) {
    return question.options.find((o) => o.id === answerOf(question));
  }

  function refreshQuestion(question, note, hint) {
    note.replaceChildren();
    const option = question.kind === "single" ? selectedOption(question) : null;
    if (option && option.note) note.appendChild(element("span", "", option.note));
    note.hidden = !(option && option.note);
    const missing = question.kind === "multi" && answers[question.id].length === 0;
    hint.textContent = missing ? T.need_worry : "";
    hint.hidden = !missing;
    next.disabled = missing;
  }

  function renderQuestion(question) {
    body.replaceChildren();
    body.appendChild(element("p", "quiz-hint-text", question.hint));
    const group = element("div", "quiz-options card-grid");
    group.setAttribute("role", "group");
    group.setAttribute("aria-labelledby", "quiz-title");
    const multi = question.kind === "multi";
    for (const option of question.options) {
      const label = element("label", "quiz-opt");
      const input = document.createElement("input");
      input.type = multi ? "checkbox" : "radio";
      input.name = `quiz-${question.id}`;
      input.value = option.id;
      input.checked = multi ? answers[question.id].includes(option.id) : answerOf(question) === option.id;
      const box = element("span", "quiz-opt-box");
      box.appendChild(element("span", "quiz-opt-label", option.label));
      box.appendChild(element("span", "quiz-opt-sub", option.sub));
      label.append(input, box);
      group.appendChild(label);
    }
    body.appendChild(group);
    const note = element("p", "quiz-note");
    note.setAttribute("role", "status");
    const hint = element("p", "quiz-need");
    hint.setAttribute("role", "status");
    body.append(note, hint);
    group.addEventListener("change", (event) => {
      const input = event.target;
      if (!(input instanceof HTMLInputElement)) return;
      if (multi) {
        const ids = new Set(answers[question.id]);
        if (input.checked) ids.add(input.value);
        else ids.delete(input.value);
        answers[question.id] = question.options.map((o) => o.id).filter((id) => ids.has(id));
      } else {
        answers[question.id] = input.value;
        if (linked(question)) agent.set(input.value);
      }
      removed = new Set();
      refreshQuestion(question, note, hint);
    });
    refreshQuestion(question, note, hint);
  }

  // ----- the result -----

  function renderResult() {
    const picks = currentPicks();
    const ids = picks.map((pick) => pick.id);
    titleEl.textContent = picks.length === 1 ? T.result_one : fill(T.result_many, { n: picks.length });
    body.replaceChildren();
    body.appendChild(element("p", "quiz-mix", mixLine(quiz, ids, config)));
    body.appendChild(element("p", "quiz-hint-text", T.result_hint));
    if (!picks.length) {
      body.appendChild(element("p", "quiz-empty", T.empty));
      return;
    }
    const list = element("ul", "quiz-picks");
    for (const pick of picks) {
      const item = element("li", "quiz-pick");
      item.dataset.policyId = pick.id;
      const chip = chipFor(pick.id);
      if (chip) item.appendChild(chip.cloneNode(true));
      const name = element("span", "quiz-pick-name", names.get(pick.id) || pick.id);
      name.append(" ", element("code", "quiz-pick-id", pick.id));
      item.appendChild(name);
      if (pick.why.length) {
        item.appendChild(element("span", "quiz-pick-why", fill(T.because, { why: pick.why.join(", ").toLowerCase() })));
      }
      const remove = element("button", "remove", T.remove);
      remove.type = "button";
      remove.setAttribute("aria-label", fill(T.remove_label, { id: pick.id }));
      remove.addEventListener("click", () => removePick(pick.id));
      item.appendChild(remove);
      list.appendChild(item);
    }
    body.appendChild(list);

    body.appendChild(makeOutputs(ids, { answers, T, rerender: renderResult }));
  }

  function removePick(id) {
    const buttons = Array.from(body.querySelectorAll(".quiz-pick .remove"));
    const index = buttons.findIndex((button) => button.closest(".quiz-pick").dataset.policyId === id);
    removed.add(id);
    renderResult();
    announce(fill(T.removed, { id }));
    const left = Array.from(body.querySelectorAll(".quiz-pick .remove"));
    (left[Math.min(index, left.length - 1)] || titleEl).focus();
  }

  // ----- steps -----

  function render(moveFocus) {
    renderBars();
    const isResult = step > total;
    stepEl.textContent = isResult ? T.result_step : fill(T.step, { n: step, total });
    back.hidden = step === 1;
    back.textContent = T.back;
    next.hidden = false;
    next.disabled = false;
    if (isResult) {
      renderResult();
      next.textContent = T.start_over;
    } else {
      const question = quiz.questions[step - 1];
      titleEl.textContent = question.title;
      renderQuestion(question);
      next.textContent = step === total ? T.show : T.next;
    }
    if (moveFocus) titleEl.focus();
  }

  back.addEventListener("click", () => {
    shared = null;
    step = Math.max(1, step - 1);
    render(true);
  });
  next.addEventListener("click", () => {
    if (step > total) {
      step = 1;
      answers = defaultAnswers(quiz);
      removed = new Set();
      shared = null;
    } else {
      step += 1;
      removed = new Set();
    }
    render(true);
  });
  const skip = document.getElementById("quiz-skip");
  if (skip && onSkip) skip.addEventListener("click", onSkip);
  render(false);
  return {
    // Re-draw the current step after something it shows changed (the coding builder's agent).
    refresh() {
      render(false);
    },
    openShared(ids) {
      shared = ids;
      step = total + 1;
      removed = new Set();
      render(true);
    },
  };
}
