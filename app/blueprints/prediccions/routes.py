"""Prediccions (mode joc).

L'usuari tria un tipus d'elecció i els partits que hi vol seguir; l'app
revela la seva predicció de tendència (puja/baixa/estable) per a cada un,
calculada a services.py a partir del % de vots vàlids de les convocatòries
anteriors d'aquest mateix tipus. És un exercici estadístic senzill i
merament orientatiu/lúdic — no una enquesta ni una previsió electoral
oficial — vegeu l'avís al template.

Igual que a resultats/routes.py i estadistiques/routes.py, aquesta vista
només demana dades ja disponibles a current_app.config["RESULTATS_CLIENT"];
tota l'agregació viu a services.py, no aquí.
"""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from app.services.api_clients.base_client import ApiClientError

from . import services

bp = Blueprint("prediccions", __name__, url_prefix="/prediccions")


def _client():
    return current_app.config["RESULTATS_CLIENT"]


def _empty_ctx() -> dict:
    return {
        "tipus_list": [], "selected_tipus": None,
        "partit_options": [], "selected_partits": [],
        "predictions": [],
    }


@bp.route("/")
def index():
    force_refresh = request.args.get("refresh") == "1"

    try:
        convocatories = _client().get_convocatories(force_refresh=force_refresh)
    except ApiClientError as exc:
        return render_template("prediccions/index.html", error=str(exc), empty=False, **_empty_ctx())

    if not convocatories:
        return render_template("prediccions/index.html", error=None, empty=True, **_empty_ctx())

    tipus_list = services.unique_tipus(convocatories)
    selected_tipus = request.args.get("tipus") or tipus_list[0]
    if selected_tipus not in tipus_list:
        selected_tipus = tipus_list[0]

    partit_options = services.partit_options(_client(), convocatories, selected_tipus)
    valid_codis = {opt["codi"] for opt in partit_options}
    selected_partits = [p for p in request.args.getlist("partit") if p in valid_codis]

    predictions = []
    if selected_partits:
        predictions = services.build_predictions(_client(), convocatories, selected_tipus, selected_partits)

    return render_template(
        "prediccions/index.html",
        error=None, empty=False, tipus_list=tipus_list, selected_tipus=selected_tipus,
        partit_options=partit_options, selected_partits=selected_partits, predictions=predictions,
    )
