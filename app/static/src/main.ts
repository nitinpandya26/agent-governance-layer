/**
 * Small interaction layer on top of the server-rendered pages in
 * app/templates/. Deliberately not a framework: FastAPI + Jinja still own
 * routing and rendering, this just adds polish once the DOM is on screen.
 */

function highlightCurrentNavLink(): void {
  const path = window.location.pathname;
  document.querySelectorAll<HTMLAnchorElement>(".app-nav a").forEach((link) => {
    const href = link.getAttribute("href") ?? "";
    const isCurrent = href === "/" ? path === "/" : path.startsWith(href);
    link.classList.toggle("current", isCurrent);
  });
}

function enableToolResultToggle(): void {
  document.querySelectorAll<HTMLElement>(".tool-result").forEach((el) => {
    el.classList.add("collapsed");
    el.addEventListener("click", () => el.classList.toggle("collapsed"));
  });
}

function enableResolveFade(): void {
  document.querySelectorAll<HTMLFormElement>("form[data-resolve-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const row = form.closest<HTMLElement>(".queue-row");
      if (!row) return;
      event.preventDefault();
      row.classList.add("resolving");
      window.setTimeout(() => form.submit(), 220);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  highlightCurrentNavLink();
  enableToolResultToggle();
  enableResolveFade();
});
