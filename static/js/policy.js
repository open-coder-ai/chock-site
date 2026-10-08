// Policy page: count a click on "Build for <agent>" with the policy id and the agent (plan AN-1).
import { track } from "./common.js";

const article = document.querySelector("article[data-policy-id]");
const list = document.querySelector(".agent-labels");
if (article && list) {
  for (const link of list.querySelectorAll("a[data-client]")) {
    link.addEventListener("click", () =>
      track("policy-build-clicked", { policy: article.dataset.policyId, agent: link.dataset.client }),
    );
  }
}
