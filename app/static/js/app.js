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

    document.querySelectorAll("form").forEach(function (form) {
      form.addEventListener("submit", showLoading);
    });

    document.querySelectorAll(".btn--primary").forEach(function (link) {
      link.addEventListener("click", showLoading);
    });
  });
})();
