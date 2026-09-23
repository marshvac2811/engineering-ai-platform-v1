from pathlib import Path
from dataclasses import asdict
import ast
import re
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skill_framework.skill_definition import (
    SkillDefinition,
    InputDefinition,
    ReviewDefinition,
    definition_from_dict,
    validate_definition_dict,
)
from skill_framework.registry import load_skill_registry

REGISTRY = ROOT / "skill_registry" / "registry.yaml"
SKILLS_ROOT = ROOT / "skills"
OUT = ROOT / "skill_framework" / "mapped_definitions.py"


def files_for_skill(skill_id):
    token = skill_id.lower()
    result = []

    for path in SKILLS_ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix().lower()
        text = path.read_text(encoding="utf-8", errors="ignore").lower()

        if token in rel or token in text:
            result.append(path)

    return sorted(set(result))


def seg(source, node):
    return (ast.get_source_segment(source, node) or "").strip()


def call_name(node):
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def extract(skill_id):
    result = {
        "inputs": [],
        "conditionals": [],
        "validations": [],
        "outputs": [],
        "review": [],
        "governance": [],
        "files": [],
    }

    seen = set()

    for path in files_for_skill(skill_id):
        rel = path.relative_to(ROOT).as_posix()
        result["files"].append(rel)
        source = path.read_text(encoding="utf-8", errors="ignore")

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):

            if isinstance(node, ast.Subscript):
                text = seg(source, node)

                if "inputs" in text.lower():
                    key = ("input", rel, node.lineno, text)

                    if key not in seen:
                        seen.add(key)
                        result["inputs"].append(
                            {
                                "file": rel,
                                "line": node.lineno,
                                "expression": text,
                                "classification": "EVIDENCE_NEEDS_REVIEW",
                            }
                        )

            if isinstance(node, ast.Call):
                name = call_name(node)
                text = seg(source, node)
                low = text.lower()

                if (
                    name == "get"
                    and isinstance(node.func, ast.Attribute)
                    and "inputs" in seg(
                        source,
                        node.func.value,
                    ).lower()
                ):
                    key = ("get", rel, node.lineno, text)

                    if key not in seen:
                        seen.add(key)

                        result["inputs"].append(
                            {
                                "file": rel,
                                "line": node.lineno,
                                "expression": text,
                                "classification": "OPTIONAL_OR_DEFAULTED",
                            }
                        )

                if name in {
                    "require_positive",
                    "require_non_negative",
                    "require_enum",
                    "validate",
                    "_validate",
                }:
                    result["validations"].append(
                        {
                            "file": rel,
                            "line": node.lineno,
                            "expression": text,
                            "classification": name.upper(),
                        }
                    )

                if name == "SkillResult":
                    fields = [
                        kw.arg
                        for kw in node.keywords
                        if kw.arg
                    ]

                    result["outputs"].append(
                        {
                            "file": rel,
                            "line": node.lineno,
                            "fields": fields,
                            "classification": "SOURCE_CONFIRMED",
                        }
                    )

                if "human_review" in low:
                    result["review"].append(
                        {
                            "file": rel,
                            "line": node.lineno,
                            "expression": text,
                            "classification": "SOURCE_CONFIRMED",
                        }
                    )

                if any(
                    token in low
                    for token in (
                        "assumption",
                        "standard",
                        "governance",
                        "source_revision",
                    )
                ):
                    result["governance"].append(
                        {
                            "file": rel,
                            "line": node.lineno,
                            "expression": text,
                            "classification": "EVIDENCE_NEEDS_REVIEW",
                        }
                    )

            if isinstance(node, ast.If):
                condition = seg(source, node.test)

                if (
                    "input" in condition.lower()
                    or "inputs" in condition.lower()
                ):
                    result["conditionals"].append(
                        {
                            "file": rel,
                            "line": node.lineno,
                            "condition": condition,
                            "classification": "CONDITIONAL_NEEDS_REVIEW",
                        }
                    )

    return result


def dedupe(items):
    seen = set()
    out = []

    for item in items:
        key = repr(item)

        if key not in seen:
            seen.add(key)
            out.append(item)

    return out


def make_definition(skill):
    evidence = extract(skill.skill_id)

    # IMPORTANT:
    # Only identity metadata is mapped automatically.
    # Engineering inputs are represented as evidence-backed candidates
    # rather than being guessed into required/optional contracts.
    definition = {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "domain": skill.domain,
        "purpose": skill.purpose,
        "version": skill.version,
        "classification": skill.classification,
        "integration_status": skill.integration_status,
        "executable": skill.executable,
        "execution_type": skill.execution_type,
        "implementation_binding": skill.implementation_binding,
        "required_inputs": [],
        "optional_inputs": [],
        "conditional_inputs": [],
        "standards": [],
        "assumptions": [],
        "validation_rules": [],
        "warning_rules": [],
        "perfection_filter_rules": [],
        "review": {
            "required": False,
            "roles": [],
            "conditions": [],
        },
        "output_fields": [],
        "audit_fields": [],
        "source_revision": skill.source_revision,
    }

    # Explicitly preserve known review evidence without inventing roles.
    if evidence["review"]:
        definition["review"]["required"] = True
        definition["review"]["conditions"] = [
            {
                "file": x["file"],
                "line": x["line"],
                "evidence": x["expression"],
            }
            for x in dedupe(evidence["review"])
        ]

    # Existing SkillResult field names are safe output evidence.
    output_fields = []

    for item in evidence["outputs"]:
        for field in item["fields"]:
            if field and field not in output_fields:
                output_fields.append(field)

    definition["output_fields"] = output_fields

    # Existing validation helper calls are preserved as auditable rules.
    definition["validation_rules"] = [
        {
            "type": x["classification"],
            "file": x["file"],
            "line": x["line"],
            "evidence": x["expression"],
            "status": "SOURCE_CONFIRMED",
        }
        for x in dedupe(evidence["validations"])
    ]

    # No engineering standard/assumption is promoted automatically.
    # This prevents source-text matches from becoming authoritative data.
    return definition, evidence


def emit_python(definitions):
    lines = [
        '"""Evidence-backed SkillDefinition mappings.',
        "",
        "Generated by Step 32.",
        "Only source-confirmed identity, review, validation and output",
        "metadata are mapped automatically.",
        "Engineering input contracts remain intentionally unresolved",
        "until explicitly verified from implementation evidence.",
        '"""',
        "",
        "from .skill_definition import definition_from_dict",
        "",
        "",
        "MAPPED_DEFINITIONS = {",
    ]

    for skill_id, definition in definitions.items():
        lines.append(f"    {skill_id!r}: definition_from_dict(")
        lines.append(repr(definition))
        lines.append("    ),")

    lines.extend(
        [
            "}",
            "",
            "",
            "def get_mapped_definition(skill_id):",
            "    return MAPPED_DEFINITIONS.get(skill_id)",
            "",
            "",
            "def mapped_skill_ids():",
            "    return tuple(sorted(MAPPED_DEFINITIONS))",
            "",
        ]
    )

    OUT.write_text("\n".join(lines), encoding="utf-8")


def main():
    registry = load_skill_registry(REGISTRY)

    assert len(registry.skill_ids) == 22
    assert len(registry.executable_ids) == 21
    assert registry.pending_ids == ["chiller_efficiency"]

    definitions = {}
    evidence_counts = {}

    for skill_id in registry.executable_ids:
        skill = registry.get(skill_id)
        data, evidence = make_definition(skill)

        validate_definition_dict(data)
        mapped = definition_from_dict(data)

        assert mapped.skill_id == skill_id
        assert mapped.name == skill.name
        assert mapped.domain == skill.domain
        assert mapped.executable is True

        definitions[skill_id] = data

        evidence_counts[skill_id] = {
            "inputs": len(dedupe(evidence["inputs"])),
            "conditionals": len(dedupe(evidence["conditionals"])),
            "validations": len(dedupe(evidence["validations"])),
            "outputs": len(dedupe(evidence["outputs"])),
            "review": len(dedupe(evidence["review"])),
            "governance": len(dedupe(evidence["governance"])),
        }

    assert len(definitions) == 21

    # The pending skill must not be promoted into executable mappings.
    assert "chiller_efficiency" not in definitions

    emit_python(definitions)

    # Import generated module and validate every mapping.

    from skill_framework import mapped_definitions as module

    assert len(module.MAPPED_DEFINITIONS) == 21
    assert set(module.MAPPED_DEFINITIONS) == set(
        registry.executable_ids
    )

    report = ROOT / (
        "STEP32_EVIDENCE_BACKED_MAPPING_"
        f"{datetime.now():%Y%m%d_%H%M%S}.txt"
    )

    lines = []
    lines.append("STEP 32 - EVIDENCE-BACKED SKILLDEFINITION MAPPING")
    lines.append("=" * 120)
    lines.append("")
    lines.append(
        "Mapping policy: do not invent engineering requirements."
    )
    lines.append(
        "Only source-confirmed identity/review/validation/output metadata"
    )
    lines.append(
        "is mapped automatically. Ambiguous engineering input contracts"
    )
    lines.append(
        "remain unresolved for subsequent controlled mapping."
    )
    lines.append("")

    for skill_id in registry.executable_ids:
        data = definitions[skill_id]
        counts = evidence_counts[skill_id]

        lines.append("-" * 120)
        lines.append(skill_id)
        lines.append(f"  name                : {data['name']}")
        lines.append(f"  domain              : {data['domain']}")
        lines.append(f"  executable          : {data['executable']}")
        lines.append(
            f"  implementation_bind : "
            f"{data['implementation_binding'] or 'UNRESOLVED'}"
        )
        lines.append(
            f"  required_inputs     : {len(data['required_inputs'])}"
        )
        lines.append(
            f"  optional_inputs     : {len(data['optional_inputs'])}"
        )
        lines.append(
            f"  conditional_inputs  : {len(data['conditional_inputs'])}"
        )
        lines.append(
            f"  validation_rules    : {len(data['validation_rules'])}"
        )
        lines.append(
            f"  output_fields       : {len(data['output_fields'])}"
        )
        lines.append(
            f"  review_required     : {data['review']['required']}"
        )
        lines.append(
            f"  source input evidence: {counts['inputs']}"
        )
        lines.append(
            f"  conditional evidence : {counts['conditionals']}"
        )
        lines.append(
            f"  governance evidence  : {counts['governance']}"
        )

    lines.append("")
    lines.append("=" * 120)
    lines.append("GLOBAL VERIFICATION")
    lines.append("=" * 120)
    lines.append(f"Registry total       : {len(registry.skill_ids)}")
    lines.append(f"Executable registry  : {len(registry.executable_ids)}")
    lines.append(f"Mapped definitions   : {len(definitions)}")
    lines.append(f"Pending registry     : {registry.pending_ids}")
    lines.append("")
    lines.append(
        "Pending skill excluded: chiller_efficiency"
    )
    lines.append(
        "Existing engineering implementations modified: NO"
    )
    lines.append(
        "Existing orchestrator modified: NO"
    )
    lines.append(
        "Registry YAML modified: NO"
    )
    lines.append("")
    lines.append(
        "IMPORTANT: Empty required/optional/conditional input sections do"
    )
    lines.append(
        "not mean the engineering skill has no inputs. They mean Step 32"
    )
    lines.append(
        "has not promoted ambiguous source evidence into an authoritative"
    )
    lines.append(
        "contract."
    )

    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"Mapping module : {OUT}")
    print(f"Report         : {report}")
    print("")
    print("=== STEP 32 VERIFICATION ===")
    print(f"Registry total      : {len(registry.skill_ids)}")
    print(f"Executable registry : {len(registry.executable_ids)}")
    print(f"Mapped definitions  : {len(definitions)}")
    print(f"Pending             : {registry.pending_ids}")
    print("")
    print("Existing engineering implementations modified: NO")
    print("Existing orchestrator modified: NO")
    print("Registry YAML modified: NO")
    print("")
    print("STEP 32 MAPPING: PASS")


if __name__ == "__main__":
    main()


