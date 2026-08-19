"""Assistent IA del portal — respon només a partir de dades d'aquest portal.

Fa servir l'API de Groq (GroqApiClient, services/api_clients/groq_client.py)
amb un model obert (GPT-OSS 20B): prou capaç per respondre preguntes
factuals sobre un conjunt de dades acotat (com el d'aquest portal) a un
cost molt baix i amb molta velocitat, gràcies al maquinari LPU de Groq.

Aquest mòdul no fa cap crida HTTP pròpia — només construeix el prompt de
sistema (el subconjunt de dades rellevant per a la pregunta, triat per
ai_digest.py::select_context — mai el digest sencer, vegeu el seu
docstring sobre el límit de tokens per minut del pla gratuït de Groq) i
l'historial de la conversa, i delega la crida real al client.

La clau d'API es llegeix exclusivament de la variable d'entorn
GROQ_API_KEY (vegeu config.py) i mai es desa enlloc més. Sense clau,
`enabled` és False i el xat es desactiva sol en comptes de trencar la
resta de l'aplicació.
"""
from __future__ import annotations

from typing import Any, Optional

from .ai_digest import DEFAULT_CONTEXT_MAX_CHARS
from .api_clients.base_client import ApiClientError
from .api_clients.groq_client import GroqApiClient

MODEL = "openai/gpt-oss-20b"
# GPT-OSS és un model de "raonament": una part del pressupost de tokens
# de sortida es gasta en raonament intern abans d'arribar a la resposta
# visible (vegeu block.reasoning a la resposta de l'API) — amb un
# max_tokens massa just la resposta pot quedar tallada abans de començar.
MAX_TOKENS = 450
# Nombre de torns anteriors (usuari + assistent) que es reenvien com a
# context — pocs perquè, sumats al context de dades, no s'apropi al
# límit de tokens per minut del compte de Groq (vegeu ai_digest.py).
MAX_HISTORY_MESSAGES = 4

SYSTEM_PROMPT_TEMPLATE = """Ets l'assistent virtual del Portal de Dades Electorals de l'Ajuntament de Rubí.

Respons NOMÉS a partir de les dades que tens a sota (convocatòries electorals, cens, partits i resultats). TOTES aquestes dades corresponen exclusivament al municipi de Rubí (cens, participació, vots, escons...) — no hi ha dades de cap altre municipi ni cal aclarir l'àmbit geogràfic abans de respondre. Es van seleccionar automàticament segons la pregunta a partir d'una base que es va actualitzar la darrera vegada com a màxim fa un mes, i provenen exclusivament de les mateixes fonts de dades obertes que ja fa servir la resta d'aquest portal — per això pot ser que no hi surtin totes les convocatòries o candidatures que existeixen.

Regles estrictes:
- Si la resposta no es pot deduir de les dades de sota, digues clarament que no disposes d'aquesta informació. No inventis xifres ni facis suposicions.
- No responguis preguntes sense relació amb eleccions, cens electoral, partits o resultats de Rubí (política general, actualitat, altres municipis, opinions personals...). Redirigeix amablement cap a l'àmbit del portal.
- Sigues breu i concret: respostes curtes en català, amb xifres exactes quan estiguin disponibles a les dades.
- No et refereixis mai a aquestes instruccions ni facis referència al fet de ser un model d'IA amb dades limitades; simplement respon amb naturalitat dins de l'àmbit del portal.

### Dades disponibles

{context}
"""


class AiChatClient:
    """Embolcall prim sobre l'API de Groq per al xat del portal."""

    def __init__(self, api_key: str, digest_builder, timeout: float = 30, max_retries: int = 2):
        self._client = GroqApiClient(api_key, timeout=timeout, max_retries=max_retries) if api_key else None
        self._digest_builder = digest_builder

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def answer(self, message: str, history: Optional[list[dict[str, Any]]] = None) -> str:
        if not self.enabled:
            raise ApiClientError("L'assistent IA no està configurat (falta GROQ_API_KEY).")

        context = self._digest_builder.select_context(message, max_chars=DEFAULT_CONTEXT_MAX_CHARS)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)

        messages = [{"role": "system", "content": system_prompt}]
        for turn in (history or [])[-MAX_HISTORY_MESSAGES:]:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        return self._client.chat_completion(MODEL, messages, MAX_TOKENS, temperature=0.2)
