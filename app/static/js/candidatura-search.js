// Incremental search for the "Vots per candidatura" comparison filter.
// Progressive enhancement only: every suggestion is already a plain <a>
// that adds the candidatura via a normal page reload (same pattern as
// every other filter in this app), and there's a <select> + submit button
// fallback inside <noscript>. This script only filters which suggestions
// are visible as the user types — it never builds URLs itself.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var input = document.getElementById("candidatura-search");
    var list = document.getElementById("candidatura-suggestions");
    if (!input || !list) {
      return;
    }

    var noMatch = document.getElementById("candidatura-no-match");
    var items = Array.prototype.slice.call(list.querySelectorAll(".candidatura-picker__suggestion[data-search]"));

    function stripAccents(text) {
      return text.normalize("NFD").replace(new RegExp("[\\u0300-\\u036f]", "g"), "");
    }

    function showList() { list.hidden = false; }
    function hideList() { list.hidden = true; }

    function filter() {
      var term = stripAccents(input.value.trim().toLowerCase());
      if (term === "") {
        hideList();
        return;
      }
      var anyVisible = false;
      items.forEach(function (li) {
        var matches = stripAccents(li.dataset.search).indexOf(term) !== -1;
        li.hidden = !matches;
        if (matches) {
          anyVisible = true;
        }
      });
      if (noMatch) {
        noMatch.hidden = anyVisible;
      }
      showList();
    }

    input.addEventListener("input", filter);
    input.addEventListener("focus", function () {
      if (input.value.trim() !== "") {
        filter();
      }
    });

    input.addEventListener("keydown", function (evt) {
      if (evt.key === "Escape") {
        input.value = "";
        hideList();
      }
    });

    document.addEventListener("click", function (evt) {
      if (evt.target !== input && !list.contains(evt.target)) {
        hideList();
      }
    });
  });
})();
