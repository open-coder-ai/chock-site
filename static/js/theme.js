// Theme: put the stored or system theme on <html> before the page paints, then wire the
// header toggle. A classic script in <head>, so it runs before the stylesheet applies.
(() => {
  const KEY = "chock-theme";
  const root = document.documentElement;
  const media = window.matchMedia("(prefers-color-scheme: dark)");

  const stored = () => {
    try {
      const value = localStorage.getItem(KEY);
      return value === "light" || value === "dark" ? value : null;
    } catch {
      return null;
    }
  };

  const apply = (theme) => {
    root.dataset.theme = theme;
    const button = document.querySelector(".theme-toggle");
    if (button) button.setAttribute("aria-pressed", String(theme === "dark"));
  };

  apply(stored() || (media.matches ? "dark" : "light"));
  // Until the visitor picks one, the theme follows the system setting live.
  media.addEventListener("change", (event) => {
    if (!stored()) apply(event.matches ? "dark" : "light");
  });

  document.addEventListener("DOMContentLoaded", () => {
    const button = document.querySelector(".theme-toggle");
    if (!button) return;
    apply(root.dataset.theme);
    button.addEventListener("click", () => {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      apply(next);
      try {
        localStorage.setItem(KEY, next);
      } catch {
        // Blocked storage: the choice lasts until the page is left.
      }
    });
  });
})();
