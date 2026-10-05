"""Normalized building-understanding primitives used by engineering design workflows."""
from .model import BuildingModel, Floor, Room, Opening, ServiceZone, SourceReference, Confidence
from .ingest import ingest_structured_layout
from .dxf import extract_lines, supported_geometry_report

__all__=["extract_lines","supported_geometry_report","BuildingModel","Floor","Room","Opening","ServiceZone","SourceReference","Confidence","ingest_structured_layout"]
