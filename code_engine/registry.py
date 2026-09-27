from pathlib import Path
import yaml
from .models import CodeDocument, CodeRequirement, RequirementType

class CodeRegistry:
    def __init__(self, documents=None, requirements=None):
        self.documents = documents or {}
        self.requirements = requirements or {}

    @classmethod
    def from_yaml(cls, path):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        docs = {}
        reqs = {}
        for raw in data.get("standards", []):
            doc = CodeDocument(
                authority=str(raw["authority"]),
                code_name=str(raw["code_name"]),
                edition=str(raw["edition"]),
                category=str(raw.get("category","")),
                jurisdiction=str(raw.get("jurisdiction","")),
                status=str(raw.get("status","active")),
                source_url=str(raw.get("source_url","")),
                effective_from=str(raw.get("effective_from","")),
                notes=str(raw.get("notes","")),
            )
            docs[raw["id"]] = doc
            for rr in raw.get("requirements", []):
                req = CodeRequirement(
                    requirement_id=str(rr["id"]),
                    document=doc,
                    clause=str(rr["clause"]),
                    title=str(rr.get("title","")),
                    discipline=str(rr["discipline"]),
                    parameter=str(rr["parameter"]),
                    operator=str(rr["operator"]),
                    required_value=float(rr["required_value"]),
                    unit=str(rr["unit"]),
                    requirement_type=RequirementType(str(rr["requirement_type"])),
                    applicability=dict(rr.get("applicability") or {}),
                    verification_method=str(rr.get("verification_method","calculation")),
                )
                reqs[req.requirement_id] = req
        return cls(docs, reqs)

    def get_requirement(self, requirement_id):
        return self.requirements[requirement_id]
