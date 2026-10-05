// Filters on /policies/: search, label chips, where chips, group select.
// The full list renders without JS; this file only narrows it.

const rows = Array.from(document.querySelectorAll(".row[data-policy-id]"));
const search = document.getElementById("policy-search");
const group = document.getElementById("policy-group");
const status = document.getElementById("policies-status");
const chips = Array.from(document.querySelectorAll(".chip[data-facet]"));

const active = { label: new Set(), where: new Set() };

function matches(row, facets) {
  const labels = facets.label;
  const wheres = facets.where;
  if (labels.size && !labels.has(row.dataset.label)) return false;
  const tags = (row.dataset.where || "").split(" ").filter(Boolean);
  for (const tag of wheres) {
    if (!tags.includes(tag)) return false;
  }
  if (facets.group === "none") {
    if (row.dataset.groups) return false;
  } else if (facets.group) {
    const groups = (row.dataset.groups || "").split(" ");
    if (!groups.includes(facets.group)) return false;
  }
  if (facets.q) {
    const haystack = (row.dataset.search || "") + " " + row.textContent.toLowerCase();
    if (!haystack.includes(facets.q)) return false;
  }
  return true;
}

function facets(except) {
  return {
    q: except === "q" ? "" : search.value.trim().toLowerCase(),
    group: except === "group" ? "" : group.value,
    label: except === "label" ? new Set() : active.label,
    where: except === "where" ? new Set() : active.where,
  };
}

function countFor(facet, value) {
  const f = facets(facet);
  return rows.filter((row) => {
    if (!matches(row, f)) return false;
    if (facet === "label") return row.dataset.label === value;
    const tags = (row.dataset.where || "").split(" ");
    return tags.includes(value);
  }).length;
}

function describe() {
  const parts = [];
  for (const chip of chips) {
    if (chip.getAttribute("aria-pressed") === "true") {
      parts.push(chip.dataset.value);
    }
  }
  if (group.value === "none") parts.push("in no group");
  else if (group.value) {
    const label = group.options[group.selectedIndex].textContent;
    parts.push(`group: ${label.split(" · ")[0]}`);
  }
  if (search.value.trim()) parts.push(`search: “${search.value.trim()}”`);
  return parts.join(", ");
}

function apply() {
  const f = facets("");
  let shown = 0;
  rows.forEach((row) => {
    const visible = matches(row, f);
    row.classList.toggle("hidden", !visible);
    if (visible) shown += 1;
  });
  chips.forEach((chip) => {
    const span = chip.querySelector(".chip-count");
    if (span) span.textContent = String(countFor(chip.dataset.facet, chip.dataset.value));
  });
  let text = `Showing ${shown} of ${rows.length}`;
  const desc = describe();
  if (desc) text += ` · filter: ${desc}`;
  status.textContent = text;
}

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const set = active[chip.dataset.facet];
    const value = chip.dataset.value;
    if (set.has(value)) {
      set.delete(value);
      chip.setAttribute("aria-pressed", "false");
    } else {
      set.add(value);
      chip.setAttribute("aria-pressed", "true");
    }
    apply();
  });
});

search.addEventListener("input", apply);
group.addEventListener("change", apply);
