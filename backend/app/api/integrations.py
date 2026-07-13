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
        "auth": ("oauth (Authorization: Bearer)" if settings.stitch_access_token
                 else "api key (x-goog-api-key)" if settings.stitch_api_key
                 else "NONE — this will 401"),
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


@router.get("/llm/routing")
def llm_routing():
    """Which model each agent actually uses — and why. Nobody should have to read env vars for this.

    The model that produced a document is also stamped on every artifact version, so the audit trail
    survives a provider change: a BRD written by Claude and a BRD written by Gemini are
    distinguishable months later, which is exactly what a model-risk review will ask for.
    """
    from app.llm.router import describe_routing

    return {
        "default_provider": settings.llm_provider,
        "embeddings": {
            "provider": "gemini",
            "model": settings.gemini_embed_model,
            "note": "Always Gemini. Anthropic has no embedding model, so retrieval stays on Gemini "
                    "even when Claude does the reasoning — GOOGLE_API_KEY remains required.",
        },
        "agents": describe_routing(),
    }


@router.get("/llm/selftest")
def llm_selftest():
    """Prove the Gemini path works — one small structured call plus one embedding.

    Run this the moment you set GOOGLE_API_KEY. A failure here is a second's feedback; the same
    failure discovered inside Agent 4 costs a full run and an unhelpful traceback.
    """
    from app.llm.router import provider

    out = {"default_provider": settings.llm_provider,
           "reasoning": provider(settings.llm_provider).selftest()}
    # Embeddings are always Gemini, whatever the reasoning provider — test them separately, because
    # a working Claude key with a broken Gemini key is a platform with no retrieval at all.
    out["embeddings"] = gemini().selftest().get("embeddings", {"ok": False, "error": "not run"})
    out["ready"] = bool(out["reasoning"].get("ready") and out["embeddings"].get("ok"))
    return out


@router.get("/llm/models")
def llm_models():
    """List the models THIS key can actually call, and flag whether the configured ones are among them.

    Run this the moment a run dies with a 404. Model names change faster than any hard-coded default
    can keep up with, and the API is the only source of truth about your key.
    """
    return gemini().list_models()


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


@router.get("/wireframes/probe")
def wireframes_probe(prompt: str = "A simple login screen with email and password fields"):
    """Generate ONE screen and return the RAW MCP responses, unparsed.

    This exists because I guessed the shape of Stitch's response three times and was wrong three
    times — the screenshot URL was never where I expected it. A probe that prints reality is worth
    more than a fourth guess, and it means the next person to hit this does not repeat the exercise.
    """
    from app.adapters.stitch import TOOLS, StitchAdapter, _artifacts, _inline_image

    adapter = registry.wireframer()
    if not isinstance(adapter, StitchAdapter):
        raise HTTPException(400, "Stitch is not the active provider, or it is mocked.")

    out: dict[str, Any] = {"server": settings.stitch_mcp_url}
    try:
        project = adapter.mcp.call(TOOLS["create_project"], {"title": "Probe"},
                                   operation="create_project")
        out["create_project_raw"] = project
        pid = project.get("project_id") or project.get("id") or project.get("projectId", "")

        gen = adapter.mcp.call(
            TOOLS["generate_screen"],
            {"project_id": pid, "prompt": prompt, "device_type": "MOBILE"},
            operation="generate_screen",
        )
        out["generate_screen_raw"] = gen
        sid = gen.get("screen_id") or gen.get("id") or gen.get("screenId", "")

        out["tools_available"] = sorted(adapter.mcp.list_tools())

        if sid:
            try:
                out["get_screen_raw"] = adapter.mcp.call(
                    TOOLS["get_screen"], {"project_id": pid, "screen_id": sid},
                    operation="get_screen",
                )
            except Exception as e:
                out["get_screen_error"] = f"{type(e).__name__}: {e}"

            # The other contract: the PNG itself, base64, in an MCP image block. A base64 block
            # contains no "http" string, so the URL walker discards it in silence — which is exactly
            # how five screens generated correctly and every preview came back empty.
            try:
                img = adapter.mcp.call(
                    TOOLS["get_screen_image"], {"project_id": pid, "screen_id": sid},
                    operation="get_screen_image", fuzzy=False,
                )
                out["get_screen_image_keys"] = sorted(img.keys())
                inline = _inline_image(img)
                out["get_screen_image_inline"] = (inline[:64] + "…") if inline else None
            except Exception as e:
                out["get_screen_image_error"] = f"{type(e).__name__}: {e}"
                inline = ""

        merged = {**gen, **out.get("get_screen_raw", {})}
        html, shot = _artifacts(merged)
        shot = shot or (inline if sid else "")
        out["extracted"] = {
            "html_url": html or None,
            "screenshot": ("base64 image block" if shot.startswith("data:") else shot) or None,
        }
        out["verdict"] = ("Extraction works — screens will render in the app and in the exports."
                          if shot else
                          "No image found by EITHER route (URL walk or base64 block). Send this whole "
                          "payload and I will map it in one pass — no more guessing.")
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out
