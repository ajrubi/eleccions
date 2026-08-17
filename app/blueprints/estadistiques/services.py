"""View-specific aggregation for "Estadístiques comparatives".

This module performs no HTTP calls of its own: it only combines calls
already implemented and tested in ResultatsApiClient
(get_convocatories / get_results) and reshapes the result for each
sub-apartat's chart and its accessible data-table fallback:
  * "Participació i abstenció per convocatòria" (build_participacio_abstencio_series)
  * "Participació i abstenció per avanços" (build_participacio_avancos_heatmap)
    — un mapa de calor amb una fila per convocatòria i una columna per
    cada "avanç" (checkpoint de recompte AVAN1/AVAN2/AVAN3), per veure
    com va evolucionar la participació durant la nit electoral i
    comparar-ho entre convocatòries.
  * "Vots per candidatura" (build_vots_candidatura_heatmap) — un mapa de
    calor amb una fila per candidatura i una columna per convocatòria,
    on la intensitat del color representa el % de vots obtinguts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


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
    """Convocatòries d'un tipus donat, de la més antiga a la més recent.

    Ordenar-les així és el que permet llegir totes les comparatives
    d'aquest blueprint com una evolució en el temps, d'esquerra a dreta.
    """
    del_tipus = [c for c in convocatories if c["tipus"] == tipus]
    return sorted(del_tipus, key=lambda c: _parse_data(c["data"]))


def build_participacio_abstencio_series(client, convocatories: list[dict[str, Any]], tipus: str) -> list[dict[str, Any]]:
    ordered = _ordered_convocatories(convocatories, tipus)

    series = []
    for c in ordered:
        results = client.get_results(c["codi"])
        te_dades = results["cens_total"] > 0
        series.append({
            "codi": c["codi"],
            "nom": c["nom"],
            "any": c["any"],
            "data": c["data"],
            "te_dades": te_dades,
            "cens_total": results["cens_total"],
            "participacio_pct": results["participacio_pct"],
            "abstencio_pct": results["abstencio_pct"],
            "participants_total": results["participants_total"],
            "abstencio_total": results["abstencio_total"],
        })
    return series


_HEATMAP_MIN_ALPHA = 0.08
_HEATMAP_MAX_ALPHA = 0.90
_HEATMAP_FALLBACK_RGB = (144, 27, 19)  # corporate dark red (#901b13), same fallback as resultats_client's party color
_AVANCOS_RGB = (218, 41, 28)  # corporate red (#da291c): un únic color, no un per convocatòria
_AVANCOS_CHECKPOINT_LABELS = ("Avanç 1", "Avanç 2", "Avanç 3 (final)")


def build_participacio_avancos_heatmap(client, convocatories: list[dict[str, Any]], tipus: str) -> dict[str, Any]:
    """Participació (%) a cada "avanç" de recompte, per convocatòria.

    Una fila per convocatòria (la més recent primer, igual que
    build_vots_candidatura_heatmap) i una columna per checkpoint
    (Avanç 1/2/3). AVAN1_TOTAL/AVAN2_TOTAL són recomptes parcials fets
    mentre encara durava l'escrutini; AVAN3_TOTAL és el recompte final
    (el mateix que ja fa servir participacio_pct). La intensitat del
    color és sempre el mateix vermell corporatiu (no n'hi ha un per
    convocatòria, com sí passa amb les candidatures).
    """
    ordered = list(reversed(_ordered_convocatories(convocatories, tipus)))

    rows = []
    for c in ordered:
        r = client.get_results(c["codi"])
        cens = r["cens_total"]
        te_dades = cens > 0

        def _pct(avan_total):
            return round((avan_total / cens) * 100, 2) if te_dades else None

        checkpoints = [
            {"label": _AVANCOS_CHECKPOINT_LABELS[0], "vots": r["avan1_total"], "pct": _pct(r["avan1_total"])},
            {"label": _AVANCOS_CHECKPOINT_LABELS[1], "vots": r["avan2_total"], "pct": _pct(r["avan2_total"])},
            {"label": _AVANCOS_CHECKPOINT_LABELS[2], "vots": r["participants_total"], "pct": r["participacio_pct"]},
        ]
        rows.append({
            "codi": c["codi"], "nom": c["nom"], "any": c["any"], "data": c["data"],
            "cens_total": cens, "te_dades": te_dades, "checkpoints": checkpoints,
        })

    max_pct = max(
        (cp["pct"] for row in rows for cp in row["checkpoints"] if cp["pct"] is not None),
        default=0.0,
    )

    r, g, b = _AVANCOS_RGB
    for row in rows:
        for cp in row["checkpoints"]:
            if cp["pct"] is None:
                cp["bg"] = None
            elif max_pct > 0:
                alpha = _HEATMAP_MIN_ALPHA + (cp["pct"] / max_pct) * (_HEATMAP_MAX_ALPHA - _HEATMAP_MIN_ALPHA)
                cp["bg"] = f"rgba({r}, {g}, {b}, {alpha:.2f})"
            else:
                cp["bg"] = f"rgba({r}, {g}, {b}, {_HEATMAP_MIN_ALPHA})"

    return {"rows": rows, "checkpoint_labels": _AVANCOS_CHECKPOINT_LABELS, "max_pct": max_pct}


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = (hex_color or "").lstrip("#")
    if len(hex_color) != 6:
        return _HEATMAP_FALLBACK_RGB
    try:
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return _HEATMAP_FALLBACK_RGB


def build_vots_candidatura_heatmap(client, convocatories: list[dict[str, Any]], tipus: str) -> dict[str, Any]:
    """Mapa de calor de vots (%) per candidatura al llarg de les convocatòries d'un tipus.

    Cada candidatura és una fila i cada convocatòria una columna. Les
    candidatures es comparen per ``codi`` (estable encara que una sigla o
    color canviï d'una convocatòria a l'altra); si una candidatura no es
    va presentar a una convocatòria concreta, la cel·la queda marcada com
    a "no presentada" en lloc de mostrar-hi un 0% enganyós.
    """
    # A diferència de la resta del blueprint, aquesta taula es llegeix per
    # columnes any per any, no com una evolució d'esquerra a dreta: es vol
    # l'any més recent primer.
    ordered = list(reversed(_ordered_convocatories(convocatories, tipus)))
    per_conv_results = [client.get_results(c["codi"]) for c in ordered]

    convocatories_meta = [
        {
            "codi": c["codi"], "nom": c["nom"], "any": c["any"], "data": c["data"],
            "te_dades": bool(r["candidatures"]),
        }
        for c, r in zip(ordered, per_conv_results)
    ]

    n = len(ordered)
    candidatura_index: dict[str, dict[str, Any]] = {}
    for i, results in enumerate(per_conv_results):
        for c in results["candidatures"]:
            # str(...) up front: CODI_PARTIT comes straight from pandas and
            # can be a numpy int64, which would silently fail to match the
            # plain-str codis coming back from the "partit" query args used
            # to filter the table.
            key = str(c["codi"]) if c["codi"] else c["nom"]
            entry = candidatura_index.setdefault(key, {
                "codi": key, "nom": c["nom"], "siglas": c["siglas"], "color": c["color"],
                "cells": [{"vots": 0, "pct": 0.0, "presentat": False} for _ in range(n)],
            })
            # Rebranding entre convocatòries: es queda amb el nom/sigles/color
            # més recents (l'ordre d'iteració és cronològic).
            entry["nom"], entry["siglas"], entry["color"] = c["nom"], c["siglas"], c["color"]
            entry["cells"][i] = {"vots": c["vots"], "pct": c["pct"], "presentat": True}

    # Primer criteri: en quants anys ha tingut presència (més anys primer),
    # no el total de vots — així una candidatura constant al llarg del
    # temps surt per davant d'una que només ha tret molts vots un sol any.
    # Els vots totals només desempaten entre candidatures amb la mateixa
    # presència.
    candidatures = sorted(
        candidatura_index.values(),
        key=lambda e: (
            sum(1 for cell in e["cells"] if cell["presentat"]),
            sum(cell["vots"] for cell in e["cells"]),
        ),
        reverse=True,
    )

    max_pct = max(
        (cell["pct"] for e in candidatures for cell in e["cells"] if cell["presentat"]),
        default=0.0,
    )

    # Colors de fons ja calculats aquí (no al template): cada candidatura
    # té el seu propi color, amb una opacitat proporcional al pct respecte
    # al valor màxim de tota la graella — així la cel·la més votada de
    # qualsevol candidatura es veu igual de "calenta", i es pot comparar
    # visualment la resta. Les cel·les no presentades es deixen sense
    # "bg" perquè el template les pinti de manera neutra.
    for e in candidatures:
        r, g, b = _hex_to_rgb(e["color"])
        for cell in e["cells"]:
            if not cell["presentat"]:
                cell["bg"] = None
            elif max_pct > 0:
                alpha = _HEATMAP_MIN_ALPHA + (cell["pct"] / max_pct) * (_HEATMAP_MAX_ALPHA - _HEATMAP_MIN_ALPHA)
                cell["bg"] = f"rgba({r}, {g}, {b}, {alpha:.2f})"
            else:
                cell["bg"] = f"rgba({r}, {g}, {b}, {_HEATMAP_MIN_ALPHA})"

    return {"convocatories": convocatories_meta, "candidatures": candidatures, "max_pct": max_pct}


def candidatura_options(heatmap: dict[str, Any]) -> list[dict[str, Any]]:
    """Universe de candidatures disponibles per al cercador de filtre.

    Es construeix a partir del heatmap sencer (abans de filtrar), perquè
    l'usuari sempre pugui tornar a afegir una candidatura que hagi tret,
    encara que la vista actual ja estigui filtrada.
    """
    return [
        {"codi": e["codi"], "nom": e["nom"], "siglas": e["siglas"], "color": e["color"]}
        for e in heatmap["candidatures"]
    ]


def split_candidatura_options(
    options: list[dict[str, Any]], selected_codis: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa el universe en (chips ja seleccionats, opcions encara disponibles).

    Cada chip ja seleccionat porta precalculada ``remove_partits``: la
    llista de codis que quedarien si es tragués just aquest — evita haver
    de fer aritmètica de llistes al template per construir l'enllaç de
    treure'l.
    """
    selected_set = set(selected_codis)
    selected_chips = []
    available = []
    for opt in options:
        if opt["codi"] in selected_set:
            selected_chips.append({**opt, "remove_partits": [c for c in selected_codis if c != opt["codi"]]})
        else:
            available.append(opt)
    return selected_chips, available


def filter_heatmap_by_partits(heatmap: dict[str, Any], selected_codis: list[str]) -> dict[str, Any]:
    """Retorna el heatmap només amb les candidatures seleccionades.

    Una selecció buida vol dir "cap filtre encara": es mostren totes.
    """
    if not selected_codis:
        return heatmap
    selected_set = set(selected_codis)
    return {**heatmap, "candidatures": [e for e in heatmap["candidatures"] if e["codi"] in selected_set]}
