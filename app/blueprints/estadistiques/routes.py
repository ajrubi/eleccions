"""Estadístiques comparatives.

Sub-apartats implementats:
  * "Participació i abstenció per convocatòria" — compara aquestes dues
    magnituds al llarg del temps per a un mateix tipus de convocatòria.
  * "Participació i abstenció per avanços" — el mateix, però desglossat
    pels checkpoints de recompte (Avanç 1/2/3) de cada convocatòria.
  * "Vots per candidatura" — mapa de calor de % de vots per candidatura
    al llarg de les convocatòries.

Igual que a resultats/routes.py, aquesta vista només demana dades ja
processades a current_app.config["RESULTATS_CLIENT"]; l'agregació
"comparativa" (combinar diverses convocatòries) viu a services.py, no aquí.
"""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from app.services.api_clients.base_client import ApiClientError

from . import services

bp = Blueprint("estadistiques", __name__, url_prefix="/estadistiques")


def _client():
    return current_app.config["RESULTATS_CLIENT"]


VISTES_VALIDES = ("participacio", "avancos", "candidatures")


@bp.route("/")
def index():
    force_refresh = request.args.get("refresh") == "1"
    vista = request.args.get("vista") if request.args.get("vista") in VISTES_VALIDES else "participacio"

    empty_candidatura_ctx = {"selected_partits": [], "selected_chips": [], "available_options": []}

    try:
        convocatories = _client().get_convocatories(force_refresh=force_refresh)
    except ApiClientError as exc:
        return render_template(
            "estadistiques/index.html",
            error=str(exc), empty=False, tipus_list=[], selected_tipus=None, vista=vista,
            series=[], avancos=None, heatmap=None, **empty_candidatura_ctx,
        )

    if not convocatories:
        return render_template(
            "estadistiques/index.html",
            error=None, empty=True, tipus_list=[], selected_tipus=None, vista=vista,
            series=[], avancos=None, heatmap=None, **empty_candidatura_ctx,
        )

    tipus_list = services.unique_tipus(convocatories)
    selected_tipus = request.args.get("tipus") or tipus_list[0]
    if selected_tipus not in tipus_list:
        selected_tipus = tipus_list[0]

    series = None
    avancos = None
    heatmap = None
    candidatura_ctx = dict(empty_candidatura_ctx)
    if vista == "candidatures":
        heatmap = services.build_vots_candidatura_heatmap(_client(), convocatories, selected_tipus)
        options = services.candidatura_options(heatmap)
        valid_codis = {opt["codi"] for opt in options}
        selected_partits = [p for p in request.args.getlist("partit") if p in valid_codis]
        heatmap = services.filter_heatmap_by_partits(heatmap, selected_partits)
        selected_chips, available_options = services.split_candidatura_options(options, selected_partits)
        candidatura_ctx = {
            "selected_partits": selected_partits, "selected_chips": selected_chips,
            "available_options": available_options,
        }
    elif vista == "avancos":
        avancos = services.build_participacio_avancos_heatmap(_client(), convocatories, selected_tipus)
    else:
        series = services.build_participacio_abstencio_series(_client(), convocatories, selected_tipus)

    return render_template(
        "estadistiques/index.html",
        error=None, empty=False, tipus_list=tipus_list, selected_tipus=selected_tipus, vista=vista,
        series=series, avancos=avancos, heatmap=heatmap, **candidatura_ctx,
    )
