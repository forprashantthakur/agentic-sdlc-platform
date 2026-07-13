"""Which model does which agent use.

The point of per-agent routing: the six agents are not doing the same kind of work.

  * **Agent 1 is a judgement task.** It has to notice that the workshop minutes and the sponsor's
    call contradict each other, and *escalate rather than resolve*. That is where a frontier model
    earns its cost, and where a cheap one quietly picks a side and hands you a plausible, wrong
    requirement.
  * **Agents 2, 3, 4 and 6 are structured transformation.** Approved requirements in, documents out,
    schema-constrained at the decoder. A fast model does this well.
  * **Agent 5 has no model at all.** It is the approval gate.

So paying frontier rates to format a sprint plan is waste, and paying budget rates to adjudicate a
regulatory conflict is a false economy. Route accordingly.

Embeddings stay on Gemini regardless of provider — Anthropic has no embedding model.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import log
from app.llm.base import LLMProvider


@lru_cache
def _gemini():
    from app.llm.gemini import gemini

    return gemini()


@lru_cache
def _anthropic():
    from app.llm.anthropic_provider import AnthropicProvider

    return AnthropicProvider()


def provider(name: str) -> LLMProvider:
    return _anthropic() if name.lower() == "anthropic" else _gemini()


def _route(agent_id: str) -> tuple[str, str | None]:
    """(provider, model) for an agent. Per-agent overrides beat the global default."""
    override = (settings.agent_models or {}).get(agent_id)
    if override:
        # Format: "anthropic:claude-opus-4-8" or just "gemini-3.5-flash"
        if ":" in override:
            p, m = override.split(":", 1)
            return p.strip().lower(), m.strip()
        return settings.llm_provider.lower(), override.strip()
    return settings.llm_provider.lower(), None


def llm_for(agent_id: str) -> tuple[LLMProvider, str | None]:
    p, m = _route(agent_id)
    return provider(p), m


def describe_routing() -> list[dict]:
    """Surfaced on /api/integrations/llm/agents, so nobody has to read env vars to know what ran."""
    out = []
    for agent_id, name, thinks in [
        ("agent1_requirements", "Requirement Gathering", True),
        ("agent2_concept_note", "Concept Note", True),
        ("agent3_wireframe", "Wireframe", True),
        ("agent4_requirement_docs", "Requirement Documents", True),
        ("agent5_approval", "Approval", False),
        ("agent6_sprint", "Sprint", True),
    ]:
        if not thinks:
            out.append({"agent": agent_id, "name": name, "provider": None, "model": None,
                        "why": "DELIBERATELY NO LLM. It is the human-approval gate — a gate with a "
                               "model in it is a gate a prompt-injected email could argue through."})
            continue
        p, m = _route(agent_id)
        prov = provider(p)
        out.append({
            "agent": agent_id, "name": name, "provider": p,
            "model": m or (settings.anthropic_model if p == "anthropic" else settings.gemini_model),
            "live": prov.live,
        })
    return out
