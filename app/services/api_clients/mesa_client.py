"""Client for the "Estat d'escrutini per mesa" data source.

Different CSV than resultats_client.py (public_eleccions_meses.csv, not
public_eleccions_partits.csv), fetched the same way: a public, read-only
CSV on GitHub, treated as a REST endpoint via BaseApiClient.get(), cached
in memory for a short TTL. It shares CODI_CONVOCATORIA values with the
Resultats source but does not carry per-candidatura votes — only each
mesa's live status (OBERTA_MESA/COMUNICADA_MESA/HORA_COMUNICADA_MESA) and
its own vote-count checkpoints (AVAN1/2/3, nuls, blancs, total).

Data quirks confirmed against the real dataset:
  * OBERTA_MESA / COMUNICADA_MESA are text "SI"/"NO" (not booleans).
    COMUNICADA_MESA == "SI" is what marks a mesa as already escrutinada;
    anything else means it's still pendent.
  * TOTALS_VOTS_MESA (note the plural, unlike TOTAL_VOTS_MESA in the
    Resultats CSV) already equals vots a candidatures + nuls + blancs,
    same relationship documented in resultats_client.py for AVAN3_TOTAL.
  * These values legitimately change while the scrutiny is in progress —
    that's the whole point of this source — so callers should keep the
    cache TTL short (see MESA_ESTAT_CACHE_TTL_SECONDS) rather than relying
    on force_refresh alone.

Official "% escrutini" (Ministeri de l'Interior / Junta Electoral Central)
is *not* vote-based at all: it's mesas amb l'acta ja transmesa (comunicada)
sobre el total de mesas — vots a partits, nuls o blancs no hi alteren res.
Per això aquest client no calcula cap "% escrutat" per mesa individual
(seria sempre 0% o 100%, redundant amb `comunicada`): l'agregat
comunicades/total viu a blueprints/mesa/services.py::build_summary.
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

_NUMERIC_COLUMNS = [
    "ANY_CONVOCATORIA", "CENS_MESA", "AVAN1_MESA", "AVAN2_MESA", "AVAN3_MESA",
    "NULS_VOTS_MESA", "BLANCS_VOTS_MESA", "TOTALS_VOTS_MESA",
]


class MesaEstatApiClient:
    """Cached access to l'estat d'escrutini (obertura/comunicació) per mesa."""

    def __init__(
        self,
        base_url: str,
        csv_path: str,
        ttl_seconds: int = 60,
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
        df = pd.read_csv(io.StringIO(raw_csv))
        for col in _NUMERIC_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df

    def _get_dataframe(self, force_refresh: bool = False) -> pd.DataFrame:
        with self._lock:
            is_stale = (time.monotonic() - self._cached_at) > self._ttl_seconds
            if self._cached_df is None or is_stale or force_refresh:
                self._cached_df = self._fetch_dataframe()
                self._cached_at = time.monotonic()
                logger.info("Meses CSV (re)carregat: %d files", len(self._cached_df))
            return self._cached_df

    @staticmethod
    def _clean_text(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _zone_sort_key(value: Any) -> tuple[int, str]:
        text = str(value)
        try:
            return (0, f"{int(text):09d}")
        except ValueError:
            return (1, text)

    def get_convocatories(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        df = self._get_dataframe(force_refresh=force_refresh)
        cols = ["CODI_CONVOCATORIA", "NOM_CONVOCATORIA", "ANY_CONVOCATORIA", "DATA_CONVOCATORIA", "TIPUS_CONVOCATORIA"]
        convs = df[cols].drop_duplicates(subset=["CODI_CONVOCATORIA"]).copy()
        convs["_ordre"] = pd.to_datetime(convs["DATA_CONVOCATORIA"], format="%d/%m/%Y", errors="coerce")
        convs = convs.sort_values("_ordre", ascending=False, na_position="last")

        result = []
        for _, row in convs.iterrows():
            any_conv = row["ANY_CONVOCATORIA"]
            result.append({
                "codi": row["CODI_CONVOCATORIA"],
                "nom": row["NOM_CONVOCATORIA"],
                "any": int(any_conv) if pd.notna(any_conv) else None,
                "data": row["DATA_CONVOCATORIA"],
                "tipus": row["TIPUS_CONVOCATORIA"],
            })
        return result

    def get_mesa_status(self, codi_convocatoria: str, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Estat d'escrutini de cada mesa per a una convocatòria.

        Una fila del CSV = una mesa (no cal cap agregació): només es
        neteja/formata cada camp per a la vista.
        """
        df = self._get_dataframe(force_refresh=force_refresh)
        conv_df = df[df["CODI_CONVOCATORIA"] == codi_convocatoria]
        if conv_df.empty:
            raise ValueError(f"No existeix cap convocatòria amb codi {codi_convocatoria!r}")

        result = []
        for _, row in conv_df.iterrows():
            cens = float(row["CENS_MESA"])
            totals_vots = float(row["TOTALS_VOTS_MESA"])
            nuls = float(row["NULS_VOTS_MESA"])
            blancs = float(row["BLANCS_VOTS_MESA"])
            vots_partits = max(totals_vots - nuls - blancs, 0.0)

            oberta_text = self._clean_text(row["OBERTA_MESA"]).upper()
            comunicada_text = self._clean_text(row["COMUNICADA_MESA"]).upper()
            hora_comunicada = self._clean_text(row["HORA_COMUNICADA_MESA"]) or None

            result.append({
                "codi_mesa": row["CODI_MESA"],
                "districte": str(row["DISTRICTE_MESA"]),
                "seccio": str(row["SECCIO_MESA"]),
                "mesa": str(row["MESA"]),
                "oberta": oberta_text == "SI",
                "oberta_text": oberta_text or "N/D",
                "comunicada": comunicada_text == "SI",
                "comunicada_text": comunicada_text or "N/D",
                "hora_comunicada": hora_comunicada,
                "cens_mesa": int(cens),
                "avan1_mesa": int(row["AVAN1_MESA"]),
                "avan2_mesa": int(row["AVAN2_MESA"]),
                "avan3_mesa": int(row["AVAN3_MESA"]),
                "nuls_mesa": int(nuls),
                "blancs_mesa": int(blancs),
                "vots_partits_mesa": int(vots_partits),
                "totals_vots_mesa": int(totals_vots),
            })

        result.sort(key=lambda r: (
            self._zone_sort_key(r["districte"]), self._zone_sort_key(r["seccio"]), self._zone_sort_key(r["mesa"]),
        ))
        return result
