"""Single choke-point for every Gemini 2.5 call.

Two backends, one interface:
  * AI Studio  (GOOGLE_API_KEY)          -> fast path for dev / POC
  * Vertex AI  (USE_VERTEX + project)    -> the enterprise path: VPC-SC, CMEK,
                                            data residency in asia-south1, audit logs
  * Mock                                 -> deterministic, offline, zero-cost

Everything the agents need is structured output, so `generate_json` is the primary
entry point: we pass a JSON Schema and let Gemini's `response_schema` do the
constraining rather than praying over a prompt.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import log
from app.llm.mock import mock_json, mock_text


class GeminiClient:
    def __init__(self) -> None:
        self._client = None
        self.live = settings.live_llm
        if self.live:
            from google import genai  # imported lazily so mock mode needs no creds

            if settings.use_vertex:
                self._client = genai.Client(
                    vertexai=True,
                    project=settings.vertex_project,
                    location=settings.vertex_location,
                )
                log.info("gemini.init", backend="vertex", location=settings.vertex_location)
            else:
                self._client = genai.Client(api_key=settings.google_api_key)
                log.info("gemini.init", backend="ai-studio")
        else:
            log.warning("gemini.init", backend="mock", reason="MOCK_MODE or no credentials")

    # ── public API ────────────────────────────────────────────────────────────
    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        task: str,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Constrained generation. Returns a dict that conforms to `schema`."""
        if not self.live:
            return mock_json(task=task, prompt=prompt, schema=schema)

        model = model or settings.gemini_model
        raw = self._call(
            model=model,
            system=system,
            prompt=prompt,
            temperature=temperature,
            response_schema=schema,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.error("gemini.bad_json", task=task, raw=raw[:400])
            raise

    def generate_text(
        self, *, system: str, prompt: str, task: str, model: str | None = None,
        temperature: float = 0.3,
    ) -> str:
        if not self.live:
            return mock_text(task=task, prompt=prompt)
        return self._call(
            model=model or settings.gemini_flash_model,
            system=system,
            prompt=prompt,
            temperature=temperature,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.live:
            return [_hash_embedding(t, settings.embed_dim) for t in texts]
        resp = self._client.models.embed_content(
            model=settings.gemini_embed_model, contents=texts
        )
        return [list(e.values) for e in resp.embeddings]

    # ── internals ─────────────────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=12), reraise=True)
    def _call(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        temperature: float,
        response_schema: dict | None = None,
    ) -> str:
        from google.genai import types

        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=32768,
            safety_settings=[],
        )
        if response_schema is not None:
            cfg.response_mime_type = "application/json"
            cfg.response_schema = response_schema

        resp = self._client.models.generate_content(
            model=model, contents=prompt, config=cfg
        )
        return resp.text or ""

    @property
    def model_name(self) -> str:
        if not self.live:
            return "mock/deterministic"
        return f"{'vertex' if settings.use_vertex else 'aistudio'}:{settings.gemini_model}"


def _hash_embedding(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding for offline mode.

    Not semantically meaningful, but stable and unit-norm, so retrieval code paths,
    cosine math and top-k ranking are all exercised for real in mock mode.
    """
    vec: list[float] = []
    seed = text.lower().encode()
    counter = 0
    while len(vec) < dim:
        h = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        vec.extend((b - 127.5) / 127.5 for b in h)
        counter += 1
    vec = vec[:dim]
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


_client: GeminiClient | None = None


def gemini() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
