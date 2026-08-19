// Progressive enhancement only: the app works without JavaScript
// (native <select> + submit button via <noscript>). This just adds
// auto-submit on filter change and a loading indicator while the next
// page is fetched, to make slow API responses visible to the user.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var overlay = document.getElementById("loading-overlay");

    function showLoading() {
      if (overlay) {
        overlay.hidden = false;
      }
    }

    document.querySelectorAll("[data-autosubmit]").forEach(function (field) {
      field.addEventListener("change", function () {
        showLoading();
        field.form.submit();
      });
    });

    // El widget de xat (#chat-widget) envia el seu formulari per fetch/AJAX,
    // no per navegació: mai "acaba de carregar" una pàgina nova que faci
    // desaparèixer aquest overlay, així que se n'exclou explícitament —
    // altrament es quedaria tapant tota la web per sempre (vegeu
    // chat-widget.js, que ja mostra el seu propi indicador "Escrivint…").
    document.querySelectorAll("form").forEach(function (form) {
      if (form.closest("#chat-widget")) {
        return;
      }
      form.addEventListener("submit", showLoading);
    });

    document.querySelectorAll(".btn--primary").forEach(function (link) {
      if (link.closest("#chat-widget")) {
        return;
      }
      link.addEventListener("click", showLoading);
    });
  });
})();
