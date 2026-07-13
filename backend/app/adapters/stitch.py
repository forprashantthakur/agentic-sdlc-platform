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
    # Creating a design system and APPLYING one to existing screens are different tools with
    # different arguments. Conflating them (via a fuzzy match) is what silently killed the whole
    # wireframe step: apply_design_system rejected our args, and Agent 3 reported "screens pending".
    "create_design_system": ["create_design_system"],
    "apply_design_system": ["apply_design_system"],
    "get_project": ["get_project"],
}

# HDFC brand, expressed in the enums Stitch actually accepts (read from its published schema).
BRAND_THEME = {
    "bodyFont": "INTER",
    "headlineFont": "INTER",
    "colorMode": "LIGHT",
    "colorVariant": "NEUTRAL",
    "customColor": "#004C8F",   # HDFC navy — the seed for Stitch's dynamic colour system
}


class StitchAdapter:
    """Real Stitch, over its MCP server.

    Endpoint and tool signatures taken from google-labs-code/stitch-sdk, not inferred. The first
    version of this adapter guessed `stitch.withgoogle.com/mcp` and would never have connected —
    the server is on googleapis.com, and it authenticates with an API key header, not a bearer token.
    """

    def __init__(self, url: str, api_key: str) -> None:
        # Google APIs take the key in x-goog-api-key. We send the bearer header too, because the
        # OAuth path (STITCH_ACCESS_TOKEN) uses it and one adapter should serve both.
        self.mcp = McpClient(url, headers={"x-goog-api-key": api_key} if api_key else {})
        if api_key:
            self.mcp.headers["Authorization"] = f"Bearer {api_key}"

    def list_tools(self, refresh: bool = False) -> dict[str, dict]:
        return self.mcp.list_tools(refresh=refresh)

    def create_wireframes(self, *, project_name: str, screens: list[dict[str, Any]],
                          design_system: str) -> dict[str, Any]:
        self.mcp.list_tools()  # fail fast, and log what this server can actually do

        project = self.mcp.call(
            TOOLS["create_project"],
            {"title": f"{project_name} — Wireframes"},   # the SDK's arg is `title`
            operation="create_project",
        )
        project_id = project.get("project_id") or project.get("id") or project.get("projectId", "")

        # Give Stitch the bank's brand up front, so it does not invent a design system. Exact tool
        # name only — no fuzzy matching here, because the near-miss (apply_design_system) takes
        # entirely different arguments and its failure kills the run.
        #
        # And catch Exception, not RuntimeError: a schema-validation rejection arrives as an
        # httpx.HTTPStatusError, which sailed straight past the old `except RuntimeError` and took
        # the whole wireframe step down with it. Branding is a nice-to-have; it must never be able
        # to cost us the screens.
        try:
            self.mcp.call(
                TOOLS["create_design_system"],
                {"project_id": project_id,
                 "design_system": {"displayName": "HDFC Bank", "theme": BRAND_THEME}},
                operation="create_design_system", fuzzy=False,
            )
            log.info("stitch.design_system_applied", colour=BRAND_THEME["customColor"])
        except Exception as e:
            log.info("stitch.design_system_skipped", error=str(e)[:140],
                     note="screens will still generate — brand comes from the prompt instead")

        out_screens: list[dict[str, Any]] = []
        for sc in screens:
            res = self.mcp.call(
                TOOLS["generate_screen"],
                {"project_id": project_id,
                 "prompt": _prompt_for(sc, design_system),
                 "device_type": _device_type(design_system)},
                operation="generate_screen",
            )
            screen_id = res.get("screen_id") or res.get("id") or res.get("screenId", "")

            # Per the SDK: getHtml() and getImage() return DOWNLOAD URLS, not inline content.
            html, shot = _artifacts(res)
            if screen_id and not (html and shot):
                # Generation may return only an id; the artifacts come from a second call.
                try:
                    full = self.mcp.call(
                        TOOLS["get_screen"],
                        {"project_id": project_id, "screen_id": screen_id},
                        operation="get_screen",
                    )
                    h2, s2 = _artifacts(full)
                    html, shot = html or h2, shot or s2
                except RuntimeError as e:
                    log.warning("stitch.get_screen_failed", screen=sc["name"], error=str(e))

            out_screens.append({
                "name": sc["name"], "screen_id": screen_id,
                "screenshot_url": shot,      # a download URL for the PNG
                "html_url": html,            # a download URL for the HTML
                "url": res.get("url") or (f"https://stitch.withgoogle.com/projects/{project_id}"
                                          if project_id else ""),
                "requirement_ids": sc.get("requirement_ids", []),
            })

        return {
            "provider": "stitch",
            "project_id": project_id,
            "project_url": project.get("url", f"https://stitch.withgoogle.com/projects/{project_id}"),
            "screens": out_screens,
            "frames": [s["name"] for s in out_screens],
        }


DEVICE = {"mobile": "MOBILE", "tablet": "TABLET", "desktop": "DESKTOP", "web": "DESKTOP"}


def _device_type(design_system: str) -> str:
    ds = design_system.lower()
    for k, v in DEVICE.items():
        if k in ds:
            return v
    return "AGNOSTIC"


def _artifacts(res: dict[str, Any]) -> tuple[str, str]:
    """Pull the HTML and screenshot download URLs out of a response, whatever it calls them."""
    html = (res.get("html") or res.get("html_url") or res.get("htmlUrl")
            or res.get("html_download_url") or "")
    shot = (res.get("image") or res.get("image_url") or res.get("imageUrl")
            or res.get("screenshot") or res.get("screenshot_url") or res.get("screenshotUrl") or "")
    return html, shot


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
                # Deliberately marked as mock URLs. They 404, and they should: a mock that hands back
                # a plausible-looking link is how you end up wondering why Stitch "lost" your screens.
                "screenshot_url": f"https://example.invalid/mock-stitch/{pid}/{i}/preview.png",
                "html_url": f"https://example.invalid/mock-stitch/{pid}/{i}/screen.html",
                "url": "https://stitch.withgoogle.com  (mock — set STITCH_API_KEY for real screens)",
                "requirement_ids": s.get("requirement_ids", []),
            } for i, s in enumerate(screens)],
            "frames": [s["name"] for s in screens],
        }

    def list_tools(self, refresh: bool = False) -> dict[str, dict]:
        return {}
