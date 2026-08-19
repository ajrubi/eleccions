"""Reflecteix l'esquema (columnes, tipus, comptatges) d'un DataFrame ja cachejat.

Usat per l'apartat "Dades" (blueprints/dades) per descriure, en temps real,
els tres CSV que consumeix aquest portal (resultats_client.py, cens_client.py,
mesa_client.py). Deliberadament genèric i sense estat propi: no torna a fer
cap crida HTTP ni guarda res — només inspecciona el DataFrame que cada client
ja té en memòria, així la llista de camps mai es queda desactualitzada si el
CSV d'origen guanya o perd una columna (a diferència d'una llista de camps
escrita a mà).
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

_DTYPE_LABELS = {
    "int64": "Numèric (enter)",
    "float64": "Numèric (decimal)",
    "bool": "Booleà",
    "object": "Text",
}


def _friendly_dtype(dtype: Any) -> str:
    return _DTYPE_LABELS.get(str(dtype), str(dtype))


def describe_dataframe(df: pd.DataFrame, field_docs: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """Esquema descriptiu d'un DataFrame: nombre de files i, per columna,
    el seu tipus, quants valors no nuls/únics té i (si es proporciona) una
    descripció humana del seu contingut."""
    field_docs = field_docs or {}
    columns = [
        {
            "nom": col,
            "tipus": _friendly_dtype(df[col].dtype),
            "no_nuls": int(df[col].notna().sum()),
            "valors_unics": int(df[col].nunique(dropna=True)),
            "descripcio": field_docs.get(col, ""),
        }
        for col in df.columns
    ]
    return {"n_files": len(df), "n_columnes": len(df.columns), "columns": columns}
