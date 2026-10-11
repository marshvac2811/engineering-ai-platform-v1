"""Add a faint tiled background picture (the Mars watermark) to every worksheet of an .xlsx."""
from __future__ import annotations
import io
import re
import zipfile

_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_BG_REL_TYPE = _REL_NS + "/image"
_MEDIA = "xl/media/mars_watermark.png"


def apply_background(xlsx_bytes: bytes, png: bytes) -> bytes:
    zin = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    names = zin.namelist()
    sheets = [n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                text = data.decode("utf-8")
                if 'Extension="png"' not in text:
                    text = text.replace("<Types ", "<Types ", 1)
                    text = re.sub(r"(<Types[^>]*>)", r'\1<Default Extension="png" ContentType="image/png"/>', text, count=1)
                data = text.encode("utf-8")
            elif item.filename in sheets:
                text = data.decode("utf-8")
                if "<picture " not in text:
                    if "xmlns:r=" not in text.split(">", 2)[1] and 'xmlns:r="' not in text[:600]:
                        text = re.sub(r"(<worksheet\b)", r'\1 xmlns:r="' + _REL_NS + '"', text, count=1)
                    tag = '<picture r:id="rIdMarsBg"/>'
                    m = re.search(r"<(oleObjects|controls|webPublishItems|tableParts|extLst)\b", text)
                    text = text[: m.start()] + tag + text[m.start():] if m else text.replace("</worksheet>", tag + "</worksheet>")
                data = text.encode("utf-8")
            elif re.fullmatch(r"xl/worksheets/_rels/sheet\d+\.xml\.rels", item.filename):
                text = data.decode("utf-8")
                if "rIdMarsBg" not in text:
                    rel = f'<Relationship Id="rIdMarsBg" Type="{_BG_REL_TYPE}" Target="../media/mars_watermark.png"/>'
                    text = text.replace("</Relationships>", rel + "</Relationships>")
                data = text.encode("utf-8")
            zout.writestr(item, data)
        # sheets that had no rels part get a new one
        for sheet in sheets:
            rels = sheet.replace("worksheets/", "worksheets/_rels/") + ".rels"
            if rels not in names:
                zout.writestr(rels, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                              '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                              f'<Relationship Id="rIdMarsBg" Type="{_BG_REL_TYPE}" Target="../media/mars_watermark.png"/></Relationships>')
        if _MEDIA not in names:
            zout.writestr(_MEDIA, png)
    return out.getvalue()
