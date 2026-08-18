// Cercador per filtrar la llista de partits a "Prediccions" (mode joc).
// Progressive enhancement only: sense JS, tots els partits ja hi surten
// com a checkboxes normals (vegeu templates/prediccions/index.html), així
// que la selecció es continua podent fer igualment. Aquest script només
// amaga les opcions que no coincideixen amb la cerca — mai les que ja
// estan marcades, perquè escriure al cercador no faci "desaparèixer" una
// selecció ja feta.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var input = document.getElementById("prediccio-search");
    var grid = document.getElementById("prediccio-grid");
    if (!input || !grid) {
      return;
    }

    var noMatch = document.getElementById("prediccio-no-match");
    var options = Array.prototype.slice.call(grid.querySelectorAll(".prediccio-picker__option[data-search]"));

    function stripAccents(text) {
      return text.normalize("NFD").replace(new RegExp("[\\u0300-\\u036f]", "g"), "");
    }

    function filter() {
      var term = stripAccents(input.value.trim().toLowerCase());
      var anyVisible = false;

      options.forEach(function (option) {
        var checkbox = option.querySelector("input[type=checkbox]");
        var matches = term === "" || stripAccents(option.dataset.search).indexOf(term) !== -1;
        var visible = matches || (checkbox && checkbox.checked);
        option.hidden = !visible;
        if (visible) {
          anyVisible = true;
        }
      });

      if (noMatch) {
        noMatch.hidden = anyVisible;
      }
    }

    input.addEventListener("input", filter);
  });
})();
