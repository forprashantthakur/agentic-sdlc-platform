from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.adapters import registry
from app.adapters.figma_mcp import TOOL_CANDIDATES, FigmaMCPAdapter
from app.core.config import settings
from app.llm.gemini import gemini

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/wireframes/tools")
def wireframe_tools():
    """Dump the active wireframe provider's advertised MCP tools.

    Tool names are server-, version- and plan-dependent. Guessing them is how you get a
    'method not found' at 2am. Point the adapter at the real server, call this, and read the
    mapping off reality.
    """
    adapter = registry.wireframer()
    provider = settings.wireframe_provider

    if type(adapter).__name__.startswith("Mock"):
        raise HTTPException(
            400,
            f"Wireframes are mocked (provider={provider}). For Stitch: set STITCH_API_KEY and "
            "STITCH_MOCK=false. For Figma: set FIGMA_TOKEN and FIGMA_MOCK=false.",
        )
    try:
        tools = adapter.list_tools(refresh=True)
    except Exception as e:
        raise HTTPException(502, f"Could not reach the {provider} MCP server: {e}") from e

    from app.adapters.stitch import TOOLS as STITCH_TOOLS

    resolved = {}
    if provider == "stitch":
        resolved = {op: adapter.mcp.resolve(names, op) for op, names in STITCH_TOOLS.items()}

    return {
        "provider": provider,
        "server": settings.stitch_mcp_url if provider == "stitch" else settings.figma_mcp_url,
        "tool_count": len(tools),
        "tools": [{"name": n, "description": (t.get("description") or "")[:200],
                   "input_schema": t.get("inputSchema")} for n, t in sorted(tools.items())],
        "resolved_operations": resolved,
        "missing_operations": [op for op, name in resolved.items() if name is None],
    }


@router.get("/figma/tools")
def figma_tools():
    """Dump the Figma MCP server's advertised tool list.

    This exists because tool names are server- and plan-dependent, and guessing them is how
    you get a 'method not found' at 2am. Point the adapter at the real server, call this,
    and map the logical operations onto whatever it actually offers.
    """
    adapter = registry.figma()
    if isinstance(adapter, FigmaMCPAdapter):
        try:
            tools = adapter.list_tools(refresh=True)
        except Exception as e:
            raise HTTPException(502, f"Could not reach the Figma MCP server: {e}") from e
    else:
        raise HTTPException(
            400,
            "Figma is mocked. Set FIGMA_TOKEN, FIGMA_MCP_URL=https://mcp.figma.com/mcp "
            "and FIGMA_MOCK=false, then call this again.",
        )

    resolved = {op: adapter._resolve(op) for op in TOOL_CANDIDATES}
    return {
        "server": settings.figma_mcp_url,
        "tool_count": len(tools),
        "tools": [
            {"name": n, "description": (t.get("description") or "")[:200],
             "input_schema": t.get("inputSchema")}
            for n, t in sorted(tools.items())
        ],
        "resolved_operations": resolved,
        "missing_operations": [op for op, name in resolved.items() if name is None],
    }


@router.get("/llm/selftest")
def llm_selftest():
    """Prove the Gemini path works — one small structured call plus one embedding.

    Run this the moment you set GOOGLE_API_KEY. A failure here is a second's feedback; the same
    failure discovered inside Agent 4 costs a full run and an unhelpful traceback.
    """
    return gemini().selftest()


@router.get("/llm/agents")
def llm_agents():
    """Which agents call the model, with what, and at what temperature.

    Agent 5 has no LLM. That is deliberate and worth stating plainly: it is the approval gate, and
    a gate with a language model in it is a gate that a prompt-injected email in the evidence base
    could argue with. It renders the packet, sends the mail, records the human's decision, and
    seals the version. It does not think.
    """
    live = gemini().live
    return {
        "llm": "live" if live else "mock",
        "model": gemini().model_name,
        "agents": [
            {"id": "agent1_requirements", "name": "Requirement Gathering", "uses_llm": True,
             "model": settings.gemini_model, "temperature": 0.1,
             "why": "Extraction, not creativity. Low temperature keeps it close to the evidence.",
             "structured_output": "REQUIREMENTS schema — an id, priority and source_evidence are non-optional"},
            {"id": "agent2_concept_note", "name": "Concept Note", "uses_llm": True,
             "model": settings.gemini_model, "temperature": 0.25,
             "why": "Framing and synthesis — needs some latitude, not much.",
             "structured_output": "CONCEPT_NOTE schema"},
            {"id": "agent3_wireframe", "name": "Wireframe", "uses_llm": True,
             "model": settings.gemini_model, "temperature": 0.35,
             "why": "Screen design benefits from the widest latitude of any agent here.",
             "structured_output": "WIREFRAME schema"},
            {"id": "agent4_requirement_docs", "name": "Requirement Documents", "uses_llm": True,
             "model": settings.gemini_model, "temperature": 0.2,
             "why": "Six separate constrained generations (BRD, FRD, SRS, stories, APIs, NFRs); "
                    "BRD/FRD/SRS run concurrently.",
             "structured_output": "DOCUMENT · USER_STORIES · API_REQUIREMENTS · NFR schemas"},
            {"id": "agent5_approval", "name": "Approval", "uses_llm": False,
             "model": None, "temperature": None,
             "why": "DELIBERATELY NO LLM. It is the human-approval gate. A model here is a gate a "
                    "prompt-injected email could talk its way through.",
             "structured_output": None},
            {"id": "agent6_sprint", "name": "Sprint", "uses_llm": True,
             "model": settings.gemini_model, "temperature": 0.25,
             "why": "Organises approved stories into epics and sprints. It must not rewrite them — "
                    "that would break traceability to the approved BRD.",
             "structured_output": "SPRINT_PLAN schema"},
        ],
        "embeddings": {"model": settings.gemini_embed_model, "dims": settings.embed_dim,
                       "used_by": "RAG — every agent's retrieval, and the copilot"},
    }
