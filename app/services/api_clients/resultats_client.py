"""Client for the "Resultats electorals" data source.

Today this is a public, read-only CSV published on GitHub
(public_eleccions_partits.csv). It is treated exactly like a read-only
REST endpoint: it's fetched with BaseApiClient.get() over HTTP, never read
from a local file, and cached in memory for a short TTL so the upstream
source isn't hit on every request. The day this becomes a real REST API,
only ``_fetch_dataframe`` needs to change.

Data quirks confirmed against the real dataset before writing this file
(see conversation validation step):
  * CENS_TOTAL / AVAN1_TOTAL / AVAN2_TOTAL / AVAN3_TOTAL / TOTAL_NULS_VOTS /
    TOTAL_BLANCS_VOTS are repeated on every row of a convocatòria: take the
    first row's value, never sum them. AVAN1/AVAN2 are earlier "avanç"
    (in-progress count) checkpoints of the same convocatòria, used by
    estadistiques/services.py::build_participacio_avancos_heatmap to show
    how participació evolved during the count — AVAN3_TOTAL is the final,
    complete count (same value already used for participacio_pct).
  * VOTS_PARTIT must be summed grouping by (CODI_CONVOCATORIA, NOM_PARTIT)
    because each party has one row per mesa.
  * AVAN3_TOTAL (participants, "vots emesos" a la LOREG) = vots a
    candidatures + vots blancs + vots nuls. Verified on AU2024: 29728
    candidatura votes + 298 blank + 216 null = 30242 = AVAN3_TOTAL exactly.
  * Some convocatòries (e.g. Senat) can have every total at 0 — division
    by zero must degrade to "N/D", never raise or show garbage.
  * COLOR_PARTIT is usually a hex string but can come back empty.

"% de cada partit" segons la LOREG: NO es calcula sobre AVAN3_TOTAL (vots
emesos) ni sobre els vots a candidatures tots sols, sinó sobre els "vots
vàlids" = vots a candidatures + vots en blanc (els nuls hi queden
exclosos). Per això el vot en blanc abaixa el % de tots els partits i el
vot nul no els afecta gens. Vegeu get_results() — `vots_candidatures` i
`vots_valids` són camps diferents; no confondre'ls.
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

FALLBACK_PARTY_COLOR = "#901b13"  # corporate dark red (Pantone 485 C, tint fosc), used when COLOR_PARTIT is empty

_NUMERIC_COLUMNS = [
    "CENS_MESA", "AVAN1_MESA", "AVAN2_MESA", "AVAN3_MESA",
    "NULS_VOTS_MESA", "BLANCS_VOTS_MESA", "TOTAL_VOTS_MESA",
    "VOTS_PARTIT", "CENS_TOTAL", "AVAN1_TOTAL", "AVAN2_TOTAL",
    "AVAN3_TOTAL", "TOTAL_NULS_VOTS", "TOTAL_BLANCS_VOTS", "TOTAL_REGIDORS",
]


class ResultatsApiClient:
    """High-level, cached access to convocatòries i resultats electorals."""

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

    # ---- low level: talks to the "API" (HTTP GET) -----------------------
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
                logger.info("Resultats CSV (re)carregat: %d files", len(self._cached_df))
            return self._cached_df

    @staticmethod
    def _clean_color(value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return FALLBACK_PARTY_COLOR

    @staticmethod
    def _clean_text(value: Any) -> str:
        return value if isinstance(value, str) else ""

    # ---- high level: what the blueprints actually call ------------------
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

    def get_results(
        self,
        codi_convocatoria: str,
        force_refresh: bool = False,
        districte: Optional[str] = None,
        seccio: Optional[str] = None,
        mesa: Optional[str] = None,
    ) -> dict[str, Any]:
        df = self._get_dataframe(force_refresh=force_refresh)
        conv_df = df[df["CODI_CONVOCATORIA"] == codi_convocatoria]
        if conv_df.empty:
            raise ValueError(f"No existeix cap convocatòria amb codi {codi_convocatoria!r}")

        if districte:
            conv_df = conv_df[conv_df["DISTRICTE_MESA"].astype(str) == str(districte)]
        if seccio:
            conv_df = conv_df[conv_df["SECCIO_MESA"].astype(str) == str(seccio)]
        if mesa:
            conv_df = conv_df[conv_df["MESA"].astype(str) == str(mesa)]
        if conv_df.empty:
            raise ValueError("No hi ha dades per a la zona seleccionada (districte/secció/mesa)")

        first = conv_df.iloc[0]
        is_filtered = bool(districte or seccio or mesa)
        if is_filtered:
            # CENS_TOTAL / AVAN3_TOTAL / etc. are city-wide totals repeated on
            # every row (see module docstring) so they can't be reused once
            # we've narrowed conv_df down to a districte/secció: instead sum
            # the per-mesa fields across the (deduplicated) mesas still left.
            mesa_totals = conv_df.drop_duplicates(subset=["CODI_DISTRICTE_SECCIO_MESA"])
            cens_total = float(mesa_totals["CENS_MESA"].sum())
            avan1_total = float(mesa_totals["AVAN1_MESA"].sum())
            avan2_total = float(mesa_totals["AVAN2_MESA"].sum())
            avan3_total = float(mesa_totals["AVAN3_MESA"].sum())
            total_nuls = float(mesa_totals["NULS_VOTS_MESA"].sum())
            total_blancs = float(mesa_totals["BLANCS_VOTS_MESA"].sum())
        else:
            cens_total = float(first["CENS_TOTAL"])
            avan1_total = float(first["AVAN1_TOTAL"])
            avan2_total = float(first["AVAN2_TOTAL"])
            avan3_total = float(first["AVAN3_TOTAL"])
            total_nuls = float(first["TOTAL_NULS_VOTS"])
            total_blancs = float(first["TOTAL_BLANCS_VOTS"])
        # Vots a candidatures: només partits, sense blancs ni nuls.
        vots_candidatures = max(avan3_total - total_blancs - total_nuls, 0.0)
        # "Vots vàlids" segons la LOREG (vegeu el docstring del mòdul): vots a
        # candidatures + vots en blanc — els nuls hi queden exclosos, però els
        # blancs sí compten. És el denominador oficial per calcular el % de
        # cada partit, NO el total de vots emesos ni només els vots a
        # candidatures (per això el vot en blanc abaixa el % dels partits i
        # el vot nul no els afecta).
        vots_valids = vots_candidatures + total_blancs

        if cens_total > 0:
            participacio_pct = round((avan3_total / cens_total) * 100, 2)
            abstencio_pct = round(100 - participacio_pct, 2)
            abstencio_total = int(cens_total - avan3_total)
        else:
            participacio_pct = None
            abstencio_pct = None
            abstencio_total = None

        per_partit = (
            conv_df.groupby(["NOM_PARTIT", "SIGLAS_PARTIT", "CODI_PARTIT", "COLOR_PARTIT"], dropna=False)["VOTS_PARTIT"]
            .sum()
            .reset_index()
            .sort_values("VOTS_PARTIT", ascending=False)
        )

        # TOTAL_REGIDORS ve al CSV com el nombre d'escons que cada partit ja
        # va obtenir oficialment, repetit (com CENS_TOTAL) a totes les seves
        # files: la mida del ple municipal és una xifra fixada per llei
        # (segons cens de població, LOREG art. 179), no un resultat del
        # recompte. Per això aquí només se'n suma el valor — un cop per
        # partit — per saber QUANTS escons cal repartir; el REPARTIMENT en
        # si el calcula `services.dhondt_regidors` a partir dels vots.
        total_regidors = int(conv_df.drop_duplicates(subset=["CODI_PARTIT"])["TOTAL_REGIDORS"].sum())

        candidatures = []
        for _, row in per_partit.iterrows():
            vots = float(row["VOTS_PARTIT"])
            pct = round((vots / vots_valids * 100), 2) if vots_valids > 0 else 0.0
            candidatures.append({
                "nom": row["NOM_PARTIT"],
                "siglas": self._clean_text(row["SIGLAS_PARTIT"]),
                "codi": row["CODI_PARTIT"],
                "color": self._clean_color(row["COLOR_PARTIT"]),
                "vots": int(vots),
                "pct": pct,
            })

        return {
            "codi": codi_convocatoria,
            "nom": first["NOM_CONVOCATORIA"],
            "any": int(first["ANY_CONVOCATORIA"]) if pd.notna(first["ANY_CONVOCATORIA"]) else None,
            "data": first["DATA_CONVOCATORIA"],
            "tipus": first["TIPUS_CONVOCATORIA"],
            "cens_total": int(cens_total),
            "avan1_total": int(avan1_total),
            "avan2_total": int(avan2_total),
            "participants_total": int(avan3_total),
            "participacio_pct": participacio_pct,
            "abstencio_pct": abstencio_pct,
            "abstencio_total": abstencio_total,
            "vots_nuls": int(total_nuls),
            "vots_blancs": int(total_blancs),
            "vots_candidatures": int(vots_candidatures),
            "vots_valids": int(vots_valids),
            "candidatures": candidatures,
            "total_regidors": total_regidors,
            "districte": str(districte) if districte else None,
            "seccio": str(seccio) if seccio else None,
            "mesa": str(mesa) if mesa else None,
        }

    @staticmethod
    def _zone_sort_key(value: Any) -> tuple[int, str]:
        text = str(value)
        try:
            return (0, f"{int(text):09d}")
        except ValueError:
            return (1, text)

    def get_zones(self, codi_convocatoria: str, force_refresh: bool = False) -> list[dict[str, str]]:
        """Combinacions (districte, secció, mesa) amb dades per a aquesta convocatòria.

        Usat només per omplir els desplegables de filtre a la vista; els
        valors es retornen com a text perquè viatgen tal qual a la query
        string i es comparen com a text a ``get_results``.
        """
        df = self._get_dataframe(force_refresh=force_refresh)
        conv_df = df[df["CODI_CONVOCATORIA"] == codi_convocatoria]
        combos = conv_df[["DISTRICTE_MESA", "SECCIO_MESA", "MESA"]].drop_duplicates()

        result = [
            {
                "districte": str(row["DISTRICTE_MESA"]),
                "seccio": str(row["SECCIO_MESA"]),
                "mesa": str(row["MESA"]),
            }
            for _, row in combos.iterrows()
        ]
        result.sort(key=lambda r: (
            self._zone_sort_key(r["districte"]), self._zone_sort_key(r["seccio"]), self._zone_sort_key(r["mesa"]),
        ))
        return result

    def get_mesa_results(self, codi_convocatoria: str, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Detall de vots per candidatura, mesa a mesa.

        Usat pel blueprint `mesa` (Resultats per mesa electoral) per afegir,
        a la taula d'estat d'escrutini, una columna de vots per cada partit
        (vegeu blueprints/mesa/services.py::merge_partit_vots). `districte`/
        `seccio`/`mesa` es retornen com a text — igual que a get_results() i
        get_zones() — perquè aquell mòdul les pugui creuar amb les de
        mesa_client.py sense sorpreses de tipus (int64 de pandas vs str).
        """
        df = self._get_dataframe(force_refresh=force_refresh)
        conv_df = df[df["CODI_CONVOCATORIA"] == codi_convocatoria]
        if conv_df.empty:
            raise ValueError(f"No existeix cap convocatòria amb codi {codi_convocatoria!r}")

        mesa_cols = [
            "CODI_DISTRICTE_SECCIO_MESA", "DISTRICTE_MESA", "SECCIO_MESA", "MESA",
            "CENS_MESA", "AVAN3_MESA", "NULS_VOTS_MESA", "BLANCS_VOTS_MESA", "TOTAL_VOTS_MESA",
        ]
        mesas = conv_df[mesa_cols].drop_duplicates(subset=["CODI_DISTRICTE_SECCIO_MESA"])

        result = []
        for _, mesa_row in mesas.iterrows():
            mesa_df = conv_df[conv_df["CODI_DISTRICTE_SECCIO_MESA"] == mesa_row["CODI_DISTRICTE_SECCIO_MESA"]]
            per_partit = (
                mesa_df.groupby(["NOM_PARTIT", "SIGLAS_PARTIT", "CODI_PARTIT", "COLOR_PARTIT"], dropna=False)["VOTS_PARTIT"]
                .sum()
                .reset_index()
                .sort_values("VOTS_PARTIT", ascending=False)
            )
            result.append({
                "codi_mesa": mesa_row["CODI_DISTRICTE_SECCIO_MESA"],
                "districte": str(mesa_row["DISTRICTE_MESA"]),
                "seccio": str(mesa_row["SECCIO_MESA"]),
                "mesa": str(mesa_row["MESA"]),
                "cens_mesa": int(mesa_row["CENS_MESA"]),
                "participants_mesa": int(mesa_row["AVAN3_MESA"]),
                "nuls_mesa": int(mesa_row["NULS_VOTS_MESA"]),
                "blancs_mesa": int(mesa_row["BLANCS_VOTS_MESA"]),
                "candidatures": [
                    {
                        "nom": r["NOM_PARTIT"],
                        "siglas": self._clean_text(r["SIGLAS_PARTIT"]),
                        "codi": r["CODI_PARTIT"],
                        "color": self._clean_color(r["COLOR_PARTIT"]),
                        "vots": int(r["VOTS_PARTIT"]),
                    }
                    for _, r in per_partit.iterrows()
                ],
            })
        return result
