"""Predicció de tendència de vot per a "Prediccions" (mode joc).

Cap crida HTTP pròpia: reutilitza el mateix ResultatsApiClient
(get_convocatories / get_results) que ja fan servir "Resultats electorals"
i "Estadístiques comparatives". Aquest mòdul només:
  * calcula, per a un tipus de convocatòria, l'univers de candidatures que
    s'hi han presentat alguna vegada, per omplir el selector de partits
    (partit_options);
  * a partir del seu historial de % de vots vàlids convocatòria a
    convocatòria, prediu si el proper % pujarà, baixarà o es mantindrà,
    per regressió lineal simple (build_predictions / _predict_trend).

Font de dades externa (intenció de vot): NO integrada en aquesta primera
versió — la predicció es basa únicament en la tendència interna (resultats
oficials de convocatòries anteriors del mateix tipus). Si en el futur cal
afegir-hi una font externa (p. ex. baròmetres del CEO o del CIS), el lloc
natural és un client nou a app/services/api_clients/ (seguint el mateix
patró que ResultatsApiClient/MesaEstatApiClient), injectat aquí com a
paràmetre opcional de build_predictions() perquè _predict_trend el pugui
fer servir per ajustar la predicció sense que aquest mòdul li hagi de fer
mai una crida HTTP directa.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

# Per sota d'aquest marge (en punts percentuals) la predicció es considera
# "estable" en lloc de pujada/baixada — evita etiquetar com a "tendència"
# un soroll d'unes dècimes que no vol dir res.
_FLAT_THRESHOLD_PCT = 0.3


def unique_tipus(convocatories: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for c in convocatories:
        if c["tipus"] not in seen:
            seen.append(c["tipus"])
    return seen


def _parse_data(data_str: Any) -> datetime:
    try:
        return datetime.strptime(data_str, "%d/%m/%Y")
    except (ValueError, TypeError):
        return datetime.min


def _ordered_convocatories(convocatories: list[dict[str, Any]], tipus: str) -> list[dict[str, Any]]:
    """Convocatòries d'un tipus donat, de la més antiga a la més recent."""
    del_tipus = [c for c in convocatories if c["tipus"] == tipus]
    return sorted(del_tipus, key=lambda c: _parse_data(c["data"]))


def _partit_key(candidatura: dict[str, Any]) -> str:
    # Mateix criteri que a estadistiques/services.py: CODI_PARTIT ve de
    # pandas i pot ser un numpy int64, així que es normalitza a str per
    # poder-lo comparar amb els codis de text que arriben per query string.
    return str(candidatura["codi"]) if candidatura["codi"] else candidatura["nom"]


def partit_options(client, convocatories: list[dict[str, Any]], tipus: str) -> list[dict[str, Any]]:
    """Univers de candidatures presentades a convocatòries d'aquest tipus.

    Per omplir el selector de partits del "joc": s'hi inclou qualsevol
    candidatura que s'hagi presentat alguna vegada a aquest tipus, amb el
    nom/sigles/color de la seva aparició més recent (per si ha canviat de
    marca entre convocatòries).
    """
    ordered = _ordered_convocatories(convocatories, tipus)
    seen: dict[str, dict[str, Any]] = {}
    for c in ordered:
        try:
            results = client.get_results(c["codi"])
        except ValueError:
            continue
        for cand in results["candidatures"]:
            key = _partit_key(cand)
            entry = seen.setdefault(key, {"codi": key})
            entry["nom"], entry["siglas"], entry["color"] = cand["nom"], cand["siglas"], cand["color"]
    return sorted(seen.values(), key=lambda e: (e["siglas"] or e["nom"]).lower())


def _predict_trend(pcts: list[float]) -> Optional[dict[str, Any]]:
    """Prediu el % de la propera convocatòria per regressió lineal simple.

    `pcts` ha de venir en ordre cronològic (més antiga primer) i només amb
    les convocatòries on la candidatura es va presentar — els buits
    (anys sense presentar-s'hi) no compten com a "baixada a 0%".

    Amb un sol punt no hi ha tendència possible: es retorna el mateix %
    com a predicció, direcció "estable" i confiança "sense_prou_dades".
    Amb dos o més punts es fa una regressió lineal (mínims quadrats) sobre
    l'índex de convocatòria i s'extrapola un punt més enllà. La confiança
    puja quan hi ha més convocatòries I totes es mouen en el mateix sentit
    (una sèrie que puja i baixa alternativament és molt menys fiable
    d'extrapolar que una que sempre ha pujat).
    """
    n = len(pcts)
    if n == 0:
        return None
    if n == 1:
        return {
            "predicted_pct": pcts[0], "last_pct": pcts[0], "delta": 0.0,
            "direction": "estable", "confidence": "sense_prou_dades", "n_convocatories": 1,
        }

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(pcts) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, pcts))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den else 0.0
    intercept = mean_y - slope * mean_x
    predicted_next = max(0.0, round(slope * n + intercept, 2))

    last = pcts[-1]
    delta = round(predicted_next - last, 2)

    deltas = [pcts[i + 1] - pcts[i] for i in range(n - 1)]
    consistent = all(d >= 0 for d in deltas) or all(d <= 0 for d in deltas)
    if n >= 4 and consistent:
        confidence = "alta"
    elif n >= 3 and consistent:
        confidence = "mitjana"
    else:
        confidence = "baixa"

    if abs(delta) < _FLAT_THRESHOLD_PCT:
        direction = "estable"
    elif delta > 0:
        direction = "puja"
    else:
        direction = "baixa"

    return {
        "predicted_pct": predicted_next, "last_pct": last, "delta": delta,
        "direction": direction, "confidence": confidence, "n_convocatories": n,
    }


def build_predictions(
    client, convocatories: list[dict[str, Any]], tipus: str, selected_codis: list[str],
) -> list[dict[str, Any]]:
    """Predicció de tendència per a cada candidatura seleccionada.

    Recorre totes les convocatòries del tipus (més antiga a més recent) una
    sola vegada per construir l'historial de % de cada partit seleccionat,
    i després hi aplica _predict_trend(). Els partits seleccionats sense
    cap aparició històrica (per exemple, un codi vell que ja no existeix)
    surten amb `history` buit i `trend` None — el template els mostra com a
    "sense dades" en lloc de fer-los desaparèixer en silenci.
    """
    ordered = _ordered_convocatories(convocatories, tipus)
    selected_set = set(selected_codis)

    meta_per_partit: dict[str, dict[str, Any]] = {}
    history_per_partit: dict[str, list[dict[str, Any]]] = {codi: [] for codi in selected_codis}

    for c in ordered:
        try:
            results = client.get_results(c["codi"])
        except ValueError:
            continue
        for cand in results["candidatures"]:
            key = _partit_key(cand)
            if key not in selected_set:
                continue
            meta_per_partit[key] = {"nom": cand["nom"], "siglas": cand["siglas"], "color": cand["color"]}
            history_per_partit[key].append({
                "codi_convocatoria": c["codi"], "nom_convocatoria": c["nom"],
                "any": c["any"], "data": c["data"], "pct": cand["pct"], "vots": cand["vots"],
            })

    predictions = []
    for codi in selected_codis:
        history = history_per_partit.get(codi, [])
        meta = meta_per_partit.get(codi, {"nom": codi, "siglas": "", "color": None})
        trend = _predict_trend([h["pct"] for h in history])
        predictions.append({"codi": codi, **meta, "history": history, "trend": trend})
    return predictions
