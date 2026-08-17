// Interactive tooltip for the "Participació i abstenció" stacked bar
// chart in Estadístiques comparatives. Purely progressive enhancement:
// every bar already carries a full aria-label, so screen readers and
// no-JS users get the same information without this script.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var tooltip = document.getElementById("compare-tooltip");
    var bars = document.querySelectorAll(".compare-chart__bar");
    if (!tooltip || !bars.length) {
      return;
    }

    function buildContent(bar) {
      if (bar.dataset.nd) {
        return (
          "<strong>" + bar.dataset.nom + "</strong> (" + bar.dataset.data + ")<br>" +
          "Sense dades de cens disponibles."
        );
      }
      return (
        "<strong>" + bar.dataset.nom + "</strong> (" + bar.dataset.data + ")<br>" +
        "Cens: " + bar.dataset.cens + "<br>" +
        "Participació: " + bar.dataset.participacio + "% (" + bar.dataset.participants + " vots)<br>" +
        "Abstenció: " + bar.dataset.abstencio + "% (" + bar.dataset.abstents + " vots)"
      );
    }

    function showTooltip(bar) {
      tooltip.innerHTML = buildContent(bar);
      tooltip.hidden = false;

      var barRect = bar.getBoundingClientRect();
      var tooltipRect = tooltip.getBoundingClientRect();

      var left = barRect.left + barRect.width / 2 - tooltipRect.width / 2;
      left = Math.max(8, Math.min(left, window.innerWidth - tooltipRect.width - 8));

      var top = barRect.top - tooltipRect.height - 10;
      if (top < 8) {
        top = barRect.bottom + 10;
      }

      tooltip.style.left = left + "px";
      tooltip.style.top = top + "px";
    }

    function hideTooltip() {
      tooltip.hidden = true;
    }

    bars.forEach(function (bar) {
      bar.addEventListener("mouseenter", function () { showTooltip(bar); });
      bar.addEventListener("mouseleave", hideTooltip);
      bar.addEventListener("focus", function () { showTooltip(bar); });
      bar.addEventListener("blur", hideTooltip);
    });
  });
})();
