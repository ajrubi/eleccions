"""Central configuration: base URLs, timeouts and cache TTLs for every
external API this portal consumes.

There is no local database configuration here because there is none —
every value below points at an HTTP data source.
"""
from __future__ import annotations

import os


class Config:
    # --- Resultats electorals -------------------------------------------
    # Today the "REST API" is a public, read-only CSV published on GitHub.
    # It is still accessed exclusively through services/api_clients, so
    # swapping it for a real REST endpoint later only means changing this
    # base URL (and, if the response shape changes, resultats_client.py).
    RESULTATS_API_BASE_URL = os.environ.get(
        "RESULTATS_API_BASE_URL",
        "https://raw.githubusercontent.com/ajrubi/opendata/refs/heads/main/datasets/csv",
    )
    RESULTATS_CSV_PATH = os.environ.get("RESULTATS_CSV_PATH", "public_eleccions_partits.csv")
    # Dades històriques: un cop una convocatòria es publica, els seus
    # resultats ja no canvien. TTL llarg (24h) perquè no cal repetir la
    # descàrrega cada pocs minuts — a diferència de MESA_ESTAT_CACHE_TTL_SECONDS
    # de sota, que sí que necessita un TTL curt un cop hi hagi escrutini en viu.
    RESULTATS_CACHE_TTL_SECONDS = int(os.environ.get("RESULTATS_CACHE_TTL_SECONDS", "86400"))

    # --- Cens electoral per mesa (agregat, anonimitzat) ------------------
    # Igual que Resultats: avui és un CSV públic de només lectura tractat
    # com si fos un endpoint REST. No conté cap dada personal identificable
    # (no DNI, no nom), només comptatge agregat per mesa.
    CENS_MESA_API_BASE_URL = os.environ.get(
        "CENS_MESA_API_BASE_URL",
        "https://raw.githubusercontent.com/ajrubi/opendata/refs/heads/main/datasets/csv",
    )
    CENS_MESA_CSV_PATH = os.environ.get("CENS_MESA_CSV_PATH", "public_eleccions_cens.csv")
    # Igual que Resultats: cens ja tancat d'una convocatòria passada, no
    # canvia mai més. TTL llarg (24h) pel mateix motiu.
    CENS_MESA_CACHE_TTL_SECONDS = int(os.environ.get("CENS_MESA_CACHE_TTL_SECONDS", "86400"))

    # --- Estat d'escrutini per mesa (oberta/comunicada/hora) -------------
    # Font diferent de la de Resultats: mateix CODI_CONVOCATORIA, però un
    # CSV propi (public_eleccions_meses.csv) amb l'estat de cada mesa en
    # temps real (OBERTA_MESA/COMUNICADA_MESA/HORA_COMUNICADA_MESA), a més
    # dels seus recomptes d'avanç (AVAN1/2/3).
    #
    # TODO (quan es faci la pantalla d'escrutini en viu): aquests valors
    # poden canviar mentre dura l'escrutini, així que aquest TTL s'hauria de
    # tornar a baixar a un valor curt (per exemple els 60s que tenia abans
    # d'aquest canvi) perquè la vista reflecteixi l'estat real gairebé en
    # temps real. Mentre aquesta pantalla en viu no existeix, es tracta
    # igual que les altres dues fonts (24h) per no repetir descàrregues
    # innecessàries d'unes dades que, de fet, encara no canvien en viu.
    MESA_ESTAT_API_BASE_URL = os.environ.get(
        "MESA_ESTAT_API_BASE_URL",
        "https://raw.githubusercontent.com/ajrubi/opendata/refs/heads/main/datasets/csv",
    )
    MESA_ESTAT_CSV_PATH = os.environ.get("MESA_ESTAT_CSV_PATH", "public_eleccions_meses.csv")
    MESA_ESTAT_CACHE_TTL_SECONDS = int(os.environ.get("MESA_ESTAT_CACHE_TTL_SECONDS", "86400"))

    # --- Font de dades, mostrada al peu de pàgina ------------------------
    # La mateixa URL que RESULTATS_API_BASE_URL/CENS_MESA_API_BASE_URL ja
    # fan servir per llegir les dades, sencera: és la que es mostra (i
    # enllaça) al peu de cada pàgina perquè qualsevol persona pugui
    # baixar-se el CSV original directament, sense passar per l'API.
    RESULTATS_SOURCE_URL = os.environ.get(
        "RESULTATS_SOURCE_URL", f"{RESULTATS_API_BASE_URL}/{RESULTATS_CSV_PATH}"
    )
    CENS_SOURCE_URL = os.environ.get(
        "CENS_SOURCE_URL", f"{CENS_MESA_API_BASE_URL}/{CENS_MESA_CSV_PATH}"
    )
    MESA_ESTAT_SOURCE_URL = os.environ.get(
        "MESA_ESTAT_SOURCE_URL", f"{MESA_ESTAT_API_BASE_URL}/{MESA_ESTAT_CSV_PATH}"
    )

    # --- Cens electoral: cerca individual per DNI (TODO: no implementat) -
    # TODO: quan existeixi, apuntar aquí a la futura API REST de només
    # lectura del cens per a la cerca d'un elector concret (GET per DNI +
    # data de naixement). A diferència del cens agregat per mesa (a dalt),
    # aquesta sí que tractaria dades personals identificables, així que
    # l'API haurà de portar la seva pròpia autenticació (OAuth2/JWT), RBAC
    # i auditoria, complint el RGPD/LOPDGDD. Aquest projecte NOMÉS hi farà
    # peticions GET amb les credencials adequades — mai reimplementar
    # aquesta seguretat pel seu compte.
    CENS_API_BASE_URL = os.environ.get("CENS_API_BASE_URL", "")

    # --- Àrea privada / Administració (TODO: no implementat encara) ------
    # TODO: quan existeixi, apuntar aquí a la futura API REST d'administració
    # (login, gestió de convocatòries, escrutini). Requerirà OAuth2/JWT,
    # control d'accés per rols i registre d'auditoria (qui ha fet quina
    # operació d'escriptura i quan), per tractar-se d'operacions crítiques
    # sobre recomptes de vots. El token s'enviaria via ADMIN_API_TOKEN /
    # sessió d'usuari, mai emmagatzemat en aquest projecte de forma persistent.
    ADMIN_API_BASE_URL = os.environ.get("ADMIN_API_BASE_URL", "")
    ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")

    # --- HTTP client defaults, shared by every api_clients/*.py ----------
    HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "10"))
    HTTP_MAX_RETRIES = int(os.environ.get("HTTP_MAX_RETRIES", "3"))

    # --- Assistent IA (xat) ------------------------------------------------
    # Un model Llama servit per Groq respon només a partir d'un resum
    # ("digest") de les dades ja obertes d'aquest portal
    # (convocatòries/resultats/cens), regenerat com a màxim un cop al mes —
    # vegeu app/services/ai_digest.py. Es parla amb l'API de Groq com amb
    # qualsevol altra font d'aquest projecte: via BaseApiClient (vegeu
    # services/api_clients/groq_client.py), no amb cap SDK propi. Sense clau
    # configurada, el xat es desactiva sol (AiChatClient.enabled == False)
    # en lloc de trencar la resta de l'aplicació.
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_TIMEOUT_SECONDS = float(os.environ.get("GROQ_TIMEOUT_SECONDS", "30"))

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
