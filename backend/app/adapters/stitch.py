"""Google Stitch — Agent 3's wireframe generator.

Why Stitch rather than Figma, now that both exist:

  * Stitch generates a screen FROM TEXT. Agent 3 already produces a structured screen spec and a
    natural-language description of each screen, so the impedance match is exact. Figma's
    write-to-canvas wants geometry — we would be inventing x/y coordinates for a model to draw,
    which is a worse use of everyone's time.
  * Stitch returns HTML AND a screenshot. That means a wireframe can be embedded in the BRD itself,
    rather than a Figma link that a reviewer has to have a seat to open.
  * No paid seat. Figma write-to-canvas requires a Full seat on a paid plan plus usage billing;
    Stitch is free in Google Labs with monthly generation caps.

It is still a Labs product with caps, so the adapter degrades the same way the Figma one does: if
Stitch is unavailable, the run does not fail. The structured spec — which is what Agent 4 actually
consumes downstream — is produced regardless, and the screens are marked pending.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.adapters.mcp import McpClient
from app.core.config import settings
from app.core.logging import log

# Logical operation -> candidate tool names, in preference order. The SDK exposes create_project /
# generate_screen_from_text / get_screen; the MCP server may name them slightly differently, and
# will certainly rename them again. Extending this list is cheaper than rewriting call sites.
TOOLS: dict[str, list[str]] = {
    "create_project": ["create_project", "stitch_create_project", "new_project"],
    "generate_screen": ["generate_screen_from_text", "generate_screen", "create_screen",
                        "generate_ui", "stitch_generate_screen"],
    "get_screen": ["get_screen", "get_screen_html", "fetch_screen", "screen_get"],
    "set_design_system": ["set_design_system", "apply_design_system", "update_design_system"],
}


class StitchAdapter:
    """Real Stitch, over its MCP server."""

    def __init__(self, url: str, api_key: str) -> None:
        self.mcp = McpClient(url, token=api_key)

    def list_tools(self, refresh: bool = False) -> dict[str, dict]:
        return self.mcp.list_tools(refresh=refresh)

    def create_wireframes(self, *, project_name: str, screens: list[dict[str, Any]],
                          design_system: str) -> dict[str, Any]:
        self.mcp.list_tools()  # fail fast, and log what this server can actually do

        project = self.mcp.call(
            TOOLS["create_project"],
            {"name": f"{project_name} — Wireframes",
             "description": f"Low-fidelity wireframes generated from approved requirements. "
                            f"Design system: {design_system}"},
            operation="create_project",
        )
        project_id = project.get("project_id") or project.get("id") or project.get("projectId", "")

        # Optional: give Stitch the bank's design system up front, so it does not invent one.
        try:
            self.mcp.call(TOOLS["set_design_system"],
                          {"project_id": project_id, "design_system": design_system},
                          operation="set_design_system")
        except RuntimeError:
            log.info("stitch.no_design_system_tool", note="continuing with the prompt's guidance only")

        out_screens: list[dict[str, Any]] = []
        for sc in screens:
            res = self.mcp.call(
                TOOLS["generate_screen"],
                {"project_id": project_id,
                 "prompt": _prompt_for(sc, design_system),
                 "platform": "mobile" if "mobile" in design_system.lower() else "web"},
                operation="generate_screen",
            )
            screen_id = res.get("screen_id") or res.get("id") or res.get("screenId", "")

            html, shot = res.get("html", ""), res.get("screenshot_url") or res.get("screenshot", "")
            if screen_id and not (html and shot):
                # Some servers return an id and expect a second call for the artifacts.
                try:
                    full = self.mcp.call(TOOLS["get_screen"], {"screen_id": screen_id},
                                         operation="get_screen")
                    html = html or full.get("html", "")
                    shot = shot or full.get("screenshot_url") or full.get("screenshot", "")
                except RuntimeError as e:
                    log.warning("stitch.get_screen_failed", error=str(e))

            out_screens.append({
                "name": sc["name"], "screen_id": screen_id,
                "screenshot_url": shot, "html": html,
                "url": res.get("url") or (f"https://stitch.withgoogle.com/project/{project_id}"
                                          f"/screen/{screen_id}" if screen_id else ""),
                "requirement_ids": sc.get("requirement_ids", []),
            })

        return {
            "provider": "stitch",
            "project_id": project_id,
            "project_url": project.get("url", f"https://stitch.withgoogle.com/project/{project_id}"),
            "screens": out_screens,
            "frames": [s["name"] for s in out_screens],
        }


def _prompt_for(screen: dict[str, Any], design_system: str) -> str:
    """Turn Agent 3's structured screen spec into the prose Stitch generates from.

    The spec is the contract; this is a rendering of it. Every component, its label and its
    behavioural props are enumerated, so what Stitch draws is traceable to what the agent specified
    — and, through that, to the requirement it satisfies.
    """
    parts = [
        screen.get("stitch_prompt") or screen.get("purpose", ""),
        "",
        f"Screen: {screen['name']}.",
        f"Design system: {design_system}.",
        "",
        "It must contain exactly these elements:",
    ]
    for c in screen.get("components", []):
        props = ", ".join(f"{k}: {v}" for k, v in (c.get("props") or {}).items())
        parts.append(f"- {c['type']}: “{c.get('label', '')}”" + (f" ({props})" if props else ""))
    parts += [
        "",
        "Low-fidelity greybox wireframe. Structure and hierarchy, not visual design. "
        "Include the empty state and the error state where the components imply one. "
        "Label everything in plain English — this will be read by a business analyst, not a designer.",
    ]
    return "\n".join(p for p in parts if p is not None)


class MockStitchAdapter:
    def create_wireframes(self, *, project_name, screens, design_system) -> dict[str, Any]:
        pid = uuid.uuid4().hex[:12]
        log.info("stitch.mock.create", screens=len(screens))
        return {
            "provider": "stitch",
            "mock": True,
            "project_id": pid,
            "project_url": f"https://stitch.withgoogle.com/project/{pid}",
            "screens": [{
                "name": s["name"],
                "screen_id": f"{pid}-{i}",
                "screenshot_url": f"https://stitch.withgoogle.com/p/{pid}/s/{i}/preview.png",
                "html": f"<!-- mock: Stitch would return the generated HTML for “{s['name']}” here -->",
                "url": f"https://stitch.withgoogle.com/project/{pid}/screen/{i}",
                "requirement_ids": s.get("requirement_ids", []),
            } for i, s in enumerate(screens)],
            "frames": [s["name"] for s in screens],
        }

    def list_tools(self, refresh: bool = False) -> dict[str, dict]:
        return {}
