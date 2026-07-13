"""A minimal MCP client, shared by every MCP-backed adapter.

Both Figma and Google Stitch expose MCP servers, and the JSON-RPC plumbing was identical in each
adapter. It lives here once.

The one opinion baked in: WE DO NOT GUESS TOOL NAMES. Tool names differ by server, by version and
by plan. The client calls `tools/list`, discovers what the server actually offers, and resolves a
logical operation ("create a screen") against that. If the operation is missing, it fails loudly
and names what *was* available — rather than firing an invented method into the void and reporting
a mysterious 404 three layers up.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.logging import log


class McpClient:
    def __init__(self, url: str, token: str = "", headers: dict[str, str] | None = None,
                 timeout: int = 120) -> None:
        self.url = url
        self.timeout = timeout
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **(headers or {}),
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self._id = 0
        self._tools: dict[str, dict] | None = None

    # ── JSON-RPC ──────────────────────────────────────────────────────────────
    def rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(self.url, json=payload, headers=self.headers)
            r.raise_for_status()
            body = r.json()
        if "error" in body:
            raise RuntimeError(f"MCP error on {method}: {body['error']}")
        return body.get("result", {})

    def list_tools(self, refresh: bool = False) -> dict[str, dict]:
        if self._tools is None or refresh:
            result = self.rpc("tools/list")
            self._tools = {t["name"]: t for t in result.get("tools", [])}
            log.info("mcp.tools_discovered", url=self.url, count=len(self._tools),
                     names=sorted(self._tools)[:30])
        return self._tools

    def resolve(self, candidates: list[str], operation: str = "") -> str | None:
        """Map a logical operation onto whatever this server actually calls it."""
        available = self.list_tools()
        for c in candidates:
            if c in available:
                return c
        # Fuzzy fallback — servers rename things, and a near-miss beats a hard failure.
        want = (operation or candidates[0]).replace("_", "").replace("-", "").lower()
        for name in available:
            if want in name.replace("_", "").replace("-", "").lower():
                return name
        return None

    def call(self, candidates: list[str], args: dict[str, Any], operation: str = "") -> dict[str, Any]:
        name = self.resolve(candidates, operation)
        if name is None:
            raise RuntimeError(
                f"This MCP server exposes no tool for '{operation or candidates[0]}'. "
                f"Available: {sorted(self.list_tools())}"
            )
        res = self.rpc("tools/call", {"name": name, "arguments": args})

        if (content := res.get("structuredContent")) is not None:
            return content
        out: dict[str, Any] = {}
        for block in res.get("content") or []:
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except json.JSONDecodeError:
                    out.setdefault("text", "")
                    out["text"] += block["text"]
            elif block.get("type") in ("image", "resource"):
                out.setdefault("images", []).append(block)
        return out
