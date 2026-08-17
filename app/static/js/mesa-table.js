// Client-side column sorting for "Resultats per mesa electoral", same
// approach as cens-table.js: a convocatòria has at most a couple hundred
// mesa rows, small enough to sort directly in the DOM without a page
// reload.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var table = document.getElementById("mesa-table");
    if (!table) {
      return;
    }

    var tbody = table.querySelector("tbody");
    var headers = table.querySelectorAll("thead th[data-sort-key]");

    var currentSort = { key: "districte", direction: "asc" };

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

    updateHeaderIndicators();

    // Districte/Secció/Mesa congelades (position: sticky) necessiten un
    // `left` per columna que coincideixi amb l'amplada REAL renderitzada
    // de les columnes anteriors — i com que la taula és `table-layout:
    // auto`, aquesta amplada depèn del contingut i no es pot fixar per
    // endavant en CSS. Si `left` no encaixa exactament, la columna
    // congelada deixa un escletxa pel mig i s'hi veu contingut d'altres
    // columnes en fer scroll. Es mesura amb `getBoundingClientRect()`
    // sobre la capçalera (totes les cel·les d'una columna comparteixen
    // amplada en table-layout: auto) i s'aplica com a `left` inline a
    // capçalera i cos.
    function updateStickyOffsets() {
      var stickyCells = table.querySelectorAll(".mesa-table__sticky-col");
      var headerWidths = [];
      stickyCells.forEach(function (cell) {
        var index = parseInt(cell.dataset.stickyIndex, 10);
        if (cell.tagName === "TH") {
          headerWidths[index] = cell.getBoundingClientRect().width;
        }
      });
      var lefts = [];
      var acc = 0;
      headerWidths.forEach(function (width, index) {
        lefts[index] = acc;
        acc += width;
      });
      stickyCells.forEach(function (cell) {
        var index = parseInt(cell.dataset.stickyIndex, 10);
        cell.style.left = lefts[index] + "px";
      });
    }

    // Barra de desplaçament "mirall" a sobre de la taula (vegeu style.css
    // ::.mesa-table-scroll-top): amb tantes columnes de partit cal fer
    // scroll horitzontal i la barra nativa, sota la taula, pot quedar fora
    // de vista. `topScroll` no té contingut real: només se li dona la
    // mateixa amplada que `wrap` perquè la seva barra reflecteixi el
    // recorregut real, i cada banda actualitza l'scrollLeft de l'altra.
    var wrap = document.getElementById("mesa-table-wrap");
    var topScroll = document.getElementById("mesa-table-scroll-top");
    var topInner = document.getElementById("mesa-table-scroll-top-inner");

    if (wrap && topScroll && topInner) {
      var syncingScroll = false;

      function syncLayout() {
        topInner.style.width = wrap.scrollWidth + "px";
        updateStickyOffsets();
      }

      function mirror(source, target) {
        return function () {
          if (syncingScroll) {
            return;
          }
          syncingScroll = true;
          target.scrollLeft = source.scrollLeft;
          syncingScroll = false;
        };
      }

      syncLayout();
      window.addEventListener("resize", syncLayout);
      if (window.ResizeObserver) {
        new ResizeObserver(syncLayout).observe(table);
      }

      topScroll.addEventListener("scroll", mirror(topScroll, wrap));
      wrap.addEventListener("scroll", mirror(wrap, topScroll));
    } else {
      updateStickyOffsets();
    }
  });
})();
