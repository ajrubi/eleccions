"""Assistent IA (xat flotant) del portal.

Widget disponible a totes les pàgines (vegeu templates/base.html): un únic
endpoint JSON que reenvia el missatge de l'usuari a AiChatClient
(app/services/ai_chat_client.py), que respon només a partir del digest de
dades ja obertes d'aquest portal, via l'API de Groq. Aquest mòdul només
valida la petició i tradueix els errors de la crida (ApiClientError i
subclasses, les mateixes que fa servir tota la resta de l'app — vegeu
services/api_clients/base_client.py) a respostes HTTP — no coneix res
sobre com es construeix la resposta ni d'on surten les dades.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.services.api_clients.base_client import ApiClientError, ApiResponseError

bp = Blueprint("chat", __name__, url_prefix="/chat")

_MAX_MESSAGE_CHARS = 1000
_MAX_HISTORY_TURNS = 12


def _client():
    return current_app.config["AI_CHAT_CLIENT"]


@bp.route("/api/status")
def status():
    return jsonify({"enabled": _client().enabled})


@bp.route("/api/message", methods=["POST"])
def message():
    client = _client()
    if not client.enabled:
        return jsonify({"error": "L'assistent IA no està disponible en aquest moment."}), 503

    payload = request.get_json(silent=True) or {}
    text = (payload.get("message") or "").strip()
    if not text:
        return jsonify({"error": "Escriu una pregunta abans d'enviar-la."}), 400
    if len(text) > _MAX_MESSAGE_CHARS:
        return jsonify({"error": f"El missatge és massa llarg (màxim {_MAX_MESSAGE_CHARS} caràcters)."}), 400

    raw_history = payload.get("history") or []
    history = [
        {"role": turn.get("role"), "content": turn.get("content")}
        for turn in raw_history[-_MAX_HISTORY_TURNS:]
        if isinstance(turn, dict) and turn.get("role") in ("user", "assistant") and turn.get("content")
    ]

    try:
        reply = client.answer(text, history)
    except ApiResponseError as exc:
        if exc.status_code == 401:
            current_app.logger.error("Clau d'API de Groq invàlida o absent")
            return jsonify({"error": "L'assistent IA no està ben configurat. Torna-ho a provar més tard."}), 502
        if exc.status_code == 429:
            return jsonify({"error": "L'assistent IA té massa peticions ara mateix. Torna-ho a provar en uns segons."}), 429
        current_app.logger.error("Error de l'API de Groq (HTTP %s): %s", exc.status_code, exc)
        return jsonify({"error": "L'assistent IA no ha pogut respondre. Torna-ho a provar més tard."}), 502
    except ApiClientError as exc:
        current_app.logger.error("Error contactant amb l'assistent IA: %s", exc)
        return jsonify({"error": "No s'ha pogut contactar amb l'assistent IA. Torna-ho a provar més tard."}), 502

    return jsonify({"reply": reply})
