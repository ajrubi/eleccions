"""Routes for "Resultats electorals" — the only fully implemented section.

Every value rendered here comes from ``current_app.config["RESULTATS_CLIENT"]``
(app/services/api_clients/resultats_client.py), which talks to the Resultats
REST data source over HTTP. This module does not fetch, parse or aggregate
raw data itself, and it never touches a local database or file: it only
asks the client for already-processed results and picks what to display.
"""
from __future__ import annotations

from flask import Blueprint, Response, current_app, render_template, request

from app.services.api_clients.base_client import ApiClientError

from . import services

bp = Blueprint("resultats", __name__, url_prefix="/resultats")


def _client():
    return current_app.config["RESULTATS_CLIENT"]


@bp.route("/")
def index():
    force_refresh = request.args.get("refresh") == "1"
    empty_zona_ctx = {
        "districtes": [], "selected_districte": "", "seccions": [], "selected_seccio": "",
        "meses": [], "selected_mesa": "",
    }

    try:
        convocatories = _client().get_convocatories(force_refresh=force_refresh)
    except ApiClientError as exc:
        return render_template(
            "resultats/index.html",
            error=str(exc), empty=False, convocatories=[], tipus_list=[],
            filtered=[], selected_tipus=None, selected_codi=None, results=None,
            **empty_zona_ctx,
        )

    if not convocatories:
        return render_template(
            "resultats/index.html",
            error=None, empty=True, convocatories=[], tipus_list=[],
            filtered=[], selected_tipus=None, selected_codi=None, results=None,
            **empty_zona_ctx,
        )

    tipus_list = services.unique_tipus(convocatories)
    selected_tipus = request.args.get("tipus") or tipus_list[0]
    if selected_tipus not in tipus_list:
        selected_tipus = tipus_list[0]

    filtered = [c for c in convocatories if c["tipus"] == selected_tipus] or convocatories

    codi_arg = request.args.get("codi")
    valid_codis = {c["codi"] for c in filtered}
    selected_codi = codi_arg if codi_arg in valid_codis else filtered[0]["codi"]

    try:
        combos = _client().get_zones(selected_codi, force_refresh=force_refresh)
    except ApiClientError:
        combos = []

    districtes = services.unique_districtes(combos)
    districte_arg = request.args.get("districte") or ""
    selected_districte = districte_arg if districte_arg in districtes else ""

    seccions = services.seccions_for_districte(combos, selected_districte)
    seccio_arg = request.args.get("seccio") or ""
    selected_seccio = seccio_arg if seccio_arg in seccions else ""

    meses = services.meses_for_districte_seccio(combos, selected_districte, selected_seccio)
    mesa_arg = request.args.get("mesa") or ""
    selected_mesa = mesa_arg if mesa_arg in meses else ""

    zona_ctx = {
        "districtes": districtes, "selected_districte": selected_districte,
        "seccions": seccions, "selected_seccio": selected_seccio,
        "meses": meses, "selected_mesa": selected_mesa,
    }

    try:
        raw_results = _client().get_results(
            selected_codi, force_refresh=force_refresh,
            districte=selected_districte or None, seccio=selected_seccio or None,
            mesa=selected_mesa or None,
        )
    except (ApiClientError, ValueError) as exc:
        return render_template(
            "resultats/index.html",
            error=str(exc), empty=False, convocatories=convocatories, tipus_list=tipus_list,
            filtered=filtered, selected_tipus=selected_tipus, selected_codi=selected_codi, results=None,
            **zona_ctx,
        )

    view_model = services.build_view_model(raw_results)

    return render_template(
        "resultats/index.html",
        error=None, empty=False, convocatories=convocatories, tipus_list=tipus_list,
        filtered=filtered, selected_tipus=selected_tipus, selected_codi=selected_codi, results=view_model,
        **zona_ctx,
    )


@bp.route("/exporta/csv")
def exporta_csv():
    codi = request.args.get("codi", "")
    if not codi:
        return Response("Falta el parametre 'codi'", status=400)
    try:
        results = _client().get_results(
            codi, districte=request.args.get("districte") or None, seccio=request.args.get("seccio") or None,
            mesa=request.args.get("mesa") or None,
        )
    except (ApiClientError, ValueError) as exc:
        return Response(str(exc), status=502)
    csv_text = services.results_to_csv(results)
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=resultats_{codi}.csv"},
    )


@bp.route("/exporta/pdf")
def exporta_pdf():
    codi = request.args.get("codi", "")
    if not codi:
        return Response("Falta el parametre 'codi'", status=400)
    try:
        results = _client().get_results(
            codi, districte=request.args.get("districte") or None, seccio=request.args.get("seccio") or None,
            mesa=request.args.get("mesa") or None,
        )
        pdf_bytes = services.results_to_pdf(results)
    except (ApiClientError, ValueError) as exc:
        return Response(str(exc), status=502)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=resultats_{codi}.pdf"},
    )
