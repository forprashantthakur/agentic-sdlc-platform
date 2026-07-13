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

    def resolve(self, candidates: list[str], operation: str = "", fuzzy: bool = True) -> str | None:
        """Map a logical operation onto whatever this server actually calls it.

        `fuzzy` exists because fuzzy matching bit us once, hard: `set_design_system` fuzzily matched
        `apply_design_system`, a completely different tool with completely different arguments. The
        call failed, and the failure surfaced three layers up as "wireframes pending" with no clue
        why. For any operation where a near-miss is worse than a clean absence, pass fuzzy=False.
        """
        available = self.list_tools()
        for c in candidates:
            if c in available:
                return c
        if not fuzzy:
            return None
        want = (operation or candidates[0]).replace("_", "").replace("-", "").lower()
        for name in available:
            if want in name.replace("_", "").replace("-", "").lower():
                log.warning("mcp.fuzzy_match", operation=operation or candidates[0], matched=name,
                            note="verify the argument schema — a near-miss tool takes different args")
                return name
        return None

    def schema_of(self, tool: str) -> dict[str, Any]:
        return (self.list_tools().get(tool) or {}).get("inputSchema") or {}

    def adapt_args(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """Rename our snake_case arguments to whatever the tool's schema actually declares.

        Google's MCP tools take camelCase (`projectId`, `assetId`); ours were snake_case, so every
        call would have been rejected on validation. Rather than hard-coding a convention that will
        change again, we read the tool's own input schema and match each argument to the property it
        declares. Anything the schema does not declare is dropped, because an unexpected property is
        a rejected request on a strict schema.
        """
        props = (self.schema_of(tool).get("properties") or {}).keys()
        if not props:
            return args      # no schema published — send what we have and let the server judge

        def variants(k: str) -> list[str]:
            camel = "".join(w if i == 0 else w.capitalize() for i, w in enumerate(k.split("_")))
            return [k, camel, k.replace("_", ""), camel.lower()]

        out: dict[str, Any] = {}
        for key, value in args.items():
            match = next((v for v in variants(key) if v in props), None)
            if match:
                out[match] = value
            else:
                log.info("mcp.arg_dropped", tool=tool, arg=key,
                         note="not declared in the tool's schema")
        return out

    def call(self, candidates: list[str], args: dict[str, Any], operation: str = "",
             fuzzy: bool = True) -> dict[str, Any]:
        name = self.resolve(candidates, operation, fuzzy=fuzzy)
        if name is None:
            raise RuntimeError(
                f"This MCP server exposes no tool for '{operation or candidates[0]}'. "
                f"Available: {sorted(self.list_tools())}"
            )
        res = self.rpc("tools/call", {"name": name, "arguments": self.adapt_args(name, args)})

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
