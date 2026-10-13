// Docs search: a WAI-ARIA combobox over /api/docs/search.json, the site's own index.
// Nothing leaves the page: the index is fetched once from this origin and queries stay local.
// Without JS the box stays hidden and its link to the docs index shows instead.

const MAX_RESULTS = 8;
const MAX_TERMS = 8;
const ANNOUNCE_MS = 400;
const WEIGHT = { title: 8, heading: 4, url: 2, excerpt: 1 };

// Terms from a query: lowercased, split on spaces, at most MAX_TERMS.
function terms(query) {
  return query.toLowerCase().split(/\s+/).filter(Boolean).slice(0, MAX_TERMS);
}

// Points for one term in one text: its weight, doubled when a word starts with it.
function hit(text, term, weight) {
  const at = text.indexOf(term);
  if (at < 0) return 0;
  return at === 0 || /[^a-z0-9]/.test(text[at - 1]) ? weight * 2 : weight;
}

// Score a page against every term; a page must match each term somewhere.
function score(page, words) {
  let total = 0;
  const headingHits = page.headings.map(() => 0);
  for (const term of words) {
    let best = Math.max(
      hit(page.lower.title, term, WEIGHT.title),
      hit(page.lower.url, term, WEIGHT.url),
      hit(page.lower.excerpt, term, WEIGHT.excerpt),
    );
    page.lower.headings.forEach((text, i) => {
      const points = hit(text, term, WEIGHT.heading);
      if (points) headingHits[i] += 1;
      best = Math.max(best, points);
    });
    if (!best) return null;
    total += best;
  }
  const titleHasAll = words.every((term) => page.lower.title.includes(term));
  let heading = null;
  if (!titleHasAll) {
    const most = Math.max(0, ...headingHits);
    if (most) heading = page.headings[headingHits.indexOf(most)];
  }
  return { page, total, heading };
}

export function search(index, query) {
  const words = terms(query);
  if (!words.length) return [];
  return index
    .map((page) => score(page, words))
    .filter(Boolean)
    .sort((a, b) => b.total - a.total || a.page.title.localeCompare(b.page.title))
    .slice(0, MAX_RESULTS);
}

// The index rows with lowercased copies for matching, built once. Only site paths are kept.
function prepare(doc) {
  return doc.pages.filter((page) => /^\/(?![/\\])/.test(page.url)).map((page) => ({
    ...page,
    lower: {
      title: page.title.toLowerCase(),
      url: page.url.toLowerCase(),
      excerpt: page.excerpt.toLowerCase(),
      headings: page.headings.map((h) => h.text.toLowerCase()),
    },
  }));
}

function span(className, text) {
  const el = document.createElement("span");
  el.className = className;
  el.textContent = text;
  return el;
}

function init(root) {
  const url = new URL(root.dataset.index, location.href);
  if (url.origin !== location.origin) return;
  const box = root.querySelector(".docs-search-box");
  const fallback = root.querySelector(".docs-search-fallback");
  const input = root.querySelector("[role=combobox]");
  const list = root.querySelector("[role=listbox]");
  const status = root.querySelector("[role=status]");
  let index = null;
  let loading = null;
  let results = [];
  let active = -1;
  let timer = 0;

  const say = (text) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      status.textContent = text;
    }, ANNOUNCE_MS);
  };

  const load = () => {
    if (!loading) {
      loading = fetch(url.href, { credentials: "same-origin" })
        .then((response) => {
          if (!response.ok) throw new Error(String(response.status));
          return response.json();
        })
        .then((doc) => {
          index = prepare(doc);
        })
        .catch(() => {
          fallback.hidden = false;
          say(root.dataset.failed);
        });
    }
    return loading;
  };

  const setActive = (n) => {
    active = n;
    [...list.children].forEach((option, i) => {
      option.setAttribute("aria-selected", String(i === n));
    });
    if (n < 0) {
      input.removeAttribute("aria-activedescendant");
      return;
    }
    const option = list.children[n];
    input.setAttribute("aria-activedescendant", option.id);
    option.scrollIntoView({ block: "nearest" });
  };

  const close = () => {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    setActive(-1);
  };

  const open = () => {
    if (!results.length) return;
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };

  const go = (n) => {
    const found = results[n];
    if (!found) return;
    const hash = found.heading ? `#${found.heading.id}` : "";
    location.assign(found.page.url + hash);
  };

  const show = () => {
    const query = input.value.trim();
    results = index && query ? search(index, query) : [];
    list.replaceChildren(
      ...results.map((found, i) => {
        const option = document.createElement("li");
        option.id = `docs-search-option-${i}`;
        option.className = "docs-search-option";
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.appendChild(span("docs-search-title", found.page.title));
        if (found.heading) option.appendChild(span("docs-search-where", found.heading.text));
        option.appendChild(span("docs-search-excerpt", found.page.excerpt));
        option.addEventListener("mousedown", (event) => event.preventDefault());
        option.addEventListener("click", () => go(i));
        return option;
      }),
    );
    active = -1;
    input.removeAttribute("aria-activedescendant");
    if (!query || !index) {
      close();
      say("");
      return;
    }
    if (results.length) {
      open();
      const word = results.length === 1 ? root.dataset.one : root.dataset.many;
      say(word.replace("{count}", () => String(results.length)));
    } else {
      close();
      say(root.dataset.none.replace("{query}", () => query));
    }
  };

  input.addEventListener("focus", load);
  input.addEventListener("input", () => {
    if (index) show();
    else load().then(show);
  });
  input.addEventListener("keydown", (event) => {
    const last = results.length - 1;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!results.length) return;
      event.preventDefault();
      open();
      if (event.altKey) return;
      const down = event.key === "ArrowDown";
      if (active < 0) setActive(down ? 0 : last);
      else if (down) setActive(active === last ? 0 : active + 1);
      else setActive(active === 0 ? last : active - 1);
    } else if (event.key === "Enter") {
      if (list.hidden || !results.length) return;
      event.preventDefault();
      go(active < 0 ? 0 : active);
    } else if (event.key === "Escape") {
      event.preventDefault();
      if (!list.hidden) close();
      else {
        input.value = "";
        show();
      }
    }
  });
  root.addEventListener("focusout", (event) => {
    if (!root.contains(event.relatedTarget)) close();
  });

  box.hidden = false;
  fallback.hidden = true;
}

const root = document.querySelector(".docs-search[data-index]");
if (root) init(root);
