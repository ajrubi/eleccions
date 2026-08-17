"""Client for the "Cens electoral" data source (aggregated, per mesa).

Today this is a public, anonymized CSV published on GitHub
(public_eleccions_cens.csv): one row per censused elector, with NO
personal identifier (no DNI, no name) — only demographic attributes (age,
sex, studies, birth continent) plus the mesa/districte/secció where each
elector is registered to vote. Because nothing in it is personally
identifying, this data can be aggregated freely, unlike the future
per-elector "cerca per DNI" lookup (see blueprints/cens/routes.py — that
placeholder is untouched and will need its own, far more sensitive, API
with OAuth2/JWT, RBAC and audit logging).

This client stays deliberately thin: it fetches/caches the raw CSV and
hands back the convocatòries available plus the raw per-elector location
rows for one of them. The actual group-and-count aggregation into
per-mesa totals is view-specific business logic and lives in
blueprints/cens/services.py, not here.

Data quirks confirmed against the real dataset before writing this file:
  * There is no CODI_CONVOCATORIA column here (unlike the Resultats CSV):
    NOM_CONVOCATORIA is the only stable identifier for a convocatòria.
  * There is no precomputed per-mesa total: it must be derived by counting
    rows grouped by (DISTRICTE, SECCIO, MESA, COL_LEGI).
  * DISTRICTE/SECCIO are numeric-looking strings, MESA is a letter.
  * Today only one convocatòria exists in the data (Eleccions Municipals
    2023: 56.616 electors across 90 mesa groups), but the convocatòria
    list is always read from the data itself, so it keeps working
    unchanged when more convocatòries get published upstream.
"""
from __future__ import annotations

import io
import logging
import threading
import time
from typing import Any, Optional

import pandas as pd

from .base_client import BaseApiClient

logger = logging.getLogger(__name__)

_LOCATION_COLUMNS = ["DISTRICTE", "SECCIO", "MESA", "COL_LEGI"]


class CensApiClient:
    """Cached access to convocatòries and per-elector mesa-location rows."""

    def __init__(
        self,
        base_url: str,
        csv_path: str,
        ttl_seconds: int = 300,
        timeout: float = 10,
        max_retries: int = 3,
    ):
        self._http = BaseApiClient(base_url=base_url, timeout=timeout, max_retries=max_retries)
        self._csv_path = csv_path
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._cached_df: Optional[pd.DataFrame] = None
        self._cached_at: float = 0.0

    def _fetch_dataframe(self) -> pd.DataFrame:
        raw_csv = self._http.get(self._csv_path, raw=True)
        df = pd.read_csv(io.StringIO(raw_csv), dtype=str)
        df["ANY_CONVOCATORIA"] = pd.to_numeric(df["ANY_CONVOCATORIA"], errors="coerce").fillna(0).astype(int)
        return df

    def _get_dataframe(self, force_refresh: bool = False) -> pd.DataFrame:
        with self._lock:
            is_stale = (time.monotonic() - self._cached_at) > self._ttl_seconds
            if self._cached_df is None or is_stale or force_refresh:
                self._cached_df = self._fetch_dataframe()
                self._cached_at = time.monotonic()
                logger.info("Cens CSV (re)carregat: %d files", len(self._cached_df))
            return self._cached_df

    def get_convocatories(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        df = self._get_dataframe(force_refresh=force_refresh)
        convs = df[["NOM_CONVOCATORIA", "ANY_CONVOCATORIA"]].drop_duplicates()
        convs = convs.sort_values("ANY_CONVOCATORIA", ascending=False)
        return [
            {"nom": row["NOM_CONVOCATORIA"], "any": int(row["ANY_CONVOCATORIA"])}
            for _, row in convs.iterrows()
        ]

    def get_elector_location_rows(self, nom_convocatoria: str, force_refresh: bool = False) -> list[dict[str, str]]:
        """Una fila per elector censat (anonimitzat), només amb la seva
        ubicació de mesa. No es retorna ni s'usa cap altra dada personal.
        """
        df = self._get_dataframe(force_refresh=force_refresh)
        conv_df = df[df["NOM_CONVOCATORIA"] == nom_convocatoria]
        if conv_df.empty:
            raise ValueError(f"No existeix cap convocatòria amb nom {nom_convocatoria!r}")
        return conv_df[_LOCATION_COLUMNS].to_dict("records")
