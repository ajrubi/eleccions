"""Application factory.

Wires together the Flask app, its blueprints, and the API clients used to
reach every external REST data source. This factory (and every blueprint
it registers) never opens a local database or writes to disk: all data
comes from HTTP calls made through services/api_clients/.
"""
from __future__ import annotations

import logging

from flask import Flask, redirect, request, url_for

from .config import Config
from .services.api_clients.cens_client import CensApiClient
from .services.api_clients.mesa_client import MesaEstatApiClient
from .services.api_clients.resultats_client import ResultatsApiClient


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    logging.basicConfig(level=logging.INFO)

    # Single shared, in-memory-cached client for the Resultats REST API.
    # Future clients (cens_client.py, admin_client.py) will be created the
    # same way, from their own CENS_API_BASE_URL / ADMIN_API_BASE_URL.
    app.config["RESULTATS_CLIENT"] = ResultatsApiClient(
        base_url=app.config["RESULTATS_API_BASE_URL"],
        csv_path=app.config["RESULTATS_CSV_PATH"],
        ttl_seconds=app.config["RESULTATS_CACHE_TTL_SECONDS"],
        timeout=app.config["HTTP_TIMEOUT_SECONDS"],
        max_retries=app.config["HTTP_MAX_RETRIES"],
    )

    # Cens electoral per mesa (agregat, anonimitzat) — vegeu config.py per
    # la diferència amb la futura cerca individual per DNI (CENS_API_BASE_URL).
    app.config["CENS_CLIENT"] = CensApiClient(
        base_url=app.config["CENS_MESA_API_BASE_URL"],
        csv_path=app.config["CENS_MESA_CSV_PATH"],
        ttl_seconds=app.config["CENS_MESA_CACHE_TTL_SECONDS"],
        timeout=app.config["HTTP_TIMEOUT_SECONDS"],
        max_retries=app.config["HTTP_MAX_RETRIES"],
    )

    # Estat d'escrutini per mesa (oberta/comunicada/hora) — font pròpia,
    # amb un TTL de caché curt perquè aquests valors canvien mentre dura
    # l'escrutini (vegeu config.py i services/api_clients/mesa_client.py).
    app.config["MESA_CLIENT"] = MesaEstatApiClient(
        base_url=app.config["MESA_ESTAT_API_BASE_URL"],
        csv_path=app.config["MESA_ESTAT_CSV_PATH"],
        ttl_seconds=app.config["MESA_ESTAT_CACHE_TTL_SECONDS"],
        timeout=app.config["HTTP_TIMEOUT_SECONDS"],
        max_retries=app.config["HTTP_MAX_RETRIES"],
    )

    from .blueprints.resultats.routes import bp as resultats_bp
    from .blueprints.cens.routes import bp as cens_bp
    from .blueprints.mesa.routes import bp as mesa_bp
    from .blueprints.estadistiques.routes import bp as estadistiques_bp
    from .blueprints.prediccions.routes import bp as prediccions_bp
    from .blueprints.admin.routes import bp as admin_bp

    app.register_blueprint(resultats_bp)
    app.register_blueprint(cens_bp)
    app.register_blueprint(mesa_bp)
    app.register_blueprint(estadistiques_bp)
    app.register_blueprint(prediccions_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def portal_index():
        return redirect(url_for("resultats.index"))

    # Which open-data CSV backs the page currently being rendered, keyed by
    # blueprint name: "resultats", "estadistiques" i "prediccions" totes
    # tres llegeixen de RESULTATS_CLIENT
    # (app/services/api_clients/resultats_client.py), així que comparteixen
    # la mateixa font. "admin" és encara un placeholder sense font de dades
    # pròpia, per això queda deliberadament fora — el peu de pàgina
    # simplement no hi mostra cap línia de "Font de dades".
    font_dades_per_blueprint = {
        "resultats": {"label": "Resultats electorals", "url": app.config["RESULTATS_SOURCE_URL"]},
        "estadistiques": {"label": "Resultats electorals", "url": app.config["RESULTATS_SOURCE_URL"]},
        "prediccions": {"label": "Resultats electorals", "url": app.config["RESULTATS_SOURCE_URL"]},
        "cens": {"label": "Cens electoral", "url": app.config["CENS_SOURCE_URL"]},
        "mesa": {"label": "Estat d'escrutini per mesa", "url": app.config["MESA_ESTAT_SOURCE_URL"]},
    }

    @app.context_processor
    def inject_nav():
        return {
            "nav_items": [
                {"endpoint": "resultats.index", "label": "Resultats electorals"},
                {"endpoint": "cens.index", "label": "Cens electoral"},
                {"endpoint": "mesa.index", "label": "Resultats per mesa"},
                {"endpoint": "estadistiques.index", "label": "Estadístiques comparatives"},
                {"endpoint": "prediccions.index", "label": "Prediccions"},
                {"endpoint": "admin.index", "label": "Àrea privada"},
            ],
            "font_dades": font_dades_per_blueprint.get(request.blueprint),
        }

    return app
