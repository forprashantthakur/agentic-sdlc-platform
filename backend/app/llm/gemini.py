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
from app.core import progress
from app.llm.mock import mock_json, mock_text


def _report_retry(state) -> None:
    """Backing off is honest work — say so, on the timeline, where the user is actually looking.

    Defined above the classes on purpose: it is referenced inside a @retry decorator, which is
    evaluated when the class body is executed, not when the method is called.
    """
    wait = f"{state.next_action.sleep:.0f}s" if state.next_action else "?"
    err = str(state.outcome.exception())[:100] if state.outcome else ""
    log.warning("llm.retry", attempt=state.attempt_number, sleeping=wait, error=err)
    progress.emit(
        f"Model unavailable — backing off {wait} and retrying "
        f"(attempt {state.attempt_number} of 5). {err}",
        level="warning",
    )


class TruncatedResponse(RuntimeError):
    """The model ran out of output budget mid-answer. Retrying with a smaller ask may help."""


class TransientError(RuntimeError):
    """Gemini is overloaded or rate-limiting us. Wait and try again — the request itself is fine.

    This class exists because the distinction matters enormously and the API does not make it for
    you. A 503 UNAVAILABLE ("high demand, try again later") and a 429 with `limit: 0` ("this model
    is paid-only on your key") arrive looking similar and mean opposite things. One resolves itself
    if you wait four seconds; the other never will, however long you wait. Retrying the second is a
    waste of a minute; NOT retrying the first throws away an entire six-agent run because Google had
    a busy moment.
    """


# The hard ceiling on a single generation. Beyond this the problem is the ask, not the budget.
MAX_BUDGET = 65536

PERMANENT = ("limit: 0", "NOT_FOUND", "no longer available", "API key not valid",
             "PERMISSION_DENIED", "billing")
TRANSIENT = ("UNAVAILABLE", "503", "overloaded", "high demand", "500", "INTERNAL",
             "DEADLINE_EXCEEDED", "504")


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
        model: str | None = None, temperature: float = 0.2, thinking: int | None = None,
        project_id: str = "", agent: str | None = None,
    ) -> dict[str, Any]:
        """Constrained generation. Returns a dict conforming to `schema`.

        Routed through the fallback chain: a transient failure moves to the next model IMMEDIATELY
        rather than sleeping on a sick one. And an exact-hash cache short-circuits a genuinely
        identical request — a replay after a mid-pipeline failure, or Agent 4's repeated system
        prompt — without ever serving one project's answer to another (the evidence is in the prompt,
        and the prompt is in the key).
        """
        if not self.live:
            return mock_json(task=task, prompt=prompt, schema=schema)

        from app.llm.cache import response_cache
        from app.llm.fallback import Candidate, execute

        primary = Candidate("gemini", model or settings.gemini_model)
        ck = response_cache.key(project_id=project_id, model=primary.model, system=system,
                                prompt=prompt, schema=schema)
        if settings.llm_cache_enabled and (hit := response_cache.get(ck)) is not None:
            return hit

        def call(c: Candidate):
            if c.provider == "anthropic":
                from app.llm.router import provider

                return provider("anthropic").generate_json(
                    system=system, prompt=prompt, schema=schema, task=task,
                    model=c.model, temperature=temperature,
                )
            raw = self._call_escalating(
                model=c.model, system=system, prompt=prompt, temperature=temperature,
                json_schema=schema, task=task,
                thinking=settings.gemini_thinking_budget if thinking is None else thinking,
            )
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                log.error("gemini.bad_json", task=task, head=raw[:400], length=len(raw))
                raise

        out = execute(primary=primary, call=call, is_transient=_transient, task=task, agent=agent)
        if settings.llm_cache_enabled:
            response_cache.put(ck, out)
        return out

    def generate_text(
        self, *, system: str, prompt: str, task: str, model: str | None = None,
        temperature: float = 0.3,
    ) -> str:
        if not self.live:
            return mock_text(task=task, prompt=prompt)
        return self._call_escalating(
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
    def _call_escalating(self, **kw) -> str:
        """Truncation is a different failure from overload, and needs a different response.

        Overload: wait, then repeat the identical request — it will work.
        Truncation: waiting changes nothing. Come back with a bigger budget, or admit it will
        never fit.
        """
        for attempt in range(1, 5):
            try:
                return self._call(attempt=attempt, **kw)
            except TruncatedResponse as e:
                if attempt == 4:
                    raise
                progress.emit(str(e), level="warning")
                log.warning("gemini.truncated", attempt=attempt, task=kw.get("task"))
        raise RuntimeError("unreachable")

    @retry(
        # Five attempts with a real backoff: Gemini's overload spikes are usually seconds, not
        # minutes, and a six-agent run is far too expensive to abandon over one of them.
        stop=stop_after_attempt(2),
        # `attempt` is threaded through so the call can escalate its own token budget on truncation.
        wait=wait_exponential(multiplier=2, min=4, max=45),
        # TruncatedResponse is NOT retried here — _call_escalating handles it, because a retry that
        # changes nothing is not a retry.
        #
        # TransientError is NOT retried here EITHER, and that is the whole point. It used to be, with
        # five attempts and exponential backoff — which meant a 503 slept for ~30s on a model we
        # already knew was sick, while a HEALTHY model sat one line down in the fallback chain,
        # unused. Two retry layers, and the dumb one ran first. Transient failures now propagate
        # straight up to fallback.execute(), which switches model in ~1ms and only ever backs off
        # once EVERY candidate has failed.
        retry=retry_if_exception_type((json.JSONDecodeError,)),
        before_sleep=_report_retry,
        reraise=True,
    )
    def _call(
        self, *, model: str, system: str, prompt: str, temperature: float, task: str,
        json_schema: dict | None = None, attempt: int = 1, thinking: int | None = None,
    ) -> str:
        from google.genai import types

        # Escalate the output budget on each truncation. Retrying an identical request that ran out
        # of room will run out of room again, in exactly the same place, five times over. A retry
        # that changes nothing is not a retry; it is a stutter, and it wastes a minute proving what
        # the first attempt already proved.
        budget = min(settings.max_output_tokens * (2 ** (attempt - 1)), MAX_BUDGET)
        if attempt > 1:
            log.info("gemini.budget_escalated", task=task, attempt=attempt, max_output_tokens=budget)

        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=budget,
        )

        # Thinking is where the seconds go. -1 leaves the model's default alone; 0 turns it off.
        if thinking is not None and thinking >= 0:
            try:
                cfg.thinking_config = types.ThinkingConfig(thinking_budget=thinking)
            except Exception as e:      # older SDKs, or a model that does not support it
                log.info("gemini.thinking_unsupported", error=str(e)[:80])
        if json_schema is not None:
            # `response_json_schema` — NOT `response_schema`. The latter coerces a dict and
            # quietly drops constraints it cannot map.
            cfg.response_mime_type = "application/json"
            cfg.response_json_schema = json_schema

        try:
            resp = self._client.models.generate_content(model=model, contents=prompt, config=cfg)
        except Exception as e:
            msg = str(e)

            # Transient FIRST — but only if it is not one of the permanent conditions. A 429 can be
            # either ("slow down" vs "you have no quota for this model, ever"), and getting that
            # wrong in either direction is expensive.
            if any(t in msg for t in TRANSIENT) and not any(p in msg for p in PERMANENT):
                raise TransientError(
                    f"{task}: Gemini is overloaded ({model}). Backing off and retrying."
                ) from e
            # "limit: 0" is not "you ran out" — it is "this model has no free-tier quota on this
            # project at all". Those are completely different problems and the raw error does a
            # poor job of saying so.
            # A retired model is a 404, not a quota error, and the message is easy to miss inside a
            # provider stack trace. Name the fix in the error itself.
            if "NOT_FOUND" in msg or "404" in msg or "no longer available" in msg:
                raise RuntimeError(
                    f"{task}: the model '{model}' is not available to this API key "
                    "(retired, or never enabled). Model names churn — call "
                    "GET /api/integrations/llm/models to see exactly what this key CAN call, then "
                    "set GEMINI_MODEL to one of them."
                ) from e
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                if "limit: 0" not in msg:
                    # A real rate limit: requests-per-minute, not a hard entitlement. Worth waiting for.
                    raise TransientError(
                        f"{task}: rate limited on '{model}'. Backing off. "
                        "Agent 4 fires six generations at once — if this repeats, that is why."
                    ) from e
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
            if budget >= MAX_BUDGET:
                # We have doubled to the ceiling and it still does not fit. Retrying further is
                # theatre — say what is actually wrong.
                raise RuntimeError(
                    f"{task}: the output does not fit even at {MAX_BUDGET:,} tokens. This is not a "
                    "budget problem — the generation is too large. Reduce the number of sources, or "
                    "split the document."
                )
            raise TruncatedResponse(
                f"{task}: output truncated at {budget:,} tokens. Retrying with {min(budget * 2, MAX_BUDGET):,}."
            )
        if finish_name in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
            raise RuntimeError(f"{task}: Gemini blocked the response (finish_reason={finish_name}).")

        text = resp.text or ""
        if not text.strip():
            raise RuntimeError(f"{task}: Gemini returned an empty response (finish_reason={finish_name}).")

        usage = getattr(resp, "usage_metadata", None)
        if usage:
            from app.core.metrics import metrics  # noqa: PLC0415

            metrics.record(
                agent=None, model=model, stage="tokens", ms=0.0,
                tokens_in=getattr(usage, "prompt_token_count", 0) or 0,
                tokens_out=getattr(usage, "candidates_token_count", 0) or 0,
            )
            log.info("gemini.usage", task=task, model=model,
                     prompt_tokens=getattr(usage, "prompt_token_count", None),
                     output_tokens=getattr(usage, "candidates_token_count", None),
                     thoughts=getattr(usage, "thoughts_token_count", None))
        return text

    def list_models(self) -> dict[str, Any]:
        """What this key can actually call. Ends the guessing.

        Model names churn fast — 2.5 was retired for new keys, and even `gemini-3-pro` now redirects
        to a 3.1 preview. Hard-coding a name means breaking again at the next rename. Asking the API
        is the only answer that stays true.
        """
        if not self.live:
            return {"live": False, "note": "MOCK_MODE is on or no credential is set."}

        try:
            models = list(self._client.models.list())
        except Exception as e:
            return {"live": True, "error": f"{type(e).__name__}: {e}"}

        def usable(m, action: str) -> bool:
            return action in (getattr(m, "supported_actions", None) or [])

        gen = sorted(
            (m.name.replace("models/", "") for m in models if usable(m, "generateContent")),
        )
        emb = sorted(
            (m.name.replace("models/", "") for m in models if usable(m, "embedContent")),
        )
        return {
            "live": True,
            "configured": {
                "GEMINI_MODEL": settings.gemini_model,
                "GEMINI_FLASH_MODEL": settings.gemini_flash_model,
                "GEMINI_EMBED_MODEL": settings.gemini_embed_model,
            },
            "configured_model_is_available": settings.gemini_model in gen,
            "configured_embed_is_available": settings.gemini_embed_model in emb,
            "generation_models": gen,
            "embedding_models": emb,
            "hint": "Set GEMINI_MODEL to one of generation_models and GEMINI_EMBED_MODEL to one of "
                    "embedding_models. Both must appear in these lists — if a model is not here, "
                    "your key cannot call it, whatever the docs say.",
        }

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


def _transient(e: Exception) -> bool:
    """Transient => try the next model at once. Permanent => stop, and name the fix.

    A 429 is BOTH, depending on its body: "quota exceeded, retry in 40s" is transient; "limit: 0" is
    an entitlement, and no amount of waiting or failing over will conjure one.
    """
    if isinstance(e, TransientError):
        return True
    msg = str(e)
    if any(pm in msg for pm in PERMANENT):
        return False
    return any(t in msg for t in TRANSIENT) or isinstance(e, (ConnectionError, TimeoutError))


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

