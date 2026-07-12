"""Single choke-point for every Gemini 2.5 call.

Three backends, one interface:
  * AI Studio (GOOGLE_API_KEY)        — fast path for dev and POC
  * Vertex AI (USE_VERTEX + project)  — the enterprise path: VPC-SC, CMEK, asia-south1 residency,
                                        audit logging
  * Mock                              — deterministic, offline, zero-cost

Everything the agents need is structured output, so `generate_json` is the primary entry point:
the JSON Schema is enforced at the decoding layer via `response_json_schema`, not begged for in
the prompt. An agent physically cannot emit a requirement without an id, a priority and a
source_evidence array.

Two details that only bite in the live path, both handled here:

1. `response_json_schema` is the parameter for a raw JSON Schema dict. `response_schema` expects
   a Pydantic model or a genai `Schema`; it *will* coerce a dict, but the coercion silently drops
   constraints it doesn't understand. We pass the schema where the SDK actually validates it.

2. A truncated response is still a 200. If Gemini hits max_output_tokens mid-object, you get
   valid-looking JSON that won't parse — or worse, parses with half the requirements missing.
   We check `finish_reason` and raise, rather than committing a silently truncated BRD.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import log
from app.llm.mock import mock_json, mock_text


class TruncatedResponse(RuntimeError):
    """The model ran out of output budget mid-answer. Retrying with a smaller ask may help."""


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
                log.info("gemini.init", backend="vertex", location=settings.vertex_location,
                         model=settings.gemini_model)
            else:
                self._client = genai.Client(api_key=settings.google_api_key)
                log.info("gemini.init", backend="ai-studio", model=settings.gemini_model)
        else:
            log.warning("gemini.init", backend="mock", reason="MOCK_MODE or no credentials")

    # ── public API ────────────────────────────────────────────────────────────
    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], task: str,
        model: str | None = None, temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Constrained generation. Returns a dict conforming to `schema`."""
        if not self.live:
            return mock_json(task=task, prompt=prompt, schema=schema)

        raw = self._call(
            model=model or settings.gemini_model,
            system=system, prompt=prompt, temperature=temperature,
            json_schema=schema, task=task,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.error("gemini.bad_json", task=task, head=raw[:400], length=len(raw))
            raise

    def generate_text(
        self, *, system: str, prompt: str, task: str, model: str | None = None,
        temperature: float = 0.3,
    ) -> str:
        if not self.live:
            return mock_text(task=task, prompt=prompt)
        return self._call(
            model=model or settings.gemini_flash_model,
            system=system, prompt=prompt, temperature=temperature, task=task,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.live:
            return [_hash_embedding(t, settings.embed_dim) for t in texts]

        from google.genai import types

        # gemini-embedding-001 returns 3072 dims by default. Our pgvector column is VECTOR(768),
        # fixed when the table was created, so we ask for 768 explicitly (Matryoshka truncation).
        # Google's guidance: anything below the native 3072 should be re-normalised afterwards —
        # truncation breaks unit length, and cosine similarity on non-unit vectors quietly skews.
        resp = self._client.models.embed_content(
            model=settings.gemini_embed_model,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.embed_dim,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        vectors = [_normalise(list(e.values)) for e in resp.embeddings]

        # The pgvector column is VECTOR(embed_dim), fixed at table creation. A model swap that
        # changes dimensionality would fail deep inside an INSERT with an opaque error — so check
        # it here, once, where the message can actually say what went wrong.
        if vectors and len(vectors[0]) != settings.embed_dim:
            raise RuntimeError(
                f"Embedding dimension mismatch: {settings.gemini_embed_model} returned "
                f"{len(vectors[0])} dims, but the vector store is built for {settings.embed_dim}. "
                "Set EMBED_DIM to match and re-index, or keep the previous embedding model."
            )
        return vectors

    # ── internals ─────────────────────────────────────────────────────────────
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=20),
        retry=retry_if_exception_type((TruncatedResponse, json.JSONDecodeError, ConnectionError)),
        reraise=True,
    )
    def _call(
        self, *, model: str, system: str, prompt: str, temperature: float, task: str,
        json_schema: dict | None = None,
    ) -> str:
        from google.genai import types

        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=settings.max_output_tokens,
        )
        if json_schema is not None:
            # `response_json_schema` — NOT `response_schema`. The latter coerces a dict and
            # quietly drops constraints it cannot map.
            cfg.response_mime_type = "application/json"
            cfg.response_json_schema = json_schema

        try:
            resp = self._client.models.generate_content(model=model, contents=prompt, config=cfg)
        except Exception as e:
            msg = str(e)
            # "limit: 0" is not "you ran out" — it is "this model has no free-tier quota on this
            # project at all". Those are completely different problems and the raw error does a
            # poor job of saying so.
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                if "limit: 0" in msg:
                    raise RuntimeError(
                        f"{task}: '{model}' has NO free-tier quota on this API key (limit: 0). "
                        "This is not a rate limit you can wait out. Either enable billing on the "
                        "Google Cloud project behind the key, or set GEMINI_MODEL=gemini-2.5-flash, "
                        "which does have a free tier."
                    ) from e
                raise RuntimeError(
                    f"{task}: rate limited on '{model}'. Free-tier Gemini 2.5 Pro is roughly 5 RPM / "
                    "100 requests per day — a full six-agent run makes ~10 calls, and Agent 4 fires "
                    "six of them concurrently. Slow the run down or enable billing."
                ) from e
            raise

        # A blocked or truncated response is still an HTTP 200. Fail loudly.
        candidate = (resp.candidates or [None])[0]
        finish = getattr(candidate, "finish_reason", None)
        finish_name = getattr(finish, "name", str(finish or ""))

        if finish_name == "MAX_TOKENS":
            raise TruncatedResponse(
                f"{task}: Gemini hit max_output_tokens ({settings.max_output_tokens}). The document "
                "was cut off mid-object. Raise MAX_OUTPUT_TOKENS or split the generation."
            )
        if finish_name in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
            raise RuntimeError(f"{task}: Gemini blocked the response (finish_reason={finish_name}).")

        text = resp.text or ""
        if not text.strip():
            raise RuntimeError(f"{task}: Gemini returned an empty response (finish_reason={finish_name}).")

        usage = getattr(resp, "usage_metadata", None)
        if usage:
            log.info("gemini.usage", task=task, model=model,
                     prompt_tokens=getattr(usage, "prompt_token_count", None),
                     output_tokens=getattr(usage, "candidates_token_count", None),
                     thoughts=getattr(usage, "thoughts_token_count", None))
        return text

    def selftest(self) -> dict[str, Any]:
        """Prove the live path end to end: structured output + embeddings, in one small call.

        Worth its weight the first time you add a key — a failure here costs a second, whereas
        the same failure discovered inside Agent 4 costs a full run and a confusing traceback.
        """
        if not self.live:
            return {"live": False, "backend": "mock", "model": self.model_name,
                    "note": "MOCK_MODE is on or no credential is set. Nothing was called."}

        schema = {
            "type": "object",
            "properties": {
                "capital": {"type": "string"},
                "confidence": {"type": "number"},
                "regulator": {"type": "string"},
            },
            "required": ["capital", "confidence", "regulator"],
        }
        result: dict[str, Any] = {"live": True, "backend": "vertex" if settings.use_vertex else "ai-studio",
                                  "model": settings.gemini_model}
        try:
            out = self.generate_json(
                system="You are a precise assistant. Answer only from general knowledge.",
                prompt="Which city is India's financial capital, and which body regulates its banks?",
                schema=schema, task="selftest", temperature=0.0,
            )
            result["structured_output"] = {"ok": True, "response": out}
        except Exception as e:
            result["structured_output"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

        try:
            vec = self.embed(["UPI AutoPay mandate"])
            result["embeddings"] = {"ok": True, "model": settings.gemini_embed_model, "dims": len(vec[0])}
        except Exception as e:
            result["embeddings"] = {
                "ok": False,
                "model": settings.gemini_embed_model,
                "error": f"{type(e).__name__}: {e}",
                "hint": "If this is a 404, the embedding model name is wrong for the current API "
                        "version. Set GEMINI_EMBED_MODEL=gemini-embedding-001.",
            }

        result["ready"] = bool(
            result.get("structured_output", {}).get("ok") and result.get("embeddings", {}).get("ok")
        )
        return result

    @property
    def model_name(self) -> str:
        if not self.live:
            return "mock/deterministic"
        return f"{'vertex' if settings.use_vertex else 'aistudio'}:{settings.gemini_model}"


def _normalise(vec: list[float]) -> list[float]:
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


def _hash_embedding(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding for offline mode.

    Not semantically meaningful, but stable and unit-norm — so retrieval code paths, cosine maths
    and top-k ranking are all genuinely exercised in mock mode.
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


def reset_client() -> None:
    """Drop the cached client — used after a config change so a key swap takes effect."""
    global _client
    _client = None
