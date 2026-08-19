// Widget flotant de l'assistent IA (vegeu templates/base.html i
// blueprints/chat/routes.py). Manté l'historial de la conversa només en
// memòria (es perd en recarregar la pàgina) i el reenvia sencer a cada
// petició perquè el backend pugui donar context a l'assistent — l'API de
// Claude no guarda estat entre peticions.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var widget = document.getElementById("chat-widget");
    var toggle = document.getElementById("chat-widget-toggle");
    var closeBtn = document.getElementById("chat-widget-close");
    var panel = document.getElementById("chat-widget-panel");
    var messagesEl = document.getElementById("chat-widget-messages");
    var form = document.getElementById("chat-widget-form");
    var input = document.getElementById("chat-widget-input");
    if (!widget || !toggle || !panel || !messagesEl || !form || !input) {
      return;
    }

    var history = [];
    var sending = false;
    var CLOSE_ANIMATION_MS = 180;
    var closeTimer = null;

    function openPanel() {
      clearTimeout(closeTimer);
      panel.hidden = false;
      // Cal treure "hidden" un instant abans d'afegir la classe que
      // dispara la transició CSS — canviar-los en el mateix "tick" fa
      // que el navegador no arribi a animar l'aparició.
      requestAnimationFrame(function () {
        panel.classList.add("chat-widget__panel--visible");
      });
      toggle.setAttribute("aria-expanded", "true");
      input.focus();
    }

    function closePanel() {
      panel.classList.remove("chat-widget__panel--visible");
      toggle.setAttribute("aria-expanded", "false");
      closeTimer = setTimeout(function () {
        panel.hidden = true;
      }, CLOSE_ANIMATION_MS);
    }

    toggle.addEventListener("click", function () {
      if (panel.hidden) {
        openPanel();
      } else {
        closePanel();
      }
    });
    closeBtn.addEventListener("click", closePanel);

    function addBubble(role, text, modifier) {
      var bubble = document.createElement("p");
      bubble.className = "chat-widget__bubble chat-widget__bubble--" + role;
      if (modifier) {
        bubble.classList.add("chat-widget__bubble--" + modifier);
      }
      bubble.textContent = text;
      messagesEl.appendChild(bubble);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return bubble;
    }

    function setSending(value) {
      sending = value;
      input.disabled = value;
      form.querySelector(".chat-widget__send").disabled = value;
    }

    form.addEventListener("submit", function (evt) {
      evt.preventDefault();
      var text = input.value.trim();
      if (!text || sending) {
        return;
      }

      addBubble("user", text);
      input.value = "";
      setSending(true);
      var typingBubble = addBubble("assistant", "Escrivint…", "typing");

      fetch("/chat/api/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: history }),
      })
        .then(function (resp) {
          return resp.json().then(function (data) {
            return { ok: resp.ok, data: data };
          });
        })
        .then(function (result) {
          typingBubble.remove();
          if (result.ok) {
            addBubble("assistant", result.data.reply);
            history.push({ role: "user", content: text });
            history.push({ role: "assistant", content: result.data.reply });
          } else {
            addBubble("assistant", result.data.error || "Hi ha hagut un error inesperat.", "error");
          }
        })
        .catch(function () {
          typingBubble.remove();
          addBubble("assistant", "No s'ha pogut contactar amb l'assistent. Comprova la connexió i torna-ho a provar.", "error");
        })
        .finally(function () {
          setSending(false);
          input.focus();
        });
    });

    input.addEventListener("keydown", function (evt) {
      if (evt.key === "Enter" && !evt.shiftKey) {
        evt.preventDefault();
        form.requestSubmit();
      }
    });
  });
})();
