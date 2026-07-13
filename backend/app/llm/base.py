"""The LLM port. Agents depend on this, never on a vendor SDK.

Two implementations: Gemini and Anthropic. They differ in one way that actually matters —
**how structured output is enforced**:

  * Gemini constrains decoding against a JSON Schema (`response_json_schema`).
  * Claude does it through forced tool use: the schema becomes a tool's `input_schema`, and the
    model is *required* to call it.

Different mechanisms, same guarantee, and the guarantee is the point: an agent physically cannot
emit a requirement without an id, a priority and a `source_evidence` array, because the decoder will
not produce one. That guardrail is not a prompt instruction — it is structural, and it survives the
provider swap.

Embeddings deliberately do NOT live on this port. Anthropic has no embedding model, so retrieval
stays on Gemini regardless of who is doing the reasoning. Pretending otherwise with a fake method
would just move the failure somewhere less obvious.
"""

from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    live: bool

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], task: str,
        model: str | None = None, temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Constrained generation. The returned dict conforms to `schema`."""

    def generate_text(
        self, *, system: str, prompt: str, task: str, model: str | None = None,
        temperature: float = 0.3,
    ) -> str: ...

    @property
    def model_name(self) -> str:
        """Recorded on every artifact version. Model-risk review will ask for exactly this."""

    def selftest(self) -> dict[str, Any]: ...
