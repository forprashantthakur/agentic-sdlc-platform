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

import base64
import io
import uuid
from typing import Any

from app.adapters.mcp import McpClient
from app.adapters.wireframe_render import render as render_wireframe_png
from app.core import progress
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
    # Stitch exposes the screenshot TWO different ways depending on the tool, and I only ever
    # supported one of them:
    #   get_screen        -> a download URL for the PNG
    #   get_screen_image  -> the PNG itself, base64, in an MCP image content block
    # A base64 block contains no "http" string, so the URL-walker discarded it without a word.
    # That is why five screens generated correctly and every preview came back empty.
    "get_screen_image": ["get_screen_image", "get_screenshot", "screen_image", "get_screen_png"],
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
        # ONE credential, never two.
        #
        # Sending both `x-goog-api-key` AND `Authorization: Bearer <api-key>` returns 401 — and not
        # for the reason you would guess. Google's auth middleware sees an Authorization header,
        # tries to validate it as an OAuth token, fails, and returns 401 WITHOUT EVER LOOKING at the
        # perfectly valid API key beside it. Belt-and-braces became a self-inflicted wound.
        #
        # So: an API key goes in x-goog-api-key, alone. An OAuth access token goes in Authorization,
        # alone (with the billing project, which OAuth requires and API keys do not).
        headers: dict[str, str] = {}
        if settings.stitch_access_token:
            headers["Authorization"] = f"Bearer {settings.stitch_access_token}"
            if settings.vertex_project or settings.google_cloud_project:
                headers["x-goog-user-project"] = (
                    settings.google_cloud_project or settings.vertex_project
                )
        elif api_key:
            headers["x-goog-api-key"] = api_key

        self.mcp = McpClient(url, headers=headers)

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
                except Exception as e:
                    log.warning("stitch.get_screen_failed", screen=sc["name"], error=str(e))

            # Still nothing? Ask for the image directly — this tool returns the PNG inline, base64.
            if screen_id and not shot:
                try:
                    img = self.mcp.call(
                        TOOLS["get_screen_image"],
                        {"project_id": project_id, "screen_id": screen_id},
                        operation="get_screen_image",
                        fuzzy=False,
                    )
                    shot = _inline_image(img) or _artifacts(img)[1]
                except Exception as e:
                    log.warning("stitch.get_image_failed", screen=sc["name"], error=str(e))

            if not shot:
                # Say what actually came back, on the run timeline, instead of rendering an empty
                # box and leaving someone to guess. Three rounds of guessing is enough.
                progress.emit(
                    f"Stitch returned no preview for '{sc['name']}'. Response keys: "
                    f"{sorted({p.split('.')[0].split('[')[0] for p, _ in _walk(res)})[:8]}",
                    level="warning",
                )

            out_screens.append({
                "name": sc["name"], "screen_id": screen_id,
                "screenshot_url": shot,      # a download URL for the PNG
                "html_url": html,            # a download URL for the HTML
                # Only link where Stitch told us to. A hand-built URL that 404s is worse than no
                # link — it makes a working integration look broken.
                "url": next((v for _, v in _walk(res)
                             if v.startswith("https://stitch.withgoogle.com")), ""),
                "requirement_ids": sc.get("requirement_ids", []),
            })

        return {
            "provider": "stitch",
            "project_id": project_id,
            "project_url": next(
                (v for _, v in _walk(project) if v.startswith("https://stitch.withgoogle.com")), ""
            ),
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


def _inline_image(res: dict[str, Any]) -> str:
    """An MCP image content block -> a data: URI the browser can render directly.

    No file store, no signed URL that expires in an hour, no extra endpoint to authenticate: the
    bytes travel with the artifact and still render after a Render restart. It costs artifact size,
    which for five screenshots is a trade worth making.
    """
    for block in res.get("images") or []:
        data = block.get("data") or (block.get("resource") or {}).get("blob")
        if data:
            mime = block.get("mimeType") or (block.get("resource") or {}).get("mimeType") or "image/png"
            return f"data:{mime};base64,{data}"
    return ""


IMAGE_HINT = ("image", "screenshot", "thumbnail", "preview", "png")
HTML_HINT = ("html", "code", "source")


def _walk(obj: Any, path: str = ""):
    """Every (key-path, string) pair in a response, however deeply it is nested."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def _artifacts(res: dict[str, Any]) -> tuple[str, str]:
    """Find the HTML and screenshot URLs wherever they actually are.

    I have now guessed the shape of this response three times and been wrong three times. The fix is
    not a better guess — it is to stop guessing: walk the whole response, and take any URL whose
    key-path or file extension says what it is. If Stitch nests it, renames it, or moves it, this
    keeps working.

    (And when it does not, /api/integrations/wireframes/probe prints the raw response so the next
    person does not have to guess either.)
    """
    html = shot = ""
    for path, val in _walk(res):
        if not val.startswith("http"):
            continue
        key = path.lower()
        if not shot and (any(h in key for h in IMAGE_HINT) or val.split("?")[0].endswith((".png", ".jpg", ".webp"))):
            shot = val
        elif not html and (any(h in key for h in HTML_HINT) or val.split("?")[0].endswith(".html")):
            html = val
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



# ── Offline wireframe rendering ───────────────────────────────────────────────────────────────
# Agent 3 already produces a STRUCTURED screen spec: every component, with a type and a label. That
# is enough to draw the screen ourselves. So the mock does not have to hand back a dead link and an
# empty grey box — it can render the actual wireframe, from the actual spec, with zero network calls
# and in about a millisecond.
#
# This is what makes a demo survivable when Google is returning 503s: the wireframes are real,
# specific to the project, traceable to requirements, and cannot fail.

_FILL = {
    "input": ("#FFFFFF", "#C7D2E0"), "textfield": ("#FFFFFF", "#C7D2E0"),
    "button": ("#004C8F", "#004C8F"), "cta": ("#004C8F", "#004C8F"),
    "table": ("#F4F7FB", "#C7D2E0"), "list": ("#F4F7FB", "#C7D2E0"),
    "card": ("#F8FAFC", "#DCE4EE"), "chart": ("#EEF4FB", "#C7D2E0"),
    "banner": ("#FFF6E5", "#F0C879"), "alert": ("#FFF1F1", "#E9A8A8"),
}


def _esc(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class MockStitchAdapter:
    def create_wireframes(self, *, project_name, screens, design_system) -> dict[str, Any]:
        pid = uuid.uuid4().hex[:12]
        nav = [s["name"] for s in screens]     # every screen sees the whole flow in its own nav
        log.info("stitch.mock.create", screens=len(screens))
        return {
            "provider": "stitch",
            "mock": True,
            "project_id": pid,
            "project_url": f"https://stitch.withgoogle.com/project/{pid}",
            "screens": [{
                "name": s["name"],
                "screen_id": f"{pid}-{i}",
                # A REAL wireframe, drawn from Agent 3's own component spec. Previously this was a
                # link to example.invalid, which 404s by design — honest, but it rendered as an
                # empty grey box, which is the last thing you want on a projector.
                "screenshot_url": render_wireframe_png({**s, "_nav": nav}, project=project_name),
                "html_url": "",
                "url": "",
                "rendered_offline": True,
                "requirement_ids": s.get("requirement_ids", []),
            } for i, s in enumerate(screens)],
            "frames": [s["name"] for s in screens],
        }

    def list_tools(self, refresh: bool = False) -> dict[str, dict]:
        return {}
