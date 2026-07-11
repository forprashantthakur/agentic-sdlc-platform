"""Figma over MCP.

Figma's MCP server gained write-to-canvas in Feb 2026 (create frames, components,
auto-layout, variables). Before that, file content was read-only over the REST API and
"generate wireframes into Figma" was impossible without a custom plugin.

Two things follow from that, and they shape this adapter:

1. WE DO NOT GUESS TOOL NAMES. The server advertises its own tools via `tools/list`, and
   they differ by server version and by seat/plan. So the adapter *discovers* the tool set
   at runtime and resolves the create/frame/export operations against what the server
   actually offers. If a required tool is absent, it says so loudly rather than firing a
   made-up method name into the void.

2. THE SPEC IS THE ARTIFACT; THE FRAMES ARE A RENDERING. Agent 3 produces a structured
   screen spec and only then draws. A Figma outage, an expired seat, or a renamed tool
   degrades to "spec produced, frames pending" — never a failed run.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import log

# Candidate names for each operation, in preference order. The first one the server
# actually advertises wins. Extend these lists as Figma renames things — that is far
# cheaper than rewriting call sites.
TOOL_CANDIDATES: dict[str, list[str]] = {
    "create_file": ["create_file", "create_design_file", "create_document"],
    "create_frame": ["create_frame", "create_node", "create_design", "add_frame"],
    "create_component": ["create_component", "create_instance", "add_component"],
    "export": ["export_frames", "export_nodes", "get_screenshot", "export_image"],
}


class FigmaMCPAdapter:
    """JSON-RPC 2.0 over Streamable HTTP against the Figma MCP server."""

    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self._id = 0
        self._tools: dict[str, dict] | None = None

    # ── JSON-RPC plumbing ─────────────────────────────────────────────────────
    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        with httpx.Client(timeout=90) as c:
            r = c.post(self.url, json=payload, headers=self.headers)
            r.raise_for_status()
            body = r.json()
        if "error" in body:
            raise RuntimeError(f"Figma MCP error on {method}: {body['error']}")
        return body.get("result", {})

    def list_tools(self, refresh: bool = False) -> dict[str, dict]:
        """The discovery call. Run this before assuming anything about the server."""
        if self._tools is None or refresh:
            result = self._rpc("tools/list", {})
            self._tools = {t["name"]: t for t in result.get("tools", [])}
            log.info("figma.tools_discovered", count=len(self._tools),
                     names=sorted(self._tools)[:25])
        return self._tools

    def _resolve(self, operation: str) -> str | None:
        """Map a logical operation onto whatever this server actually calls it."""
        available = self.list_tools()
        for candidate in TOOL_CANDIDATES.get(operation, []):
            if candidate in available:
                return candidate
        # Fall back to a fuzzy match — servers rename, and a near-miss beats a hard failure.
        for name in available:
            if operation.replace("_", "") in name.replace("_", "").replace("-", "").lower():
                return name
        return None

    def _call_tool(self, operation: str, args: dict[str, Any]) -> dict[str, Any]:
        name = self._resolve(operation)
        if name is None:
            raise RuntimeError(
                f"Figma MCP server exposes no tool for '{operation}'. "
                f"Available: {sorted(self.list_tools())}. "
                "Write-to-canvas requires a Full seat on a paid plan."
            )
        res = self._rpc("tools/call", {"name": name, "arguments": args})

        if (content := res.get("structuredContent")) is not None:
            return content
        for block in res.get("content") or []:
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except json.JSONDecodeError:
                    return {"text": block["text"]}
        return {}

    # ── the operation Agent 3 actually needs ──────────────────────────────────
    def create_wireframes(self, *, project_name, screens, design_system) -> dict[str, Any]:
        self.list_tools()  # fail fast, and log what this server can do

        file = self._call_tool(
            "create_file",
            {"name": f"{project_name} — Wireframes", "team_id": settings.figma_team_id},
        )
        file_key = file.get("file_key") or file.get("key") or file.get("fileKey", "")

        frames: list[str] = []
        for i, sc in enumerate(screens):
            self._call_tool(
                "create_frame",
                {
                    "file_key": file_key,
                    "name": sc["name"],
                    "x": i * 420, "y": 0, "width": 375, "height": 812,  # mobile canvas
                    "design_system": design_system,
                    "children": [
                        {"component": c["type"], "label": c.get("label", ""),
                         "props": c.get("props", {})}
                        for c in sc.get("components", [])
                    ],
                },
            )
            frames.append(sc["name"])

        thumbs = {}
        try:
            thumbs = self._call_tool("export", {"file_key": file_key, "format": "png", "scale": 2})
        except RuntimeError as e:
            log.warning("figma.export_unavailable", error=str(e))

        return {
            "file_key": file_key,
            "file_url": file.get("url", f"https://figma.com/file/{file_key}"),
            "frames": frames,
            "thumbnails": thumbs.get("urls", []),
        }


class MockFigmaAdapter:
    def create_wireframes(self, *, project_name, screens, design_system) -> dict[str, Any]:
        key = uuid.uuid4().hex[:12]
        log.info("figma.mock.create", screens=len(screens))
        return {
            "file_key": key,
            "file_url": f"https://www.figma.com/file/{key}/{project_name.replace(' ', '-')}-Wireframes",
            "frames": [s["name"] for s in screens],
            "thumbnails": [f"https://www.figma.com/file/{key}/thumb/{i}.png" for i, _ in enumerate(screens)],
            "mock": True,
        }

    def list_tools(self, refresh: bool = False) -> dict[str, dict]:
        return {}
