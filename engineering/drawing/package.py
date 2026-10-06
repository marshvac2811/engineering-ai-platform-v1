"""Controlled drawing-package manifest and hashes."""
import hashlib, json
from typing import Iterable, Dict, Any
from .export import drawing_to_json, drawing_to_svg

def sha256_text(value:str)->str: return hashlib.sha256(value.encode("utf-8")).hexdigest()

def build_drawing_package(drawings:Iterable, *, source_hashes:Dict[str,str]|None=None, conflicts=None)->Dict[str,Any]:
    drawings=list(drawings); conflicts=list(conflicts or [])
    artifacts=[]
    drawing_payloads=[]
    drawing_svgs={}
    for d in drawings:
        payload=drawing_to_json(d); svg=drawing_to_svg(d)
        drawing_payloads.append(json.loads(payload))
        drawing_svgs[d.drawing_id]=svg
        artifacts.append({"drawing_id":d.drawing_id,"revision":d.revision,"status":d.status,"discipline":d.discipline,"floor_id":d.floor_id,"json_sha256":sha256_text(payload),"svg_sha256":sha256_text(svg),"source_calculations":sorted({o.source_calculation for o in d.objects if o.source_calculation}),"human_review_required":True})
    manifest={"package_type":"preliminary_engineering_drawing_package","status":"preliminary","human_review_required":True,"source_hashes":dict(source_hashes or {}),"drawings":artifacts,"drawing_payloads":drawing_payloads,"drawing_svgs":drawing_svgs,"coordination":{"conflict_count":len(conflicts),"unresolved_count":sum(1 for c in conflicts if getattr(c,"status","open")!="resolved"),"review_required":bool(conflicts)},"governance":"Not a statutory/construction approval; qualified engineer review required."}
    manifest["manifest_sha256"]=sha256_text(json.dumps(manifest,sort_keys=True,separators=(",",":")))
    return manifest
