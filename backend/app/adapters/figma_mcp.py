"""Figma over MCP.

The wireframe agent does not talk to the Figma REST API. It speaks MCP to a Figma MCP
server, which exposes design-authoring tools. We keep the JSON-RPC surface small and
explicit — `tools/call` with a tool name and arguments — so the same adapter works
against the official Figma MCP server or the bank's internal design-system MCP.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import log


class FigmaMCPAdapter:
    """Real implementation: JSON-RPC 2.0 over Streamable HTTP."""

    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self._id = 0

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        with httpx.Client(timeout=90) as c:
            r = c.post(self.url, json=payload, headers=self.headers)
            r.raise_for_status()
            body = r.json()
        if "error" in body:
            raise RuntimeError(f"Figma MCP error: {body['error']}")
        return body.get("result", {})

    def _call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        content = res.get("structuredContent")
        if content is not None:
            return content
        blocks = res.get("content") or []
        import json

        for b in blocks:
            if b.get("type") == "text":
                try:
                    return json.loads(b["text"])
                except json.JSONDecodeError:
                    return {"text": b["text"]}
        return {}

    def create_wireframes(self, *, project_name, screens, design_system) -> dict[str, Any]:
        file = self._call_tool(
            "create_file",
            {"name": f"{project_name} — Wireframes", "team_id": settings.figma_team_id},
        )
        file_key = file.get("file_key") or file.get("key", "")

        frames: list[str] = []
        for i, sc in enumerate(screens):
            self._call_tool(
                "create_frame",
                {
                    "file_key": file_key,
                    "name": sc["name"],
                    "x": i * 420,
                    "y": 0,
                    "width": 375,
                    "height": 812,
                    "design_system": design_system,
                    "children": [
                        {
                            "component": c["type"],
                            "label": c.get("label", ""),
                            "props": c.get("props", {}),
                        }
                        for c in sc.get("components", [])
                    ],
                },
            )
            frames.append(sc["name"])

        thumbs = self._call_tool("export_frames", {"file_key": file_key, "format": "png", "scale": 2})
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
            "thumbnails": [
                f"https://www.figma.com/file/{key}/thumb/{i}.png" for i, _ in enumerate(screens)
            ],
            "mock": True,
        }
