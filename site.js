const root = document.documentElement;
const themeButton = document.querySelector("[data-theme-toggle]");
const storageKey = "pref-theme";

const preferredTheme = () => {
  const saved = localStorage.getItem(storageKey);
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

const setTheme = (theme) => {
  root.setAttribute("data-theme", theme);
  root.classList.toggle("dark", theme === "dark");
  if (document.body.classList.contains("writing-page")) {
    // The pinned marimo runtime observes this attribute to update widget themes.
    document.body.dataset.vscodeThemeKind = `vscode-${theme}`;
  }
  if (themeButton) {
    themeButton.textContent = theme === "dark" ? "○" : "●";
    themeButton.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} theme`);
  }
};

setTheme(preferredTheme());

themeButton?.addEventListener("click", () => {
  const nextTheme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
  localStorage.setItem(storageKey, nextTheme);
  setTheme(nextTheme);
});

document.querySelectorAll("[data-year]").forEach((element) => {
  element.textContent = new Date().getFullYear();
});
