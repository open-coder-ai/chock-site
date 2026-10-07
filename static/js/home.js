// Home page: the terminal demo and the use-case panels become tabs.
// Without this file both render as plain lists, so nothing here is required.

// A WAI-ARIA tablist placed before `host`, over `items` ({id, label, panel}).
function makeTabs(host, items, label, className) {
  const list = document.createElement("div");
  list.className = className;
  list.setAttribute("role", "tablist");
  list.setAttribute("aria-label", label);
  const buttons = items.map((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tab-button";
    button.setAttribute("role", "tab");
    button.id = `tab-${item.id}`;
    button.setAttribute("aria-controls", item.panel.id);
    button.textContent = item.label;
    item.panel.setAttribute("role", "tabpanel");
    item.panel.setAttribute("aria-labelledby", button.id);
    list.appendChild(button);
    return button;
  });

  function select(index, focus) {
    items.forEach((item, i) => {
      const on = i === index;
      buttons[i].setAttribute("aria-selected", String(on));
      buttons[i].tabIndex = on ? 0 : -1;
      item.panel.hidden = !on;
    });
    if (focus) buttons[index].focus();
  }

  buttons.forEach((button, i) => {
    button.addEventListener("click", () => select(i, false));
    button.addEventListener("keydown", (event) => {
      const last = buttons.length - 1;
      const keys = {
        ArrowRight: i === last ? 0 : i + 1,
        ArrowLeft: i === 0 ? last : i - 1,
        Home: 0,
        End: last,
      };
      if (event.key in keys) {
        event.preventDefault();
        select(keys[event.key], true);
      }
    });
  });
  host.before(list);
  select(0, false);
  return { select };
}

function initDemo() {
  const demo = document.querySelector("[data-demo]");
  if (!demo) return;
  const cases = Array.from(demo.querySelectorAll(".demo-case"));
  if (cases.length < 2) return;
  const items = cases.map((panel) => ({
    id: panel.dataset.tab,
    label: panel.dataset.tab,
    panel,
  }));
  demo.classList.add("demo-tabbed");
  makeTabs(demo.querySelector(".demo-list"), items, "Policies", "demo-tabs");
}

function initUsecases() {
  const host = document.querySelector("[data-usecases]");
  if (!host) return;
  const panels = Array.from(host.querySelectorAll("[data-usecase]"));
  const staticTabs = host.querySelector(".usecase-tabs");
  if (!panels.length || !staticTabs) return;
  const items = panels.map((panel) => {
    const link = staticTabs.querySelector(`[data-usecase-tab="${panel.dataset.usecase}"]`);
    return {
      id: panel.dataset.usecase,
      label: link ? link.textContent : panel.dataset.usecase,
      panel,
    };
  });
  const label = staticTabs.getAttribute("aria-label") || "Use cases";
  staticTabs.hidden = true;
  host.classList.add("usecases-tabbed");
  const tabs = makeTabs(host.querySelector(".usecase-panels"), items, label, "usecase-tablist");
  const wanted = items.findIndex((item) => `#usecase-${item.id}` === window.location.hash);
  if (wanted > 0) tabs.select(wanted, false);
}

initDemo();
initUsecases();
