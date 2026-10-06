// The builder's start screen: three questions, then a result with the real install command.
// The questions and their answers come from data/quiz.yaml (site.json "quiz"); the command is
// built by common.js, exactly as the full builder builds it.
import { announce, buildSelection, copyText, installCommand } from "./common.js";

const LABEL_ORDER = ["block", "ask", "warn", "advise"];

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
// Presets are read in the order the worries and their presets are listed in the data.
export function quizPicks(quiz, site, answers) {
  const byId = new Map(site.policies.map((p) => [p.id, p]));
  const presets = new Map(site.presets.map((p) => [p.id, p]));
  const worries = quiz.questions.find((q) => q.id === "worries");
  const strictness = quiz.questions.find((q) => q.id === "strictness");
  const allowed = new Set(strictness.options.find((o) => o.id === answers.strictness).allow);
  const picks = new Map();
  for (const worry of worries.options) {
    if (!answers.worries.includes(worry.id)) continue;
    for (const presetId of worry.presets) {
      for (const id of presets.get(presetId).members) {
        if (!allowed.has(byId.get(id).keyword)) continue;
        if (!picks.has(id)) picks.set(id, []);
        if (!picks.get(id).includes(worry.label)) picks.get(id).push(worry.label);
      }
    }
  }
  return [...picks].map(([id, why]) => ({ id, why }));
}

// The label mix of some policy ids as one line: "3 blocks · 1 asks · ...".
export function mixLine(quiz, site, ids) {
  const byId = new Map(site.policies.map((p) => [p.id, p]));
  const words = site.label_words.coding;
  const counts = Object.fromEntries(LABEL_ORDER.map((key) => [key, 0]));
  for (const id of ids) counts[byId.get(id).keyword] += 1;
  return LABEL_ORDER.map((key) => fill(quiz.texts.mix, { n: counts[key], word: words[key] })).join(
    quiz.texts.mix_separator,
  );
}

export function initQuiz({ site, chipFor, onSkip }) {
  const quiz = site.quiz;
  const T = quiz.texts;
  const total = quiz.questions.length;
  const bars = document.getElementById("quiz-bars");
  const stepEl = document.getElementById("quiz-step");
  const titleEl = document.getElementById("quiz-title");
  const body = document.getElementById("quiz-body");
  const back = document.getElementById("quiz-back");
  const next = document.getElementById("quiz-next");
  let step = 1;
  let answers = defaultAnswers(quiz);
  let removed = new Set();

  function currentPicks() {
    return quizPicks(quiz, site, answers).filter((pick) => !removed.has(pick.id));
  }

  function renderBars() {
    bars.replaceChildren(
      ...Array.from({ length: total + 1 }, (_, i) => element("span", i < step ? "quiz-bar on" : "quiz-bar")),
    );
  }

  // ----- a question -----

  function selectedOption(question) {
    return question.options.find((o) => o.id === answers[question.id]);
  }

  function refreshQuestion(question, note, hint) {
    note.replaceChildren();
    const option = question.kind === "single" ? selectedOption(question) : null;
    const ends = Boolean(option && option.other);
    if (ends) {
      note.appendChild(element("span", "", fill(T.clients_note, { agent: option.label })));
      note.appendChild(document.createTextNode(" "));
      const link = element("a", "", T.clients_link);
      link.href = "/coding/clients/";
      note.appendChild(link);
    }
    note.hidden = !ends;
    const missing = question.kind === "multi" && answers[question.id].length === 0;
    hint.textContent = missing ? T.need_worry : "";
    hint.hidden = !missing;
    next.hidden = ends;
    next.disabled = missing;
  }

  function renderQuestion(question) {
    body.replaceChildren();
    body.appendChild(element("p", "quiz-hint-text", question.hint));
    const group = element("div", "quiz-options");
    group.setAttribute("role", "group");
    group.setAttribute("aria-labelledby", "quiz-title");
    const multi = question.kind === "multi";
    for (const option of question.options) {
      const label = element("label", "quiz-opt");
      const input = document.createElement("input");
      input.type = multi ? "checkbox" : "radio";
      input.name = `quiz-${question.id}`;
      input.value = option.id;
      input.checked = multi ? answers[question.id].includes(option.id) : answers[question.id] === option.id;
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
    body.appendChild(element("p", "quiz-mix", mixLine(quiz, site, ids)));
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
      item.appendChild(element("code", "quiz-pick-id", pick.id));
      item.appendChild(element("span", "quiz-pick-why", fill(T.because, { why: pick.why.join(", ").toLowerCase() })));
      const remove = element("button", "remove", T.remove);
      remove.type = "button";
      remove.setAttribute("aria-label", fill(T.remove_label, { id: pick.id }));
      remove.addEventListener("click", () => removePick(pick.id));
      item.appendChild(remove);
      list.appendChild(item);
    }
    body.appendChild(list);

    const { code, command } = installCommand(site, buildSelection(site, ids));
    const box = element("div", "quiz-command");
    box.appendChild(element("h3", "quiz-command-title", T.command_label));
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
    body.appendChild(box);
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
    step = Math.max(1, step - 1);
    render(true);
  });
  next.addEventListener("click", () => {
    if (step > total) {
      step = 1;
      answers = defaultAnswers(quiz);
      removed = new Set();
    } else {
      step += 1;
      removed = new Set();
    }
    render(true);
  });
  document.getElementById("quiz-skip").addEventListener("click", onSkip);
  render(false);
}
