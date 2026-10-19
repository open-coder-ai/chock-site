// Report page: add the context in this page's query to each issue-form link (plan IS-1b).
// Only known keys with id-shaped values pass, so a crafted link cannot plant text in an issue.
import { track } from "./common.js";

const ID = /^[a-z0-9.-]{1,64}$/;
const PAGE = /^\/(?:[a-z0-9][a-z0-9.-]{0,63}\/){0,4}$/;
const KEYS = ["policy", "version", "agent", "page"];
const TITLE_KEY = /\{([a-z_]+)\}/g;

export function readContext(search, agents, siteUrl, formAgents) {
  const query = new URLSearchParams(search);
  const context = {};
  for (const key of KEYS) {
    const value = query.get(key);
    if (value === null) continue;
    if (key === "page") {
      if (PAGE.test(value)) context.page = siteUrl + value;
    } else if (ID.test(value) && (key !== "agent" || agents.includes(value))) {
      // An agent the issue forms do not offer goes in as "other": the dropdown is never left blank.
      context[key] = key === "agent" && !formAgents.includes(value) ? "other" : value;
    }
  }
  return context;
}

// The link's form URL with each field it declares (data-fields="field=key …") filled from context.
export function fillLink(href, fields, title, context) {
  const url = new URL(href);
  for (const pair of fields.split(" ").filter(Boolean)) {
    const [field, key] = pair.split("=");
    if (Object.hasOwn(context, key)) url.searchParams.set(field, context[key]);
  }
  const keys = [...title.matchAll(TITLE_KEY)].map((m) => m[1]);
  if (title && keys.every((key) => Object.hasOwn(context, key))) {
    url.searchParams.set("title", title.replace(TITLE_KEY, (_, key) => context[key]));
  }
  return url.toString();
}

const cards = document.getElementById("report-cards");
if (cards) {
  const agents = cards.dataset.agents.split(" ");
  const formAgents = cards.dataset.formAgents.split(" ");
  const context = readContext(location.search, agents, cards.dataset.siteUrl, formAgents);
  for (const link of cards.querySelectorAll("a[data-report-kind]")) {
    link.href = fillLink(link.href, link.dataset.fields, link.dataset.title, context);
    link.addEventListener("click", () =>
      track("report-form-opened", { form: link.dataset.reportKind }),
    );
  }
}
