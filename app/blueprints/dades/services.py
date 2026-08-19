"""Contingut de l'apartat "Dades": catàleg dels CSV consumits pel portal.

Aquest mòdul no fa cap crida HTTP ni llegeix cap DataFrame: `routes.py` ja
demana l'esquema en viu (columnes/tipus/comptatges) a cada client via
`get_dataset_info()` (app/services/dataset_info.py). Aquí només s'hi guarda
el contingut que NO es pot deduir del CSV en si — la descripció de cada
camp, com s'ha d'utilitzar el conjunt de dades, i la fitxa estàtica de
tecnologia/càlculs de tot el portal — i es combina amb l'esquema en viu en
`build_dataset_view()`.
"""
from __future__ import annotations

from typing import Any, Optional

# Camps que es repeteixen, amb el mateix significat, a les tres fonts.
_COMMON_FIELD_DOCS = {
    "ID": "Identificador intern de la fila dins el conjunt de dades obert.",
    "CODI_ENS": "Codi de l'ens (administració) que publica les dades.",
    "NOM_ENS": "Nom de l'ens que publica les dades: sempre \"Ajuntament de Rubí\".",
    "CODI_CONVOCATORIA": "Identificador únic de la convocatòria electoral — el camp que aquest portal fa servir per enllaçar les tres fonts entre elles.",
    "NOM_CONVOCATORIA": "Nom complet de la convocatòria (p. ex. «Eleccions Municipals 2023»).",
    "ANY_CONVOCATORIA": "Any en què es va celebrar la convocatòria.",
    "DATA_CONVOCATORIA": "Data de la votació.",
    "CODI_TIPUS_CONVOCATORIA": "Codi numèric del tipus d'elecció.",
    "TIPUS_CONVOCATORIA": "Tipus d'elecció (Municipals, Generals, Autonòmiques, Europees, Senat...).",
    "DISTRICTE_MESA": "Districte on hi ha aquesta mesa electoral.",
    "SECCIO_MESA": "Secció censal on hi ha aquesta mesa electoral.",
    "MESA": "Lletra de la mesa electoral dins la secció.",
    "CODI_DISTRICTE_SECCIO": "Codi combinat «districte-secció».",
    "CODI_DISTRICTE_SECCIO_MESA": "Codi combinat «districte-secció-mesa»: identifica una mesa de manera única dins la convocatòria.",
    "OBERTA_MESA": "«SI»/«NO»: si la mesa ja s'ha obert per votar.",
    "COMUNICADA_MESA": "«SI»/«NO»: si l'acta d'aquesta mesa ja s'ha transmès, és a dir, si ja està escrutinada.",
    "MESA_COMUNICADA": "«SI»/«NO»: si l'acta d'aquesta mesa ja s'ha transmès, és a dir, si ja està escrutinada.",
    "HORA_COMUNICADA_MESA": "Hora a la qual es va comunicar l'acta d'aquesta mesa.",
    "CENS_MESA": "Nombre d'electors censats en aquesta mesa.",
    "AVAN1_MESA": "Vots emesos en aquesta mesa al 1r avanç (checkpoint) de recompte.",
    "AVAN2_MESA": "Vots emesos en aquesta mesa al 2n avanç de recompte.",
    "AVAN3_MESA": "Vots emesos en aquesta mesa al 3r avanç (final) de recompte.",
    "NULS_VOTS_MESA": "Vots nuls en aquesta mesa.",
    "BLANCS_VOTS_MESA": "Vots en blanc en aquesta mesa.",
}

_FIELD_DOCS_PER_DATASET: dict[str, dict[str, str]] = {
    "resultats": {
        **_COMMON_FIELD_DOCS,
        "TOTAL_VOTS_MESA": "Total de vots emesos en aquesta mesa (candidatures + nuls + blancs).",
        "ENTEL_PARTIT": "Ordre d'aparició de la candidatura a la papereta/pantalla de resultats.",
        "COLOR_PARTIT": "Color corporatiu de la candidatura, en hexadecimal — el que fa servir el portal als gràfics.",
        "CODI_PARTIT": "Codi únic de la candidatura, estable entre convocatòries encara que canviï de nom o sigles.",
        "SIGLAS_PARTIT": "Sigles de la candidatura.",
        "NOM_PARTIT": "Nom complet de la candidatura.",
        "VOTS_PARTIT": "Vots obtinguts per aquesta candidatura, en aquesta mesa. Cal sumar-lo agrupant per (CODI_CONVOCATORIA, CODI_PARTIT) per obtenir el total municipal — mai s'ha de llegir un total ja fet, no existeix cap fila d'agregat.",
        "CENS_TOTAL": "Cens electoral de tot el municipi per aquesta convocatòria. Es repeteix igual a totes les files: no s'ha de sumar, només agafar-ne un valor.",
        "AVAN1_TOTAL": "Vots emesos a tot el municipi al 1r avanç. Repetit a totes les files, igual que CENS_TOTAL.",
        "AVAN2_TOTAL": "Vots emesos a tot el municipi al 2n avanç. Repetit a totes les files.",
        "AVAN3_TOTAL": "Vots emesos a tot el municipi al 3r avanç (final) — equival als «vots emesos» de la LOREG. Repetit a totes les files.",
        "TOTAL_NULS_VOTS": "Vots nuls de tot el municipi. Repetit a totes les files.",
        "TOTAL_BLANCS_VOTS": "Vots en blanc de tot el municipi. Repetit a totes les files.",
        "TOTAL_REGIDORS": "Nombre d'escons a repartir en aquesta convocatòria (només Eleccions Municipals). Repetit a totes les files.",
    },
    "cens": {
        **_COMMON_FIELD_DOCS,
        "DISTRICTE": "Districte on vota aquest elector censat.",
        "SECCIO": "Secció censal on vota aquest elector censat.",
        "MESA": "Lletra de la mesa on vota aquest elector censat.",
        "COL_LEGI": "Centre o col·legi electoral on vota aquest elector.",
        "EDAT_CENS_INE": "Edat de l'elector, segons el cens de l'INE.",
        "CODI_INTERVAL_EDAD_INE": "Codi de l'interval d'edat oficial de l'INE al qual pertany l'elector.",
        "INTERVAL_EDAD_INE": "Etiqueta llegible de l'interval d'edat de l'INE (p. ex. «46-55 Anys»).",
        "CONTINENT_NAIXEMENT": "Continent de naixement de l'elector.",
        "CODI_SEXE": "Codi del sexe de l'elector («V»/«M»).",
        "SEXE": "Sexe de l'elector, en text («Home»/«Dona»).",
        "CODI_ESTUDIS": "Codi del nivell d'estudis de l'elector.",
        "ESTUDIS_DESC": "Descripció del nivell d'estudis de l'elector.",
        "DADES": "Marca de temps de quan es va generar aquesta fila del conjunt de dades obert.",
    },
    "mesa": {
        **_COMMON_FIELD_DOCS,
        "CODI_MESA": "Identificador intern numèric de la mesa.",
        "CODI_DISTRICTE_SECCIO_MEDA": "Mateix codi que CODI_DISTRICTE_SECCIO_MESA (variant amb errata de nom a la font original).",
        "TOTALS_VOTS_MESA": "Total de vots emesos en aquesta mesa (candidatures + nuls + blancs) — mateix càlcul que TOTAL_VOTS_MESA a la font de Resultats, amb la «S» de plural.",
    },
}

_DATASET_META = {
    "resultats": {
        "titol": "Resultats electorals",
        "fitxer": "public_eleccions_partits.csv",
        "grup": "una fila = els vots d'UNA candidatura en UNA mesa, per a una convocatòria",
        "descripcio": (
            "Detall de vots per candidatura i mesa electoral, per a cada convocatòria "
            "publicada. És la font més gran i completa de les tres: alimenta "
            "«Resultats electorals», «Estadístiques comparatives» i «Prediccions»."
        ),
        "us": (
            "Per obtenir el total de vots d'una candidatura a tot el municipi, agrupa "
            "per (CODI_CONVOCATORIA, CODI_PARTIT) i suma VOTS_PARTIT — no hi ha cap fila "
            "d'agregat ja feta. En canvi, CENS_TOTAL / AVAN1_TOTAL / AVAN2_TOTAL / "
            "AVAN3_TOTAL / TOTAL_NULS_VOTS / TOTAL_BLANCS_VOTS ja vénen agregats a tot el "
            "municipi i es repeteixen idèntics a totes les files de la convocatòria: "
            "agafa'n un sol valor, mai els sumis. El % oficial de cada candidatura es "
            "calcula sobre els «vots vàlids» (candidatures + blancs, sense els nuls), no "
            "sobre el total de vots emesos."
        ),
        "config_key": "RESULTATS_SOURCE_URL",
        "ttl_config_key": "RESULTATS_CACHE_TTL_SECONDS",
    },
    "cens": {
        "titol": "Cens electoral per mesa",
        "fitxer": "public_eleccions_cens.csv",
        "grup": "una fila = UN elector censat (anonimitzat)",
        "descripcio": (
            "Microdada anonimitzada del cens electoral: una fila per elector censat, "
            "sense cap identificador personal (ni DNI, ni nom) — només la seva ubicació "
            "de vot i variables demogràfiques agregables (edat, sexe, estudis, continent "
            "de naixement). Alimenta l'apartat «Cens electoral»."
        ),
        "us": (
            "No hi ha cap columna amb el total d'electors per mesa: cal comptar files "
            "agrupant per (DISTRICTE, SECCIO, MESA, COL_LEGI). Com que és una fila per "
            "persona, també es pot fer servir per encreuar la participació amb qualsevol "
            "de les variables demogràfiques (edat, sexe, estudis, continent de "
            "naixement) sense arribar mai a identificar ningú."
        ),
        "config_key": "CENS_SOURCE_URL",
        "ttl_config_key": "CENS_MESA_CACHE_TTL_SECONDS",
    },
    "mesa": {
        "titol": "Estat d'escrutini per mesa",
        "fitxer": "public_eleccions_meses.csv",
        "grup": "una fila = l'estat d'UNA mesa, per a una convocatòria",
        "descripcio": (
            "Estat en viu de cada mesa electoral durant l'escrutini: si ja s'ha obert, "
            "si ja ha comunicat la seva acta (està escrutinada) i a quina hora, més els "
            "seus recomptes d'avanç. No porta detall per candidatura — això és a la font "
            "de Resultats. Alimenta l'apartat «Resultats per mesa electoral»."
        ),
        "us": (
            "El «% d'escrutini» oficial (Ministeri de l'Interior / Junta Electoral "
            "Central) es calcula com mesas amb COMUNICADA_MESA=«SI» sobre el total de "
            "mesas — els vots no hi alteren res."
        ),
        "config_key": "MESA_ESTAT_SOURCE_URL",
        "ttl_config_key": "MESA_ESTAT_CACHE_TTL_SECONDS",
        "ttl_note_extra": (
            "Aquest valor és igual que el de les altres dues fonts perquè encara no "
            "existeix una pantalla de seguiment d'escrutini en viu — quan es "
            "implementi, aquest TTL es tornarà a baixar a un valor curt (segons o "
            "minuts) perquè l'estat de cada mesa es vegi gairebé en temps real."
        ),
    },
}


def _format_ttl(seconds: int) -> str:
    """Nombre de segons d'un TTL, en text llegible (la unitat més gran que hi encaixa exacta)."""
    if seconds >= 86400 and seconds % 86400 == 0:
        n = seconds // 86400
        return f"{n} dia" if n == 1 else f"{n} dies"
    if seconds >= 3600 and seconds % 3600 == 0:
        n = seconds // 3600
        return f"{n} hora" if n == 1 else f"{n} hores"
    if seconds >= 60 and seconds % 60 == 0:
        n = seconds // 60
        return f"{n} minut" if n == 1 else f"{n} minuts"
    return f"{seconds} segons"


def build_dataset_view(
    key: str, info: Optional[dict[str, Any]], error: Optional[str], app_config: dict[str, Any],
) -> dict[str, Any]:
    meta = _DATASET_META[key]
    field_docs = _FIELD_DOCS_PER_DATASET[key]
    columns = []
    if info:
        columns = [{**c, "descripcio": c["descripcio"] or field_docs.get(c["nom"], "")} for c in info["columns"]]
    return {
        "key": key,
        "titol": meta["titol"],
        "fitxer": meta["fitxer"],
        "grup": meta["grup"],
        "descripcio": meta["descripcio"],
        "us": meta["us"],
        "url": app_config[meta["config_key"]],
        "ttl_label": _format_ttl(app_config[meta["ttl_config_key"]]),
        "ttl_note_extra": meta.get("ttl_note_extra"),
        "error": error,
        "n_files": info["n_files"] if info else None,
        "n_columnes": info["n_columnes"] if info else None,
        "columns": columns,
    }


TECNOLOGIA = [
    {
        "grup": "Backend",
        "elements": [
            ("Flask", "Framework web Python: enruta les peticions HTTP i renderitza les plantilles amb Jinja2, un blueprint per apartat."),
            ("Cap base de dades", "Aquest portal no en té: totes les dades venen de CSV oberts, llegits per HTTP i tractats com un endpoint REST de només lectura (vegeu app/services/api_clients/)."),
            ("Caché en memòria amb TTL", "Cada font es descarrega un cop i es queda en memòria un temps configurable (5 min per Resultats/Cens, 1 min per l'Estat d'escrutini, perquè aquest canvia en viu) abans de tornar-la a demanar."),
            ("requests + urllib3 Retry", "Client HTTP amb reintents automàtics (errors 429/5xx) i timeout configurable — mai una petició penjada indefinidament."),
            ("pandas", "Parseja cada CSV i fa els agrupaments/sumes (per candidatura, per mesa, per convocatòria) que necessita cada vista."),
            ("ReportLab", "Genera en memòria els PDF exportables de «Resultats electorals» i «Resultats per mesa electoral» — mai es desa cap fitxer al disc."),
        ],
    },
    {
        "grup": "Frontend",
        "elements": [
            ("Jinja2 + HTML semàntic", "Plantilles server-side (sense React/Vue): cada pàgina es renderitza sencera al servidor."),
            ("CSS pur", "Sense frameworks (Bootstrap/Tailwind): un únic full d'estils amb la paleta corporativa de l'Ajuntament de Rubí, gràfics de barres/arc fets amb HTML+CSS/SVG en lloc de canvas."),
            ("JavaScript vanilla", "Petites millores progressives (ordenació de taules, columnes congelades, el widget de xat...) sense cap dependència externa."),
        ],
    },
    {
        "grup": "Assistent IA",
        "elements": [
            ("Groq (openai/gpt-oss-20b)", "Model obert servit per Groq (maquinari LPU, molt ràpid i barat) que respon el xat del portal."),
            ("Digest mensual propi", "El context que rep el model no és tot el CSV: és un resum textual (regenerat com a màxim un cop al mes) de convocatòries/resultats/cens, filtrat per rellevància a la pregunta perquè càpiga dins el límit de tokens/minut del pla gratuït de Groq."),
        ],
    },
]

CALCULS = [
    {
        "nom": "Participació i abstenció",
        "formula": "participació % = (vots emesos ÷ cens electoral) × 100 · abstenció % = 100 − participació %",
        "explicacio": "«Vots emesos» és AVAN3_TOTAL (el recompte final), no la suma dels vots a candidatures.",
    },
    {
        "nom": "Vots vàlids i % de cada candidatura",
        "formula": "vots vàlids = vots a candidatures + vots en blanc (els nuls queden exclosos) · % candidatura = (vots candidatura ÷ vots vàlids) × 100",
        "explicacio": "És el criteri oficial de la LOREG: el vot en blanc rebaixa el % de totes les candidatures, mentre que el vot nul no n'afecta cap.",
    },
    {
        "nom": "Repartiment d'escons (Llei D'Hondt)",
        "formula": "s'exclouen les candidatures amb menys del 5% dels vots vàlids (LOREG art. 180); dels escons restants, cada un es dona a qui tingui el quocient vots ÷ (escons ja obtinguts + 1) més alt",
        "explicacio": "Només es calcula per a Eleccions Municipals i sobre el resultat de tot el municipi (mai amb un filtre de districte/secció/mesa actiu).",
    },
    {
        "nom": "% d'escrutini oficial",
        "formula": "% escrutini = (mesas comunicades ÷ total de mesas) × 100",
        "explicacio": "Mesura mesas amb l'acta ja transmesa, no vots comptats: per això no varia si una mesa gran o petita és la que falta.",
    },
    {
        "nom": "Mapes de calor comparatius",
        "formula": "una cel·la per (candidatura o convocatòria) × (convocatòria o zona), acolorida amb una opacitat proporcional al seu % respecte al màxim de tota la graella",
        "explicacio": "Usat a «Estadístiques comparatives» per comparar visualment l'evolució de la participació, els vots per candidatura i quina candidatura guanya a cada zona.",
    },
    {
        "nom": "Predicció de tendència (mode joc)",
        "formula": "regressió lineal simple sobre l'historial de % de vots vàlids d'una candidatura al llarg de les convocatòries del mateix tipus, extrapolada un punt més enllà",
        "explicacio": "La confiança («alta»/«mitjana»/«baixa») puja quan hi ha més convocatòries i totes es mouen en el mateix sentit. És un joc basat només en la tendència interna de dades oficials passades, no una enquesta ni una predicció professional.",
    },
]
