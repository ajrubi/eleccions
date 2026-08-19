"""Routes for "Dades": catàleg de les fonts obertes que consumeix el portal.

A diferència de la resta de blueprints, aquest no mostra resultats
electorals: documenta, per a qui vulgui reutilitzar les mateixes dades
obertes, quins CSV hi ha darrere de cada apartat, quins camps porten (en
viu, via `get_dataset_info()` de cada client — mai una llista escrita a
mà), quants registres tenen ara mateix, i com descarregar-los. També hi
recull, en text estàtic, la tecnologia del projecte i els càlculs que fa
(participació, vots vàlids, D'Hondt, % d'escrutini...).
"""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from app.services.api_clients.base_client import ApiClientError

from . import services

bp = Blueprint("dades", __name__, url_prefix="/dades")

_CLIENT_CONFIG_KEYS = {
    "resultats": "RESULTATS_CLIENT",
    "cens": "CENS_CLIENT",
    "mesa": "MESA_CLIENT",
}


@bp.route("/")
def index():
    force_refresh = request.args.get("refresh") == "1"
    datasets = []
    for key, config_key in _CLIENT_CONFIG_KEYS.items():
        client = current_app.config[config_key]
        try:
            info = client.get_dataset_info(force_refresh=force_refresh)
            error = None
        except ApiClientError as exc:
            info = None
            error = str(exc)
        datasets.append(services.build_dataset_view(key, info, error, current_app.config))

    return render_template(
        "dades/index.html",
        datasets=datasets,
        tecnologia=services.TECNOLOGIA,
        calculs=services.CALCULS,
    )
