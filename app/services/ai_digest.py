"""Digest mensual de dades per a l'assistent IA del portal.

Construeix, a partir dels mateixos clients ja existents
(RESULTATS_CLIENT / CENS_CLIENT), un "bloc" de text independent per cada
convocatòria (amb els seus resultats i candidatures) més un bloc-resum de
cens, i deixa triar a select_context() només els blocs rellevants per a
la pregunta de l'usuari — no el digest sencer.

Per què cal seleccionar en lloc d'enviar-ho tot: el pla gratuït de l'API
que fa servir aquest assistent (Groq) limita cada compte a un nombre de
tokens per minut molt petit (8.000 al pla "on_demand" en el moment
d'escriure això — confirmat empíricament: enviar el digest sencer, uns
25.000 tokens, retornava HTTP 413 "tokens per minute exceeded"). Filtrar
per rellevància abans d'enviar la petició és per tant un requisit real
d'aquest proveïdor, no una optimització prematura.

A diferència dels clients de app/services/api_clients/ (TTL de segons o
minuts, perquè les seves dades poden canviar durant una nit electoral),
els blocs es refresquen com a màxim un cop al mes: reconstruir-los és
relativament costós (recorre totes les convocatòries històriques) i les
dades obertes que els nodreixen només es publiquen unes poques vegades
l'any. Mateix patró lock + cached_at que ja fan servir tots els
ApiClient, només amb un TTL molt més llarg.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from typing import Any, Optional

logger = logging.getLogger(__name__)

REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60  # ~1 mes

# Mida per defecte (en caràcters, no tokens) del context que es passa a
# l'assistent per pregunta — vegeu el docstring del mòdul sobre per què
# cal un límit petit. ~12.000 caràcters són ~3.000 tokens, prou marge per
# sota del límit de 8.000 tokens/minut un cop sumats el prompt de
# sistema, l'historial de la conversa i la resposta.
DEFAULT_CONTEXT_MAX_CHARS = 12000

_STOPWORDS = {
    "de", "del", "dels", "la", "les", "el", "els", "i", "per", "a", "al", "als",
    "d", "l", "en", "amb", "un", "una", "uns", "unes", "que", "com", "es", "se",
}


def _normalize(text: Any) -> str:
    # Alguns camps de text del CSV històric (p. ex. NOM_PARTIT en
    # convocatòries molt antigues) poden arribar com a NaN (float de
    # pandas) en lloc d'una cadena buida — es tracten igual que None.
    text = text if isinstance(text, str) else ""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _keywords(*texts: Any) -> set[str]:
    tokens: set[str] = set()
    for text in texts:
        for token in re.split(r"[^a-z0-9]+", _normalize(text)):
            if len(token) > 2 and token not in _STOPWORDS:
                tokens.add(token)
    return tokens


class KnowledgeDigestBuilder:
    """Genera i cacheja els blocs de dades que l'assistent IA fa servir."""

    def __init__(self, resultats_client, cens_client):
        self._resultats = resultats_client
        self._cens = cens_client
        self._lock = threading.Lock()
        self._cached_blocks: Optional[list[dict[str, Any]]] = None
        self._cached_at: float = 0.0

    def get_blocks(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            is_stale = (time.monotonic() - self._cached_at) > REFRESH_TTL_SECONDS
            if self._cached_blocks is None or is_stale or force_refresh:
                self._cached_blocks = self._build_blocks()
                self._cached_at = time.monotonic()
                logger.info("Blocs de dades per a l'assistent IA (re)generats: %d", len(self._cached_blocks))
            return self._cached_blocks

    def select_context(self, question: str, max_chars: int = DEFAULT_CONTEXT_MAX_CHARS) -> str:
        """Tria els blocs més rellevants per a `question`, dins de `max_chars`.

        Si cap bloc de convocatòria coincideix amb cap paraula de la
        pregunta (una pregunta genèrica, p. ex. "com funciona el vot?"),
        es cau a mostrar les convocatòries més recents en lloc de no
        mostrar-ne cap — sempre és millor una resposta parcialment
        fonamentada que cap dada de context.
        """
        blocks = self.get_blocks()
        summary_blocks = [b for b in blocks if b["is_summary"]]
        data_blocks = [b for b in blocks if not b["is_summary"]]

        question_tokens = _keywords(question)

        def score(block: dict[str, Any]) -> int:
            return len(block["keywords"] & question_tokens)

        ranked = sorted(data_blocks, key=lambda b: (score(b), b["any"] or 0), reverse=True)
        has_match = bool(ranked) and score(ranked[0]) > 0
        candidates = [b for b in ranked if score(b) > 0] if has_match else sorted(
            data_blocks, key=lambda b: b["any"] or 0, reverse=True,
        )

        selected = [b["text"] for b in summary_blocks]
        total = sum(len(t) for t in selected)
        for block in candidates:
            if total + len(block["text"]) > max_chars:
                continue
            selected.append(block["text"])
            total += len(block["text"])

        return "\n\n".join(selected)

    def _build_blocks(self) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []

        try:
            convocatories = self._resultats.get_convocatories(force_refresh=True)
        except Exception as exc:  # noqa: BLE001 — un digest parcial és millor que cap
            logger.warning("No s'ha pogut generar el bloc de resultats del digest: %s", exc)
            convocatories = []

        for c in convocatories:
            try:
                r = self._resultats.get_results(c["codi"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("No s'han pogut llegir els resultats de %s: %s", c["codi"], exc)
                continue

            regidors_txt = f" {r['total_regidors']} regidors a repartir." if r.get("total_regidors") else ""
            lines = [
                f"{r['nom']} (tipus: {r['tipus']}, any {r['any']}, data {r['data']}): "
                f"cens {r['cens_total']}, participació {r['participacio_pct']}%, "
                f"abstenció {r['abstencio_pct']}%, vots nuls {r['vots_nuls']}, "
                f"vots en blanc {r['vots_blancs']}, vots vàlids {r['vots_valids']}.{regidors_txt}"
            ]
            keywords = _keywords(r["nom"], r["tipus"], str(r["any"]))
            if r["candidatures"]:
                for cand in r["candidatures"]:
                    nom = cand["nom"] if isinstance(cand["nom"], str) else "(sense nom)"
                    lines.append(f"  · {cand['siglas'] or nom} ({nom}): {cand['vots']} vots ({cand['pct']}%)")
                    keywords |= _keywords(cand["siglas"], nom)
            else:
                lines.append("  · Sense dades de candidatures per a aquesta convocatòria.")

            blocks.append({
                "text": "\n".join(lines), "keywords": keywords, "any": r["any"], "is_summary": False,
            })

        cens_lines = ["Cens electoral (agregat i anonimitzat, sense dades personals identificables):"]
        try:
            cens_convocatories = self._cens.get_convocatories(force_refresh=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("No s'ha pogut generar el bloc de cens del digest: %s", exc)
            cens_convocatories = []

        if not cens_convocatories:
            cens_lines.append("- Sense dades de cens disponibles.")
        for cc in cens_convocatories:
            try:
                rows = self._cens.get_elector_location_rows(cc["nom"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("No s'ha pogut llegir el cens de %s: %s", cc["nom"], exc)
                continue
            cens_lines.append(f"- {cc['nom']} ({cc['any']}): {len(rows)} electors censats en total.")

        blocks.append({"text": "\n".join(cens_lines), "keywords": set(), "any": None, "is_summary": True})

        return blocks
