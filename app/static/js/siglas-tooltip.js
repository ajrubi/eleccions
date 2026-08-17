// Custom tooltip for party-acronym <abbr title="..."> elements, reusing
// the exact same visual format and positioning logic as compare-chart.js
// (the "Participació i abstenció" chart tooltip): the full party name
// highlighted in <strong>, shown near the pointer instead of the native
// browser title tooltip.
//
// The native `title` attribute stays in the HTML the whole time (it's
// what makes the abbreviation accessible without JS/for screen readers);
// it's only removed for the moment the pointer is over the element so
// the browser's own tooltip doesn't show up doubled with this one.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var tooltip = document.getElementById("siglas-tooltip");
    var abbrs = document.querySelectorAll(".siglas-abbr[title]");
    if (!tooltip || !abbrs.length) {
      return;
    }

    function showTooltip(el) {
      var nom = el.getAttribute("title");
      if (nom) {
        el.dataset.savedTitle = nom;
        el.removeAttribute("title");
      }

      tooltip.innerHTML = "<strong>" + (nom || el.dataset.savedTitle || "") + "</strong>";
      tooltip.hidden = false;

      var elRect = el.getBoundingClientRect();
      var tooltipRect = tooltip.getBoundingClientRect();

      var left = elRect.left + elRect.width / 2 - tooltipRect.width / 2;
      left = Math.max(8, Math.min(left, window.innerWidth - tooltipRect.width - 8));

      var top = elRect.top - tooltipRect.height - 10;
      if (top < 8) {
        top = elRect.bottom + 10;
      }

      tooltip.style.left = left + "px";
      tooltip.style.top = top + "px";
    }

    function hideTooltip(el) {
      tooltip.hidden = true;
      if (el.dataset.savedTitle) {
        el.setAttribute("title", el.dataset.savedTitle);
        delete el.dataset.savedTitle;
      }
    }

    abbrs.forEach(function (el) {
      el.addEventListener("mouseenter", function () { showTooltip(el); });
      el.addEventListener("mouseleave", function () { hideTooltip(el); });
      el.addEventListener("focus", function () { showTooltip(el); });
      el.addEventListener("blur", function () { hideTooltip(el); });
    });
  });
})();
