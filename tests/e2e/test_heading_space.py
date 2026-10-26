"""Section headings never sit flush under the block before them, on every page of the site."""

import re
from urllib.request import urlopen

import pytest

SIZES = {
    "desktop": {"width": 1280, "height": 900},
    "phone": {"width": 390, "height": 844},
}
# In the page: each heading's gap to the content above it, against the --flow paragraph gap.
GAPS_JS = """() => {
  const flow = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--flow"));
  const shown = (e) => {
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    return s.display !== "none" && s.visibility !== "hidden" && s.position !== "absolute"
      && s.position !== "fixed" && r.height > 0;
  };
  const boxed = (e) => {
    const s = getComputedStyle(e);
    return parseFloat(s.borderTopWidth) > 0 || s.backgroundColor !== "rgba(0, 0, 0, 0)";
  };
  const before = (e) => {
    let p = e.previousElementSibling;
    while (p && !shown(p)) p = p.previousElementSibling;
    return p;
  };
  const out = [];
  const heads = [...document.querySelectorAll("main h2")].map((h) => [h, 2 * flow])
    .concat([...document.querySelectorAll(".docs-section h3, .docs-prose h3")].map((h) => [h, flow + 1]));
  for (const [h, need] of heads) {
    if (!shown(h)) continue;
    // A kicker line (eyebrow, source path, step number and its progress bars) belongs to its heading.
    let start = h;
    for (let k = before(h); k && k.matches(".eyebrow, .docs-from, .quiz-step, .quiz-bars"); k = before(k)) start = k;
    let prev = null;
    for (let n = start; n && n.tagName !== "MAIN"; n = n.parentElement) {
      prev = before(n);
      if (prev) break;
    }
    if (!prev) continue;
    // The content the reader sees last: descend through unboxed wrappers.
    let last = prev;
    while (!boxed(last)) {
      const kids = [...last.children].filter(shown);
      if (!kids.length) break;
      last = kids[kids.length - 1];
    }
    const a = last.getBoundingClientRect(), b = h.getBoundingClientRect();
    if (a.right <= b.left || a.left >= b.right) continue;
    const gap = Math.round((start.getBoundingClientRect().top - a.bottom) * 10) / 10;
    if (gap < need) out.push(`${h.tagName} "${h.textContent.trim().slice(0, 50)}": ${gap}px, needs ${need}px`);
  }
  return out;
}"""


def _pages(site_url: str) -> list[str]:
    with urlopen(site_url + "/sitemap.xml") as response:
        xml = response.read().decode()
    return sorted(
        {
            re.sub(r"^https?://[^/]+", "", u)
            for u in re.findall(r"<loc>([^<]+)</loc>", xml)
        }
    )


@pytest.mark.parametrize("size", ["desktop", "phone"])
def test_headings_have_space_above(browser, site_url, size) -> None:
    pages = _pages(site_url)
    assert len(pages) > 200
    context = browser.new_context(viewport=SIZES[size])
    try:
        page = context.new_page()
        problems = []
        for path in pages:
            page.goto(site_url + path)
            problems += [f"{path} {p}" for p in page.evaluate(GAPS_JS)]
        assert not problems, "\n".join(problems)
    finally:
        context.close()
