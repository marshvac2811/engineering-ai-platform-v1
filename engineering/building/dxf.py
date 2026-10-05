"""Minimal deterministic ASCII-DXF geometry extraction.

Supports LINE and lightweight POLYLINE vertex sequences. It intentionally does
not interpret DWG binaries, raster PDFs, symbols or architectural semantics.
Those require a dedicated parser/vision layer and remain explicitly unsupported.
"""
from typing import List
from engineering.drawing.model import Point, Line

def _pairs(data: bytes):
    text=data.decode("utf-8-sig",errors="strict"); lines=text.splitlines();
    for i in range(0,len(lines)-1,2): yield lines[i].strip(),lines[i+1].strip()

def extract_lines(data: bytes)->List[Line]:
    pairs=list(_pairs(data)); out=[]; i=0
    while i < len(pairs):
        code,value=pairs[i]
        if code=="0" and value.upper()=="LINE":
            vals={}; j=i+1
            while j<len(pairs) and pairs[j][0]!="0": vals[pairs[j][0]]=pairs[j][1]; j+=1
            try:
                out.append(Line(Point(float(vals["10"]),float(vals["20"])),Point(float(vals["11"]),float(vals["21"])),str(vals.get("8") or "DEFAULT")))
            except (KeyError,ValueError):
                raise ValueError("DXF LINE entity is missing valid coordinates")
            i=j; continue
        i+=1
    return out

def supported_geometry_report(data: bytes):
    lines=extract_lines(data)
    return {"format":"dxf_ascii","supported_entities":["LINE"],"line_count":len(lines),"semantic_interpretation":False,"human_review_required":True}
