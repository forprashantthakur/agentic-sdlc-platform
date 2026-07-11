from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.adapters import registry
from app.adapters.figma_mcp import TOOL_CANDIDATES, FigmaMCPAdapter
from app.core.config import settings

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


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
