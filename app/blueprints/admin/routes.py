"""Placeholder for "Àrea privada / Administració".

TODO: aquest blueprint gestionarà el login dels empleats de l'ajuntament i,
un cop autenticats, la gestió de convocatòries (POST/PUT/DELETE) i
l'escrutini de vots per partit/mesa (POST/PUT), sempre contra una futura
API REST d'administració (ADMIN_API_BASE_URL a app/config.py), mai escrivint
a un fitxer o base de dades local. El patró és el mateix que a
resultats_client.py: un nou services/api_clients/admin_client.py construït
sobre BaseApiClient, afegint el token/sessió de l'usuari autenticat a les
capçaleres (BaseApiClient ja suporta Authorization: Bearer <token>).

TODO (seguretat crítica): aquest apartat és el que realment escriu dades
(recomptes de vots, convocatòries). La futura API externa haurà de tenir:
  - autenticació robusta OAuth2/JWT per als usuaris administradors;
  - control d'accés per rols (qui pot escrutar, qui pot crear convocatòries);
  - registre d'auditoria complet (qui ha fet quina operació d'escriptura,
    sobre quina convocatòria/mesa/partit, i quan);
  - compliment RGPD/LOPDGDD.
Aquesta aplicació web NOMÉS ha de consumir aquesta API amb les credencials
adequades (sessió d'usuari + capçalera Authorization) — no ha de
reimplementar cap d'aquesta seguretat pel seu compte.
"""
from flask import Blueprint, render_template

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
def index():
    return render_template("admin/coming_soon.html")
