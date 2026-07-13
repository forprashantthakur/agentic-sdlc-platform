"""High-fidelity offline wireframe rendering.

Agent 3 emits a structured screen spec — every component, typed and labelled. That is enough to draw
a real wireframe, so we do, with no network call and no browser.

Two deliberate decisions:

* **PNG, not SVG.** python-docx cannot embed SVG at all, so an SVG wireframe renders in the browser
  and then silently vanishes from the Word export. PNG is the one raster format the browser,
  WeasyPrint and Word all accept — and it is what real Stitch returns, so the offline and live paths
  converge on a single code path instead of two.

* **The font is vendored.** PIL falls back to a bitmap font when it cannot find a TTF, which looks
  fine on a laptop with system fonts and turns into jagged 8px text on a slim container. The font
  ships with the repo so production renders exactly like development.

This produces a *high-fidelity greybox*: real tables with headers and rows, labelled fields,
metric cards, charts, chips. It is not brand-finished UI — that is what the live Stitch path is
for, and this does not pretend otherwise.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# ── canvas ────────────────────────────────────────────────────────────────────
W, H = 1440, 900          # logical size — a desktop screen, not a thumbnail
S = 2                     # supersample, then downscale: crisp text at any zoom
NAV_W, TOP_H = 232, 60
PAD = 32

NAVY = (0, 76, 143)
NAVY_D = (0, 58, 110)
INK = (28, 40, 54)
MUTED = (122, 138, 156)
LINE = (219, 227, 237)
BG = (247, 249, 252)
WHITE = (255, 255, 255)
AMBER_BG, AMBER_LN, AMBER_TX = (255, 247, 230), (240, 200, 121), (146, 94, 10)
RED_BG, RED_LN, RED_TX = (254, 242, 242), (233, 168, 168), (155, 44, 44)
GREEN = (22, 138, 90)

_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(str(_FONTS / name), size * S)
    except OSError:                                    # never crash a run over a font
        return ImageFont.load_default()


def _t(d: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, size: int = 13,
       bold: bool = False, fill: tuple = INK) -> None:
    d.text((xy[0] * S, xy[1] * S), text, font=_font(size, bold), fill=fill)


def _box(d: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], *, fill=WHITE, outline=LINE,
         r: int = 8, width: int = 1) -> None:
    d.rounded_rectangle([xy[0] * S, xy[1] * S, xy[2] * S, xy[3] * S], radius=r * S,
                        fill=fill, outline=outline, width=width * S)


def _bar(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int = 8, fill=(226, 232, 240)) -> None:
    d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=(h // 2) * S, fill=fill)


def _split_cols(label: str) -> list[str]:
    """"Deals — pair, notional, tenor, rate" -> the column headers a designer would draw."""
    tail = label.split("—")[-1] if "—" in label else label
    cols = [c.strip().title() for c in tail.split(",") if c.strip()]
    return cols[:5] if len(cols) >= 2 else ["Reference", "Detail", "Status", "Updated"]


# ── component renderers ───────────────────────────────────────────────────────
def _table(d, x, y, w, label) -> int:
    cols = _split_cols(label)
    cw = w // len(cols)
    head_h, row_h, rows = 34, 32, 4
    h = head_h + row_h * rows
    _box(d, (x, y, x + w, y + h), fill=WHITE)
    d.rectangle([x * S, y * S, (x + w) * S, (y + head_h) * S], fill=(240, 244, 249))
    for i, c in enumerate(cols):
        _t(d, (x + 14 + i * cw, y + 11), c[:16], size=11, bold=True, fill=(74, 90, 108))
    for r in range(rows):
        ry = y + head_h + r * row_h
        d.line([(x * S, ry * S), ((x + w) * S, ry * S)], fill=LINE, width=1 * S)
        for i in range(len(cols)):
            _bar(d, x + 14 + i * cw, ry + 12, int(cw * 0.55), 9)
    return h


def _chart(d, x, y, w, label) -> int:
    h = 168
    _box(d, (x, y, x + w, y + h), fill=WHITE)
    _t(d, (x + 14, y + 12), label[:60], size=11, bold=True, fill=(74, 90, 108))
    base, left = y + h - 22, x + 44
    d.line([(left * S, (y + 38) * S), (left * S, base * S)], fill=LINE, width=1 * S)
    d.line([(left * S, base * S), ((x + w - 20) * S, base * S)], fill=LINE, width=1 * S)
    heights = [42, 68, 55, 88, 74, 96, 61]
    bw = (w - 80) // len(heights)
    for i, bh in enumerate(heights):
        bx = left + 14 + i * bw
        d.rectangle([bx * S, (base - bh) * S, (bx + bw - 18) * S, base * S],
                    fill=NAVY if i % 2 == 0 else (120, 168, 214))
    return h


def _field(d, x, y, w, label) -> int:
    _t(d, (x, y), label[:54], size=11, bold=True, fill=(74, 90, 108))
    _box(d, (x, y + 18, x + w, y + 54), fill=WHITE)
    _t(d, (x + 14, y + 29), "Enter " + label.split("—")[0].strip().lower()[:38], size=12, fill=MUTED)
    return 62


def _card(d, x, y, w, label) -> int:
    h = 92
    _box(d, (x, y, x + w, y + h), fill=WHITE)
    _t(d, (x + 18, y + 16), label[:52], size=11, bold=True, fill=MUTED)
    _t(d, (x + 18, y + 40), "—", size=28, bold=True, fill=NAVY)
    _bar(d, x + 18, y + 74, min(160, w - 40), 6, (226, 240, 232))
    return h


def _banner(d, x, y, w, label, *, danger: bool = False) -> int:
    h = 52
    bg, ln, tx = (RED_BG, RED_LN, RED_TX) if danger else (AMBER_BG, AMBER_LN, AMBER_TX)
    _box(d, (x, y, x + w, y + h), fill=bg, outline=ln)
    d.ellipse([(x + 18) * S, (y + 21) * S, (x + 28) * S, (y + 31) * S], fill=ln)
    _t(d, (x + 38, y + 18), label[:88], size=12, bold=True, fill=tx)
    return h


def _button(d, x, y, w, label) -> int:
    bw = max(150, min(240, 14 + len(label) * 9))
    _box(d, (x, y, x + bw, y + 44), fill=NAVY, outline=NAVY, r=8)
    _t(d, (x + 20, y + 14), label[:26], size=13, bold=True, fill=WHITE)
    return 52


RENDERERS = {
    ("table", "list", "grid", "blotter"): _table,
    ("chart", "graph", "trend"): _chart,
    ("card", "metric", "stat", "kpi"): _card,
    ("button", "cta", "submit", "primary"): _button,
}


def render(screen: dict[str, Any], project: str = "HDFC Bank") -> str:
    """Render one screen spec to a PNG data: URI."""
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)

    # top bar
    d.rectangle([0, 0, W * S, TOP_H * S], fill=NAVY)
    _t(d, (24, 20), "HDFC BANK", size=15, bold=True, fill=WHITE)
    d.line([(150 * S, 16 * S), (150 * S, 44 * S)], fill=NAVY_D, width=2 * S)
    _t(d, (166, 22), project[:42], size=13, fill=(198, 219, 240))
    _box(d, (W - 250, 14, W - 24, 46), fill=NAVY_D, outline=NAVY_D)
    _t(d, (W - 234, 22), "Search", size=12, fill=(150, 184, 218))

    # left nav — the project's OTHER screens, so the flow is legible at a glance
    d.rectangle([0, TOP_H * S, NAV_W * S, H * S], fill=WHITE)
    d.line([(NAV_W * S, TOP_H * S), (NAV_W * S, H * S)], fill=LINE, width=1 * S)
    for i, item in enumerate(screen.get("_nav") or []):
        y = TOP_H + 24 + i * 44
        cur = item == screen.get("name")
        if cur:
            _box(d, (12, y - 8, NAV_W - 12, y + 28), fill=(235, 243, 251), outline=(235, 243, 251))
            d.rectangle([12 * S, (y - 8) * S, 15 * S, (y + 28) * S], fill=NAVY)
        _t(d, (28, y + 2), item[:22], size=12, bold=cur, fill=NAVY if cur else MUTED)

    # page header
    x, y = NAV_W + PAD, TOP_H + 28
    cw = W - NAV_W - PAD * 2
    _t(d, (x, y), screen.get("name", "Screen"), size=24, bold=True, fill=INK)
    _t(d, (x, y + 36), (screen.get("purpose") or "")[:104], size=12, fill=MUTED)

    # requirement chips — traceability, visible on the artwork itself
    cx = x
    for rid in (screen.get("requirement_ids") or [])[:6]:
        w_chip = 74
        _box(d, (cx, y + 60, cx + w_chip, y + 84), fill=(235, 243, 251), outline=(205, 226, 245), r=6)
        _t(d, (cx + 12, y + 66), rid, size=11, bold=True, fill=NAVY)
        cx += w_chip + 8

    y += 104
    for c in (screen.get("components") or []):
        if y > H - 70:
            break
        ctype = str(c.get("type", "")).lower()
        label = str(c.get("label", ""))
        fn = next((f for keys, f in RENDERERS.items() if any(k in ctype for k in keys)), None)
        if any(k in ctype for k in ("alert", "error")):
            y += _banner(d, x, y, cw, label, danger=True) + 14
        elif any(k in ctype for k in ("banner", "notice", "warning")):
            y += _banner(d, x, y, cw, label) + 14
        elif fn is _table or fn is _chart or fn is _card:
            y += fn(d, x, y, cw, label) + 16
        elif fn is _button:
            y += _button(d, x, y, cw, label) + 14
        else:
            y += _field(d, x, y, min(cw, 620), label) + 8

    _t(d, (x, H - 34), "Low-fidelity wireframe · generated from the requirement set", size=10,
       fill=(170, 182, 196))

    img = img.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
