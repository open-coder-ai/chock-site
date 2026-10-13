// Docs pages: tabs, copy buttons on code blocks, and the "On this page" list.
// Each is an enhancement: without JS the panels stay stacked and the list stays open.
import { announce, copyText } from "./common.js";

const NARROW = "(max-width: 1180px)";

// WAI-ARIA tabs: one tab stop, arrow keys, Home and End move and select.
function initTabs(box, index) {
  const panels = [...box.querySelectorAll(":scope > .docs-tab-panel")];
  if (panels.length < 2) return;
  const list = document.createElement("div");
  list.className = "docs-tab-list";
  list.setAttribute("role", "tablist");
  list.setAttribute("aria-label", box.dataset.label || "");
  const tabs = panels.map((panel, i) => {
    const heading = panel.querySelector(":scope > .docs-tab-heading");
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "docs-tab";
    tab.id = `docs-tab-${index}-${i}`;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", panel.id);
    tab.textContent = heading ? heading.textContent : String(i + 1);
    if (heading) heading.hidden = true;
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", tab.id);
    panel.tabIndex = 0;
    list.appendChild(tab);
    return tab;
  });
  const select = (n, focus) => {
    tabs.forEach((tab, i) => {
      const on = i === n;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      panels[i].hidden = !on;
    });
    if (focus) tabs[n].focus();
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => select(i, false));
    tab.addEventListener("keydown", (event) => {
      const last = tabs.length - 1;
      const moves = { ArrowRight: i === last ? 0 : i + 1, ArrowLeft: i === 0 ? last : i - 1 };
      const to = { ...moves, Home: 0, End: last }[event.key];
      if (to === undefined) return;
      event.preventDefault();
      select(to, true);
    });
  });
  box.insertBefore(list, panels[0]);
  box.classList.add("docs-tabs-on");
  const target = location.hash ? document.getElementById(location.hash.slice(1)) : null;
  const start = panels.findIndex((panel) => target && panel.contains(target));
  select(Math.max(start, 0), false);
}

// A Copy button on each code block; nothing is recorded about what is copied.
function initCopy(main) {
  const label = main.dataset.copyLabel;
  if (!label) return;
  main.querySelectorAll("pre").forEach((pre) => {
    const wrap = document.createElement("div");
    wrap.className = "code-block";
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy code-copy";
    button.textContent = label;
    button.addEventListener("click", () => copyText(button, pre.textContent, pre));
    wrap.appendChild(button);
  });
}

// "Copy page as Markdown": copies this page's own Markdown twin, fetched from this site only.
// Without JS the link to the twin stays, so the Markdown is one click away either way.
function initCopyPage(link) {
  const url = new URL(link.getAttribute("href"), window.location.href);
  if (url.origin !== window.location.origin) return;
  const twin = () =>
    fetch(url, { credentials: "omit" }).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.text();
    });
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy docs-copy-page";
  button.textContent = link.dataset.copyPage;
  button.addEventListener("click", async () => {
    try {
      if (window.ClipboardItem && navigator.clipboard.write) {
        // A pending item keeps the click's permission while the twin loads (Safari).
        const blob = twin().then((text) => new Blob([text], { type: "text/plain" }));
        await navigator.clipboard.write([new window.ClipboardItem({ "text/plain": blob })]);
      } else {
        await navigator.clipboard.writeText(await twin());
      }
    } catch {
      announce(link.dataset.failed);
      return;
    }
    button.textContent = link.dataset.copied;
    announce(link.dataset.copied);
    window.setTimeout(() => {
      button.textContent = link.dataset.copyPage;
    }, 1600);
  });
  link.parentNode.insertBefore(button, link);
}

// The list starts closed on narrow screens and marks the section being read.
function initToc(toc) {
  const box = toc.querySelector("details");
  if (box && window.matchMedia(NARROW).matches) box.open = false;
  const links = [...toc.querySelectorAll("a[href^='#']")];
  const targets = links.map((a) => document.getElementById(a.getAttribute("href").slice(1)));
  if (targets.includes(null)) return;
  let queued = false;
  const mark = () => {
    queued = false;
    const style = getComputedStyle(document.documentElement);
    const top = (parseFloat(style.getPropertyValue("--sticky-top")) || 0) + 24;
    let current = 0;
    targets.forEach((t, i) => {
      if (t.getBoundingClientRect().top <= top) current = i;
    });
    const root = document.documentElement;
    if (window.scrollY > 0 && window.innerHeight + window.scrollY >= root.scrollHeight - 2) {
      current = targets.length - 1;
    }
    links.forEach((a, i) => {
      if (i === current) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
  };
  window.addEventListener(
    "scroll",
    () => {
      if (!queued) {
        queued = true;
        window.requestAnimationFrame(mark);
      }
    },
    { passive: true },
  );
  mark();
}

const main = document.querySelector(".docs-main");
if (main) {
  document.querySelectorAll(".docs-tabs").forEach(initTabs);
  initCopy(main);
  const pageLink = main.querySelector(".docs-md a[data-copy-page]");
  if (pageLink) initCopyPage(pageLink);
}
const toc = document.querySelector(".docs-toc");
if (toc) initToc(toc);
