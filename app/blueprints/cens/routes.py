"""Cens electoral per mesa — l'únic sub-apartat implementat d'aquest blueprint.

Mostra el cens agregat (comptat) per mesa electoral, a partir de dades
anonimitzades (sense DNI ni cap identificador personal). Igual que a
resultats/routes.py, aquesta vista només demana dades ja processades a
current_app.config["CENS_CLIENT"] i a services.py; no fa cap càlcul propi
ni toca cap fitxer o base de dades local.

TODO: la cerca individual d'un elector per DNI + data de naixement segueix
sent un placeholder de cara al futur (no es toca en aquesta implementació):
necessitarà una API externa molt més sensible (dades personals), amb
autenticació OAuth2/JWT, control d'accés per rols i registre d'auditoria —
vegeu el README. Aquesta vista de cens agregat no té aquests requisits
perquè no exposa cap dada personal identificable.
"""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from app.services.api_clients.base_client import ApiClientError

from . import services

bp = Blueprint("cens", __name__, url_prefix="/cens")


def _client():
    return current_app.config["CENS_CLIENT"]


@bp.route("/")
def index():
    force_refresh = request.args.get("refresh") == "1"

    try:
        convocatories = _client().get_convocatories(force_refresh=force_refresh)
    except ApiClientError as exc:
        return render_template(
            "cens/index.html",
            error=str(exc), empty=False, convocatories=[], selected_nom=None,
            mesa_rows=[], total=0,
        )

    if not convocatories:
        return render_template(
            "cens/index.html",
            error=None, empty=True, convocatories=[], selected_nom=None,
            mesa_rows=[], total=0,
        )

    noms_disponibles = {c["nom"] for c in convocatories}
    selected_nom = request.args.get("convocatoria")
    if selected_nom not in noms_disponibles:
        selected_nom = convocatories[0]["nom"]

    try:
        location_rows = _client().get_elector_location_rows(selected_nom, force_refresh=force_refresh)
    except (ApiClientError, ValueError) as exc:
        return render_template(
            "cens/index.html",
            error=str(exc), empty=False, convocatories=convocatories, selected_nom=selected_nom,
            mesa_rows=[], total=0,
        )

    mesa_rows = services.build_cens_per_mesa(location_rows)
    total = services.total_cens(mesa_rows)

    return render_template(
        "cens/index.html",
        error=None, empty=False, convocatories=convocatories, selected_nom=selected_nom,
        mesa_rows=mesa_rows, total=total,
    )
