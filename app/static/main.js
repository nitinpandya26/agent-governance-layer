"use strict";
(() => {
  // app/static/src/main.ts
  function highlightCurrentNavLink() {
    const path = window.location.pathname;
    document.querySelectorAll(".app-nav a").forEach((link) => {
      var _a;
      const href = (_a = link.getAttribute("href")) != null ? _a : "";
      const isCurrent = href === "/" ? path === "/" : path.startsWith(href);
      link.classList.toggle("current", isCurrent);
    });
  }
  function enableToolResultToggle() {
    document.querySelectorAll(".tool-result").forEach((el) => {
      el.classList.add("collapsed");
      el.addEventListener("click", () => el.classList.toggle("collapsed"));
    });
  }
  function enableResolveFade() {
    document.querySelectorAll("form[data-resolve-form]").forEach((form) => {
      form.addEventListener("submit", (event) => {
        const row = form.closest(".queue-row");
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
})();
