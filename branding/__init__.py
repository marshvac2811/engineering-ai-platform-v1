"""Mars Engineering Solutions brand constants and logo drawing.

Everything is overridable via environment variables so the exact registered
address/contact can be set in Render without a code change:
MARS_BRAND_NAME, MARS_TAGLINE, MARS_ADDRESS, MARS_EMAIL, MARS_PHONE, MARS_WEBSITE.
"""
from __future__ import annotations
import os

NAVY = "#14233c"
RED = "#c8442b"
GOLD = "#e0a93b"


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def brand() -> dict:
    return {
        "name": _env("MARS_BRAND_NAME", "Mars Engineering Solutions"),
        "tagline": _env("MARS_TAGLINE", "HVAC • MEP • Building Services Engineering"),
        "address": _env("MARS_ADDRESS", "Delhi NCR, India"),
        "email": _env("MARS_EMAIL", "mars.hvac2811@gmail.com"),
        "phone": _env("MARS_PHONE", "+91 8887136167"),
        "website": _env("MARS_WEBSITE", ""),
    }


def footer_line() -> str:
    b = brand()
    parts = [b["name"], b["address"], b["email"], b["phone"]]
    if b["website"]:
        parts.append(b["website"])
    return "  •  ".join(p for p in parts if p)


def draw_logo(canvas, x: float, y: float, size: float, *, mono: bool = False, alpha: float | None = None) -> None:
    """Draw the Mars monogram with ReportLab at (x, y) = bottom-left, `size` points square.

    A rounded navy tile; an 'M' built from two duct-like peaks; a red disc (the planet).
    `mono=True` draws a grey, very light version intended as a page background mark.
    """
    from reportlab.lib import colors
    c = canvas
    c.saveState()
    s = size

    mark_alpha = alpha if alpha is not None else 0.09
    if mono:
        tile = colors.Color(0.30, 0.30, 0.30, alpha=0.035)
        grey = colors.Color(0.30, 0.30, 0.30, alpha=mark_alpha)
        c.setFillColor(tile)
        c.roundRect(x, y, s, s, s * 0.18, stroke=0, fill=1)
        c.setStrokeColor(grey)
        c.setFillColor(grey)
    else:
        c.setFillColor(colors.HexColor(NAVY))
        c.roundRect(x, y, s, s, s * 0.18, stroke=0, fill=1)
        c.setStrokeColor(colors.white)
    c.setLineWidth(s * 0.085)
    c.setLineJoin(1)
    c.setLineCap(1)
    p = c.beginPath()
    p.moveTo(x + s * 0.20, y + s * 0.24)
    p.lineTo(x + s * 0.20, y + s * 0.72)
    p.lineTo(x + s * 0.50, y + s * 0.40)
    p.lineTo(x + s * 0.80, y + s * 0.72)
    p.lineTo(x + s * 0.80, y + s * 0.24)
    c.drawPath(p, stroke=1, fill=0)
    if not mono:
        c.setFillColor(colors.HexColor(RED))
    c.circle(x + s * 0.76, y + s * 0.80, s * 0.095, stroke=0, fill=1)
    c.setStrokeColor(grey if mono else colors.HexColor(GOLD))
    c.setLineWidth(s * 0.045)
    c.line(x + s * 0.20, y + s * 0.13, x + s * 0.80, y + s * 0.13)
    c.restoreState()


def logo_svg(size: int = 40) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 100 100" role="img" aria-label="Mars Engineering Solutions">'
        f'<rect width="100" height="100" rx="18" fill="{NAVY}"/>'
        '<path d="M20 76V28L50 60L80 28V76" fill="none" stroke="#fff" stroke-width="8.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="76" cy="20" r="9.5" fill="{RED}"/>'
        f'<line x1="20" y1="87" x2="80" y2="87" stroke="{GOLD}" stroke-width="4.5" stroke-linecap="round"/>'
        '</svg>'
    )
