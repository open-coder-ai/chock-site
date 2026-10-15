// Architecture diagrams: select a box to show its card under the picture, highlight the
// main path, or switch the figure to its light theme. Without JS each box links to its
// card in the list below the diagram, and the toolbar and panel stay hidden.
import { announce } from "./common.js";

function initFigure(figure) {
  const panel = figure.querySelector(".arch-panel");
  const list = panel.querySelector(".arch-panel-body");
  const nodes = [...figure.querySelectorAll(".arch-node")];
  let selected = null;

  function select(node) {
    const card = document.getElementById(node.getAttribute("href").slice(1));
    if (!card) return;
    const copy = card.cloneNode(true);
    copy.removeAttribute("id");
    list.replaceChildren(copy);
    nodes.forEach((n) => n.classList.toggle("is-selected", n === node));
    selected = node;
    panel.hidden = false;
    const label = copy.querySelector(".arch-card-label");
    announce(label ? label.textContent : "");
  }

  function close() {
    panel.hidden = true;
    list.replaceChildren();
    nodes.forEach((n) => n.classList.remove("is-selected"));
    if (selected) selected.focus();
    selected = null;
  }

  nodes.forEach((node) => {
    node.addEventListener("click", (event) => {
      event.preventDefault();
      select(node);
    });
  });
  panel.querySelector(".arch-close").addEventListener("click", close);
  figure.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) close();
  });

  const pathButton = figure.querySelector(".arch-path-toggle");
  pathButton.addEventListener("click", () => {
    const on = pathButton.getAttribute("aria-pressed") !== "true";
    pathButton.setAttribute("aria-pressed", String(on));
    figure.classList.toggle("show-path", on);
  });

  const themeButton = figure.querySelector(".arch-theme-toggle");
  themeButton.addEventListener("click", () => {
    const on = themeButton.getAttribute("aria-pressed") !== "true";
    themeButton.setAttribute("aria-pressed", String(on));
    if (on) figure.dataset.theme = "light";
    else delete figure.dataset.theme;
  });

  figure.querySelector(".arch-toolbar").hidden = false;
  figure.querySelector(".arch-hint-nojs").hidden = true;
  figure.querySelector(".arch-hint-js").hidden = false;
}

document.querySelectorAll(".arch-figure").forEach(initFigure);
