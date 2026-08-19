"""Client for the Groq chat-completions API (esquema compatible amb OpenAI).

Usat només per l'assistent IA del portal (services/ai_chat_client.py).
Groq serveix models Llama de codi obert sobre maquinari LPU propi —
molt més ràpid i barat que un model gran de propòsit general, suficient
per respondre preguntes factuals sobre un conjunt de dades acotat com el
d'aquest portal.

Igual que la resta de fonts d'aquest projecte, es parla amb l'API a
través de BaseApiClient — cap sessió HTTP ni gestió d'errors pròpia aquí,
només la crida POST i el Bearer token, que és exactament el que
BaseApiClient ja sap fer (vegeu el paràmetre `auth_token`).
"""
from __future__ import annotations

from typing import Any

from .base_client import ApiClientError, BaseApiClient

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqApiClient:
    """Cached-free wrapper: cada crida és una petició de xat independent."""

    def __init__(self, api_key: str, timeout: float = 30, max_retries: int = 2):
        self._http = BaseApiClient(base_url=GROQ_BASE_URL, timeout=timeout, max_retries=max_retries, auth_token=api_key)

    def chat_completion(
        self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float,
    ) -> str:
        data = self._http.post("chat/completions", json_body={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiClientError("Resposta inesperada de l'API de Groq") from exc
