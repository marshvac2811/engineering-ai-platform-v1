"""Faint tiled watermark image (Mars monogram + name) used as the Excel sheet background."""
from __future__ import annotations
import io


def watermark_png_bytes(size: int = 360) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    from branding import brand
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = ImageDraw.Draw(img)
    tile = (238, 240, 244)   # very light grey-blue so cell text stays readable
    s = int(size * 0.34)
    x0, y0 = (size - s) // 2, int(size * 0.18)
    d.rounded_rectangle([x0, y0, x0 + s, y0 + s], radius=int(s * 0.18), fill=tile)
    w = max(3, int(s * 0.085))
    pts = [(x0 + s * 0.20, y0 + s * 0.76), (x0 + s * 0.20, y0 + s * 0.28), (x0 + s * 0.50, y0 + s * 0.60),
           (x0 + s * 0.80, y0 + s * 0.28), (x0 + s * 0.80, y0 + s * 0.76)]
    d.line(pts, fill=(255, 255, 255), width=w, joint="curve")
    r = s * 0.095
    cx, cy = x0 + s * 0.76, y0 + s * 0.20
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 232, 228))
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(size * 0.042))
    except Exception:
        font = ImageFont.load_default()
    text = brand()["name"].upper()
    tw = d.textlength(text, font=font)
    d.text(((size - tw) / 2, y0 + s + int(size * 0.07)), text, fill=tile, font=font)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
