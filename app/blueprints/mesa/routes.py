"""Routes for "Resultats per mesa electoral".

Reutilitza els mateixos filtres de tipus d'elecció + convocatòria +
districte/secció/mesa que "Resultats electorals"
(app/blueprints/resultats/routes.py), però consulta
current_app.config["MESA_CLIENT"] (app/services/api_clients/mesa_client.py):
una font diferent, amb l'estat d'escrutini en viu de cada mesa
(OBERTA_MESA/COMUNICADA_MESA/HORA_COMUNICADA_MESA), no la de resultats per
candidatura. A diferència de "Resultats electorals" (on la zona tria una
sola mesa a mostrar), aquí sempre es mostra una taula: la zona només
n'acota les files. Els filtres propis d'aquest apartat (mesa oberta, mesa
comunicada) i el resum es calculen a services.py; aquesta vista només
demana dades i tria què renderitzar.

La taula també hi afegeix una columna de vots per cada partit, creuant amb
RESULTATS_CLIENT (mateix client que "Resultats electorals") via
services.merge_partit_vots — vegeu _partits_i_mesa_results().
"""
from __future__ import annotations

from flask import Blueprint, Response, current_app, render_template, request

from app.services.api_clients.base_client import ApiClientError

from . import services

bp = Blueprint("mesa", __name__, url_prefix="/mesa")


def _client():
    return current_app.config["MESA_CLIENT"]


def _resultats_client():
    return current_app.config["RESULTATS_CLIENT"]


def _partits_i_mesa_results(codi: str) -> tuple[list[dict], list[dict]]:
    """Llista mestra de partits + desglossament de vots mesa a mesa.

    Si la font de Resultats no respon, es degrada a columnes de partit
    buides (totes a 0) en comptes de trencar la pàgina d'estat d'escrutini,
    que és la funció principal d'aquesta vista.
    """
    try:
        partits = _resultats_client().get_results(codi)["candidatures"]
        mesa_results = _resultats_client().get_mesa_results(codi)
    except (ApiClientError, ValueError):
        return [], []
    return partits, mesa_results


_OBERTA_COMUNICADA_VALUES = ("", "SI", "NO")


def _empty_ctx(
    selected_districte: str = "", selected_seccio: str = "", selected_mesa: str = "",
    selected_oberta: str = "", selected_comunicada: str = "",
) -> dict:
    return {
        "tipus_list": [], "selected_tipus": None, "filtered": [], "selected_codi": None,
        "districtes": [], "selected_districte": selected_districte,
        "seccions": [], "selected_seccio": selected_seccio,
        "meses": [], "selected_mesa": selected_mesa,
        "mesa_rows": [], "summary": None, "partits": [],
        "selected_oberta": selected_oberta, "selected_comunicada": selected_comunicada,
    }


@bp.route("/")
def index():
    force_refresh = request.args.get("refresh") == "1"

    try:
        convocatories = _client().get_convocatories(force_refresh=force_refresh)
    except ApiClientError as exc:
        return render_template("mesa/index.html", error=str(exc), empty=False, **_empty_ctx())

    if not convocatories:
        return render_template("mesa/index.html", error=None, empty=True, **_empty_ctx())

    tipus_list = services.unique_tipus(convocatories)
    selected_tipus = request.args.get("tipus") or tipus_list[0]
    if selected_tipus not in tipus_list:
        selected_tipus = tipus_list[0]

    filtered = [c for c in convocatories if c["tipus"] == selected_tipus] or convocatories

    codi_arg = request.args.get("codi")
    valid_codis = {c["codi"] for c in filtered}
    selected_codi = codi_arg if codi_arg in valid_codis else filtered[0]["codi"]

    selected_oberta = request.args.get("oberta") or ""
    if selected_oberta not in _OBERTA_COMUNICADA_VALUES:
        selected_oberta = ""
    selected_comunicada = request.args.get("comunicada") or ""
    if selected_comunicada not in _OBERTA_COMUNICADA_VALUES:
        selected_comunicada = ""

    try:
        rows = _client().get_mesa_status(selected_codi, force_refresh=force_refresh)
    except (ApiClientError, ValueError) as exc:
        return render_template(
            "mesa/index.html", error=str(exc), empty=False,
            **{
                **_empty_ctx(selected_oberta=selected_oberta, selected_comunicada=selected_comunicada),
                "tipus_list": tipus_list, "selected_tipus": selected_tipus,
                "filtered": filtered, "selected_codi": selected_codi,
            },
        )

    districtes = services.unique_districtes(rows)
    districte_arg = request.args.get("districte") or ""
    selected_districte = districte_arg if districte_arg in districtes else ""

    seccions = services.seccions_for_districte(rows, selected_districte)
    seccio_arg = request.args.get("seccio") or ""
    selected_seccio = seccio_arg if seccio_arg in seccions else ""

    meses = services.meses_for_districte_seccio(rows, selected_districte, selected_seccio)
    mesa_arg = request.args.get("mesa") or ""
    selected_mesa = mesa_arg if mesa_arg in meses else ""

    zona_rows = services.filter_by_zona(rows, districte=selected_districte, seccio=selected_seccio, mesa=selected_mesa)
    summary = services.build_summary(zona_rows)
    mesa_rows = services.filter_meses(zona_rows, oberta=selected_oberta, comunicada=selected_comunicada)

    partits, mesa_results = _partits_i_mesa_results(selected_codi)
    mesa_rows = services.merge_partit_vots(mesa_rows, mesa_results, partits)

    return render_template(
        "mesa/index.html",
        error=None, empty=False, tipus_list=tipus_list, selected_tipus=selected_tipus,
        filtered=filtered, selected_codi=selected_codi,
        districtes=districtes, selected_districte=selected_districte,
        seccions=seccions, selected_seccio=selected_seccio,
        meses=meses, selected_mesa=selected_mesa,
        mesa_rows=mesa_rows, summary=summary, partits=partits,
        selected_oberta=selected_oberta, selected_comunicada=selected_comunicada,
    )


def _filtered_rows_for_export(codi: str):
    """Les mateixes files que la taula de la vista mostraria per a `codi` amb
    els filtres actuals de la query string (zona + oberta/comunicada)."""
    rows = _client().get_mesa_status(codi)
    rows = services.filter_by_zona(
        rows,
        districte=request.args.get("districte") or "",
        seccio=request.args.get("seccio") or "",
        mesa=request.args.get("mesa") or "",
    )
    return services.filter_meses(
        rows,
        oberta=request.args.get("oberta") or "",
        comunicada=request.args.get("comunicada") or "",
    )


@bp.route("/exporta/csv")
def exporta_csv():
    codi = request.args.get("codi", "")
    if not codi:
        return Response("Falta el parametre 'codi'", status=400)
    try:
        convocatories = _client().get_convocatories()
        rows = _filtered_rows_for_export(codi)
    except (ApiClientError, ValueError) as exc:
        return Response(str(exc), status=502)

    partits, mesa_results = _partits_i_mesa_results(codi)
    rows = services.merge_partit_vots(rows, mesa_results, partits)
    meta = services.build_export_meta(convocatories, codi, request.args)
    csv_text = services.rows_to_csv(rows, meta, partits)
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=mesa_{codi}.csv"},
    )


@bp.route("/exporta/pdf")
def exporta_pdf():
    codi = request.args.get("codi", "")
    if not codi:
        return Response("Falta el parametre 'codi'", status=400)
    try:
        convocatories = _client().get_convocatories()
        rows = _filtered_rows_for_export(codi)
    except (ApiClientError, ValueError) as exc:
        return Response(str(exc), status=502)

    partits, mesa_results = _partits_i_mesa_results(codi)
    rows = services.merge_partit_vots(rows, mesa_results, partits)
    meta = services.build_export_meta(convocatories, codi, request.args)
    pdf_bytes = services.rows_to_pdf(rows, meta, partits)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=mesa_{codi}.pdf"},
    )
