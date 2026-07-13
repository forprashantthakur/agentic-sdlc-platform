"""Claude, via the Anthropic API.

Structured output is enforced with **forced tool use**, not by asking nicely. The agent's JSON
Schema becomes a tool's `input_schema`, and `tool_choice` compels the model to call it. The model
cannot answer in prose, cannot omit a required field, and cannot invent one — the same structural
guarantee Gemini gives through constrained decoding, arrived at differently.

That symmetry is the whole reason the swap is safe. If Claude's structured output were merely a
prompt convention, moving Agent 1 onto it would quietly remove the guardrail that stops a
requirement being emitted without a citation, and nobody would notice until a BRD had a fabricated
requirement in it.
"""

from __future__ import annotations

import json
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import log
from app.llm.mock import mock_json, mock_text

TRANSIENT = ("overloaded_error", "rate_limit_error", "api_error", "529", "503", "500", "timeout")
PERMANENT = ("authentication_error", "permission_error", "not_found_error", "invalid_request_error")

TOOL_NAME = "emit_structured_output"


class TransientError(RuntimeError):
    """Anthropic is overloaded or throttling. Wait and retry — the request itself is fine."""


class AnthropicProvider:
    def __init__(self) -> None:
        self.live = bool(settings.anthropic_api_key) and not settings.is_mocked("llm")
        self._client = None
        if self.live:
            import anthropic

            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            log.info("anthropic.init", model=settings.anthropic_model)
        else:
            log.warning("anthropic.init", backend="mock",
                        reason="MOCK_MODE or no ANTHROPIC_API_KEY")

    # ── public API ────────────────────────────────────────────────────────────
    def generate_json(self, *, system, prompt, schema, task, model=None, temperature=0.2):
        if not self.live:
            return mock_json(task=task, prompt=prompt, schema=schema)

        msg = self._call(
            model=model or settings.anthropic_model,
            system=system, prompt=prompt, temperature=temperature, task=task,
            tool={
                "name": TOOL_NAME,
                "description": "Emit the result. You MUST call this tool. Do not answer in prose.",
                "input_schema": _to_anthropic_schema(schema),
            },
        )

        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                return dict(block.input)

        # Forced tool use should make this unreachable. If it happens, the schema was rejected —
        # and returning prose that looks like an answer would be far worse than failing here.
        raise RuntimeError(
            f"{task}: Claude did not call the structured-output tool. "
            f"stop_reason={getattr(msg, 'stop_reason', '?')}. The schema was probably rejected."
        )

    def generate_text(self, *, system, prompt, task, model=None, temperature=0.3):
        if not self.live:
            return mock_text(task=task, prompt=prompt)
        msg = self._call(
            model=model or settings.anthropic_fast_model,
            system=system, prompt=prompt, temperature=temperature, task=task,
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")

    # ── internals ─────────────────────────────────────────────────────────────
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=45),
        retry=retry_if_exception_type((TransientError, ConnectionError)),
        before_sleep=lambda st: log.warning(
            "anthropic.retry", attempt=st.attempt_number,
            error=str(st.outcome.exception())[:120] if st.outcome else ""),
        reraise=True,
    )
    def _call(self, *, model, system, prompt, temperature, task, tool=None):
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": settings.max_output_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if tool:
            kwargs["tools"] = [tool]
            kwargs["tool_choice"] = {"type": "tool", "name": TOOL_NAME}   # not a suggestion

        try:
            msg = self._client.messages.create(**kwargs)
        except Exception as e:
            m = str(e)
            if any(t in m for t in TRANSIENT) and not any(p in m for p in PERMANENT):
                raise TransientError(f"{task}: Anthropic is overloaded ({model}). Backing off.") from e
            if "not_found_error" in m or "404" in m:
                raise RuntimeError(
                    f"{task}: model '{model}' is not available to this API key. "
                    "Check ANTHROPIC_MODEL against your account's model list."
                ) from e
            if "authentication_error" in m or "401" in m:
                raise RuntimeError(f"{task}: ANTHROPIC_API_KEY is invalid or missing.") from e
            raise

        if getattr(msg, "stop_reason", None) == "max_tokens":
            raise RuntimeError(
                f"{task}: Claude hit max_tokens ({settings.max_output_tokens}) and the output is "
                "truncated. Raise MAX_OUTPUT_TOKENS or split the generation — committing a truncated "
                "BRD is worse than failing."
            )

        u = getattr(msg, "usage", None)
        if u:
            log.info("anthropic.usage", task=task, model=model,
                     input_tokens=getattr(u, "input_tokens", None),
                     output_tokens=getattr(u, "output_tokens", None))
        return msg

    @property
    def model_name(self) -> str:
        return "mock/deterministic" if not self.live else f"anthropic:{settings.anthropic_model}"

    def selftest(self) -> dict[str, Any]:
        if not self.live:
            return {"live": False, "provider": "anthropic", "model": self.model_name,
                    "note": "MOCK_MODE is on or ANTHROPIC_API_KEY is unset. Nothing was called."}
        schema = {
            "type": "object",
            "properties": {"capital": {"type": "string"}, "regulator": {"type": "string"},
                           "confidence": {"type": "number"}},
            "required": ["capital", "regulator", "confidence"],
        }
        out: dict[str, Any] = {"live": True, "provider": "anthropic",
                               "model": settings.anthropic_model}
        try:
            out["structured_output"] = {
                "ok": True,
                "response": self.generate_json(
                    system="You are precise. Answer from general knowledge.",
                    prompt="Which city is India's financial capital, and which body regulates its banks?",
                    schema=schema, task="selftest", temperature=0.0),
            }
        except Exception as e:
            out["structured_output"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        out["ready"] = bool(out.get("structured_output", {}).get("ok"))
        out["note"] = ("Embeddings are NOT provided by Anthropic. Retrieval stays on Gemini — "
                       "GEMINI_API_KEY is still required even when Claude does the reasoning.")
        return out


def _to_anthropic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Our schemas are already JSON Schema, which is what `input_schema` wants.

    One nuance: Anthropic is stricter about the top level. It must be an object with `properties`.
    Every schema in agents/schemas.py already is — this asserts it rather than discovering it in
    production.
    """
    if schema.get("type") != "object" or "properties" not in schema:
        raise ValueError("Anthropic tool schemas must be an object with properties at the top level.")
    return schema
