// Client-side search + column sorting for "Resultats per mesa electoral",
// same approach as cens-table.js: a convocatòria has at most a couple
// hundred mesa rows, small enough to filter/sort directly in the DOM
// without a page reload.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var table = document.getElementById("mesa-table");
    if (!table) {
      return;
    }

    var tbody = table.querySelector("tbody");
    var searchInput = document.getElementById("mesa-search");
    var rowCountEl = document.getElementById("mesa-row-count");
    var headers = table.querySelectorAll("thead th[data-sort-key]");

    var currentSort = { key: "districte", direction: "asc" };

    function stripAccents(text) {
      return text.normalize("NFD").replace(new RegExp("[\\u0300-\\u036f]", "g"), "");
    }

    function applyFilter() {
      var term = stripAccents((searchInput ? searchInput.value : "").trim().toLowerCase());
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      var visibleCount = 0;

      rows.forEach(function (row) {
        var haystack = stripAccents(row.textContent.toLowerCase());
        var matches = term === "" || haystack.indexOf(term) !== -1;
        row.hidden = !matches;
        if (matches) {
          visibleCount += 1;
        }
      });

      if (rowCountEl) {
        rowCountEl.textContent = visibleCount + " de " + rows.length + " meses";
      }
    }

    function compareRows(a, b, key, type) {
      var va = a.dataset[key] || "";
      var vb = b.dataset[key] || "";
      if (type === "number") {
        return (parseFloat(va) || 0) - (parseFloat(vb) || 0);
      }
      return va.localeCompare(vb, "ca");
    }

    function sortBy(key, type, direction) {
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      rows.sort(function (a, b) {
        var result = compareRows(a, b, key, type);
        return direction === "asc" ? result : -result;
      });
      rows.forEach(function (row) { tbody.appendChild(row); });
    }

    function updateHeaderIndicators() {
      headers.forEach(function (th) {
        var indicator = th.querySelector(".sort-indicator");
        if (th.dataset.sortKey === currentSort.key) {
          th.setAttribute("aria-sort", currentSort.direction === "asc" ? "ascending" : "descending");
          if (indicator) {
            indicator.textContent = currentSort.direction === "asc" ? "▲" : "▼";
          }
        } else {
          th.setAttribute("aria-sort", "none");
          if (indicator) {
            indicator.textContent = "";
          }
        }
      });
    }

    function handleSortActivation(th) {
      var key = th.dataset.sortKey;
      var type = th.dataset.sortType;
      if (currentSort.key === key) {
        currentSort.direction = currentSort.direction === "asc" ? "desc" : "asc";
      } else {
        currentSort = { key: key, direction: "asc" };
      }
      sortBy(key, type, currentSort.direction);
      updateHeaderIndicators();
      applyFilter();
    }

    headers.forEach(function (th) {
      th.addEventListener("click", function () { handleSortActivation(th); });
      th.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          handleSortActivation(th);
        }
      });
    });

    if (searchInput) {
      searchInput.addEventListener("input", applyFilter);
    }

    updateHeaderIndicators();
    applyFilter();
  });
})();
