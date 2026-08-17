// Client-side search + column sorting for the "Cens electoral per mesa"
// table. No page reload, no external library needed: a convocatòria has
// at most a couple hundred mesa rows, small enough to filter/sort
// directly in the DOM. Districte subtotal rows were intentionally left
// out to keep this sort/filter logic simple — sorting by Districte
// already clusters same-district rows together visually.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var table = document.getElementById("cens-table");
    if (!table) {
      return;
    }

    var tbody = table.querySelector("tbody");
    var searchInput = document.getElementById("cens-search");
    var totalVisibleEl = document.getElementById("cens-total-visible");
    var rowCountEl = document.getElementById("cens-row-count");
    var headers = table.querySelectorAll("thead th[data-sort-key]");

    var currentSort = { key: "districte", direction: "asc" };

    function stripAccents(text) {
      return text.normalize("NFD").replace(new RegExp("[\\u0300-\\u036f]", "g"), "");
    }

    function applyFilter() {
      var term = stripAccents((searchInput ? searchInput.value : "").trim().toLowerCase());
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      var visibleIndex = 0;
      var totalCens = 0;

      rows.forEach(function (row) {
        var haystack = stripAccents(row.textContent.toLowerCase());
        var matches = term === "" || haystack.indexOf(term) !== -1;
        row.hidden = !matches;
        if (matches) {
          row.classList.toggle("row-alt", visibleIndex % 2 === 1);
          visibleIndex += 1;
          totalCens += parseInt(row.dataset.cens, 10) || 0;
        }
      });

      if (totalVisibleEl) {
        totalVisibleEl.textContent = totalCens.toLocaleString("ca-ES");
      }
      if (rowCountEl) {
        rowCountEl.textContent = visibleIndex + " de " + rows.length + " meses";
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
