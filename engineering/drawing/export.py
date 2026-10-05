"""Deterministic JSON/SVG export for structured engineering drawings."""
import html, json
from .objects import DisciplineDrawing

def drawing_to_dict(drawing):
    return {"drawing_id":drawing.drawing_id,"title":drawing.title,"discipline":drawing.discipline,"floor_id":drawing.floor_id,"revision":drawing.revision,"status":drawing.status,"objects":[{"object_id":o.object_id,"discipline":o.discipline,"kind":o.kind,"x_mm":o.x_mm,"y_mm":o.y_mm,"floor_id":o.floor_id,"size":o.size,"source_calculation":o.source_calculation,"confidence":o.confidence,"attributes":o.attributes} for o in drawing.objects],"annotations":[{"text":a.text,"x_mm":a.x_mm,"y_mm":a.y_mm,"kind":a.kind} for a in drawing.annotations],"metadata":drawing.metadata}

def drawing_to_json(drawing): return json.dumps(drawing_to_dict(drawing),sort_keys=True,indent=2)

def drawing_to_svg(drawing, width=1200, height=800, scale=0.5):
    if drawing.validate(): raise ValueError("invalid drawing: "+"; ".join(drawing.validate()))
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',f'<text x="20" y="30">{html.escape(drawing.title)} | {html.escape(drawing.discipline)} | Rev {html.escape(drawing.revision)}</text>']
    for o in drawing.objects:
        x=20+o.x_mm*scale; y=60+o.y_mm*scale
        parts.append(f'<circle cx="{x:g}" cy="{y:g}" r="5"/><text x="{x+8:g}" y="{y+4:g}">{html.escape(o.kind)} {html.escape(o.object_id)}</text>')
    for a in drawing.annotations: parts.append(f'<text x="{20+a.x_mm*scale:g}" y="{60+a.y_mm*scale:g}">{html.escape(a.text)}</text>')
    parts.append('</svg>'); return "".join(parts)
