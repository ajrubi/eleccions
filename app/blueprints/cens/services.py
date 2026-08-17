"""Aggregation for "Cens electoral per mesa".

Turns the raw, anonymized per-elector location rows already fetched by
cens_client.py into per-mesa totals. Nothing here performs I/O: it only
counts a list that was already fetched, grouping by
(DISTRICTE, SECCIO, MESA, COL_LEGI) since the source data has no
precomputed per-mesa total.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_cens_per_mesa(location_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts: Counter = Counter()
    col_legi_by_mesa: dict[tuple, str] = {}

    for row in location_rows:
        key = (row["DISTRICTE"], row["SECCIO"], row["MESA"])
        counts[key] += 1
        col_legi_by_mesa[key] = row["COL_LEGI"]

    mesa_rows = [
        {
            "districte": districte,
            "seccio": seccio,
            "mesa": mesa,
            "col_legi": col_legi_by_mesa[(districte, seccio, mesa)],
            "cens": total,
        }
        for (districte, seccio, mesa), total in counts.items()
    ]
    mesa_rows.sort(key=lambda r: (_safe_int(r["districte"]), _safe_int(r["seccio"]), r["mesa"]))
    return mesa_rows


def total_cens(mesa_rows: list[dict[str, Any]]) -> int:
    return sum(r["cens"] for r in mesa_rows)
