from pathlib import Path
import ast
import re
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skill_framework.registry import load_skill_registry

REGISTRY = ROOT / "skill_registry" / "registry.yaml"
SKILLS_ROOT = ROOT / "skills"


def files_for_skill(skill_id):
    result = []
    token = skill_id.lower()

    for path in SKILLS_ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix().lower()
        text = path.read_text(encoding="utf-8", errors="ignore").lower()

        if token in rel or token in text:
            result.append(path)

    return sorted(set(result))


def segment(source, node):
    return (ast.get_source_segment(source, node) or "").strip()


def call_name(node):
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def literal_value(node):
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = []
        for item in node.elts:
            value = literal_value(item)
            if value is not None:
                values.append(value)
        return values

    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values):
            k = literal_value(key)
            v = literal_value(value)
            if k is not None:
                result[k] = v
        return result

    return None


def extract_skill(skill_id):
    evidence = {
        "files": [],
        "input_access": [],
        "get_access": [],
        "validation_calls": [],
        "conditionals": [],
        "defaults": [],
        "enums": [],
        "outputs": [],
        "review": [],
        "governance": [],
        "function_signatures": [],
        "source_lines": [],
    }

    for path in files_for_skill(skill_id):
        rel = path.relative_to(ROOT).as_posix()
        evidence["files"].append(rel)

        source = path.read_text(encoding="utf-8", errors="ignore")

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            evidence["source_lines"].append(
                (rel, 0, f"PARSE_ERROR: {exc}")
            )
            continue

        lines = source.splitlines()

        for node in ast.walk(tree):

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [
                    a.arg
                    for a in node.args.args
                    if a.arg != "self"
                ]

                if args:
                    evidence["function_signatures"].append(
                        {
                            "file": rel,
                            "line": node.lineno,
                            "name": node.name,
                            "args": args,
                        }
                    )

            if isinstance(node, ast.Subscript):
                text = segment(source, node)

                if "inputs" in text.lower():
                    evidence["input_access"].append(
                        (rel, node.lineno, text)
                    )

            if isinstance(node, ast.Call):
                name = call_name(node)
                text = segment(source, node)

                if (
                    name == "get"
                    and isinstance(node.func, ast.Attribute)
                    and "inputs" in segment(source, node.func.value).lower()
                ):
                    evidence["get_access"].append(
                        (rel, node.lineno, text)
                    )

                    if len(node.args) >= 2:
                        default = literal_value(node.args[1])
                        evidence["defaults"].append(
                            (rel, node.lineno, text, default)
                        )

                if name in {
                    "require_positive",
                    "require_non_negative",
                    "require_enum",
                    "validate",
                    "_validate",
                }:
                    evidence["validation_calls"].append(
                        (rel, node.lineno, text)
                    )

                if name == "SkillResult":
                    fields = {}

                    for kw in node.keywords:
                        if kw.arg:
                            fields[kw.arg] = segment(
                                source,
                                kw.value,
                            )

                    evidence["outputs"].append(
                        (rel, node.lineno, fields)
                    )

                if "human_review" in text.lower():
                    evidence["review"].append(
                        (rel, node.lineno, text)
                    )

                low = text.lower()

                if any(
                    token in low
                    for token in (
                        "assumption",
                        "standard",
                        "governance",
                        "source_revision",
                    )
                ):
                    evidence["governance"].append(
                        (rel, node.lineno, text)
                    )

            if isinstance(node, ast.If):
                test = segment(source, node.test)

                if "input" in test.lower() or "inputs" in test.lower():
                    evidence["conditionals"].append(
                        (rel, node.lineno, test)
                    )

            if isinstance(node, ast.Assign):
                target = ", ".join(
                    segment(source, t)
                    for t in node.targets
                )

                value = literal_value(node.value)

                if isinstance(value, list) and value:
                    # Only record lists as candidate enums.
                    evidence["enums"].append(
                        (rel, node.lineno, target, value)
                    )

            if hasattr(node, "lineno"):
                line_no = node.lineno

                if 0 < line_no <= len(lines):
                    line = lines[line_no - 1].strip()

                    # Keep only lines that contain contract-relevant
                    # vocabulary. This avoids treating every source line
                    # as engineering evidence.
                    if re.search(
                        r"\b(inputs?|validate|required|optional|"
                        r"human_review|SkillResult|assumption|standard|"
                        r"source_revision|positive|non.?negative|enum|"
                        r"minimum|maximum|range|limit|velocity|pressure|"
                        r"flow|capacity|load|area|temperature|efficiency)\b",
                        line,
                        re.IGNORECASE,
                    ):
                        evidence["source_lines"].append(
                            (rel, line_no, line)
                        )

    return evidence


def classify_input_expression(expr):
    low = expr.lower()

    if ".get(" in low:
        return "OPTIONAL_OR_DEFAULTED"

    if "[" in expr and "inputs" in low:
        return "EXPLICIT_INPUT_ACCESS"

    return "INPUT_EVIDENCE_NEEDS_REVIEW"


def classify_validation(expr):
    low = expr.lower()

    if "require_positive" in low:
        return "RANGE_POSITIVE"

    if "require_non_negative" in low:
        return "RANGE_NON_NEGATIVE"

    if "require_enum" in low:
        return "ENUM_ALLOWED_VALUES"

    return "VALIDATION_NEEDS_REVIEW"


def build_mapping(skill_id, definition, evidence):
    mapping = {
        "skill_id": skill_id,
        "name": definition.name,
        "domain": definition.domain,
        "identity_status": "SOURCE_CONFIRMED",
        "input_candidates": [],
        "conditional_candidates": [],
        "validation_candidates": [],
        "enum_candidates": [],
        "output_candidates": [],
        "review_candidates": [],
        "governance_candidates": [],
        "needs_review": [],
    }

    seen = set()

    for rel, line, expr in (
        evidence["input_access"] + evidence["get_access"]
    ):
        key = (rel, line, expr)

        if key in seen:
            continue

        seen.add(key)

        mapping["input_candidates"].append(
            {
                "file": rel,
                "line": line,
                "evidence": expr,
                "classification": classify_input_expression(expr),
            }
        )

    for rel, line, expr in evidence["conditionals"]:
        mapping["conditional_candidates"].append(
            {
                "file": rel,
                "line": line,
                "condition": expr,
                "classification": "CONDITIONAL_NEEDS_REVIEW",
            }
        )

    for rel, line, expr in evidence["validation_calls"]:
        mapping["validation_candidates"].append(
            {
                "file": rel,
                "line": line,
                "evidence": expr,
                "classification": classify_validation(expr),
            }
        )

    for rel, line, target, values in evidence["enums"]:
        mapping["enum_candidates"].append(
            {
                "file": rel,
                "line": line,
                "target": target,
                "values": values,
                "classification": "ENUM_CANDIDATE_NEEDS_REVIEW",
            }
        )

    for rel, line, fields in evidence["outputs"]:
        mapping["output_candidates"].append(
            {
                "file": rel,
                "line": line,
                "fields": fields,
                "classification": "OUTPUT_SOURCE_CONFIRMED",
            }
        )

    for rel, line, expr in evidence["review"]:
        mapping["review_candidates"].append(
            {
                "file": rel,
                "line": line,
                "evidence": expr,
                "classification": "REVIEW_SOURCE_CONFIRMED",
            }
        )

    for rel, line, expr in evidence["governance"]:
        mapping["governance_candidates"].append(
            {
                "file": rel,
                "line": line,
                "evidence": expr,
                "classification": "GOVERNANCE_EVIDENCE_NEEDS_REVIEW",
            }
        )

    # Explicitly prevent unsupported inference.
    if not mapping["input_candidates"]:
        mapping["needs_review"].append(
            "No direct request.inputs evidence found; inspect constructor/"
            "calculator/data-structure contracts before defining inputs."
        )

    if not mapping["validation_candidates"]:
        mapping["needs_review"].append(
            "No explicit validation helper evidence found."
        )

    if not mapping["output_candidates"]:
        mapping["needs_review"].append(
            "No SkillResult output evidence found."
        )

    if not mapping["governance_candidates"]:
        mapping["needs_review"].append(
            "No direct governance/assumption/standard evidence found."
        )

    mapping["needs_review"].append(
        "Do not infer required/optional status from variable names alone."
    )
    mapping["needs_review"].append(
        "Do not infer units, standards, engineering limits or constants "
        "unless supported by source evidence."
    )
    mapping["needs_review"].append(
        "Do not populate missing SkillDefinition fields with invented "
        "engineering information."
    )

    return mapping


def main():
    registry = load_skill_registry(REGISTRY)

    assert len(registry.skill_ids) == 22
    assert len(registry.executable_ids) == 21
    assert registry.pending_ids == ["chiller_efficiency"]

    report = ROOT / (
        "STEP32A_CONTRACT_MAPPING_AUDIT_"
        f"{datetime.now():%Y%m%d_%H%M%S}.txt"
    )

    lines = []
    lines.append("STEP 32A - CONTRACT MAPPING DESIGN / AUDIT")
    lines.append("=" * 125)
    lines.append("")
    lines.append(
        "PURPOSE: Convert source evidence into a proposed mapping plan."
    )
    lines.append(
        "STATUS: AUDIT/DESIGN ONLY - NO SkillDefinition mapping is written."
    )
    lines.append("")
    lines.append(
        "IMPORTANT: Evidence is not automatically treated as an authoritative"
    )
    lines.append(
        "engineering contract. Ambiguous evidence is explicitly marked."
    )
    lines.append("")

    total_files = 0
    total_input = 0
    total_validation = 0
    total_conditional = 0
    total_outputs = 0
    total_review = 0
    total_governance = 0

    for index, skill_id in enumerate(registry.executable_ids, 1):
        definition = registry.get(skill_id)
        evidence = extract_skill(skill_id)
        mapping = build_mapping(
            skill_id,
            definition,
            evidence,
        )

        total_files += len(evidence["files"])
        total_input += len(mapping["input_candidates"])
        total_validation += len(mapping["validation_candidates"])
        total_conditional += len(mapping["conditional_candidates"])
        total_outputs += len(mapping["output_candidates"])
        total_review += len(mapping["review_candidates"])
        total_governance += len(mapping["governance_candidates"])

        lines.append("=" * 125)
        lines.append(
            f"{index:02d}. {skill_id} | {definition.name}"
        )
        lines.append(
            f"Domain: {definition.domain}"
        )
        lines.append("")

        lines.append("SOURCE FILES")
        for item in evidence["files"]:
            lines.append(f"  - {item}")

        lines.append("")
        lines.append("INPUT CANDIDATES")
        if mapping["input_candidates"]:
            for item in mapping["input_candidates"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"[{item['classification']}] "
                    f"{item['evidence']}"
                )
        else:
            lines.append("  - NONE")

        lines.append("")
        lines.append("CONDITIONAL CANDIDATES")
        if mapping["conditional_candidates"]:
            for item in mapping["conditional_candidates"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"[{item['classification']}] "
                    f"{item['condition']}"
                )
        else:
            lines.append("  - NONE")

        lines.append("")
        lines.append("VALIDATION CANDIDATES")
        if mapping["validation_candidates"]:
            for item in mapping["validation_candidates"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"[{item['classification']}] "
                    f"{item['evidence']}"
                )
        else:
            lines.append("  - NONE")

        lines.append("")
        lines.append("ENUM CANDIDATES")
        if mapping["enum_candidates"]:
            for item in mapping["enum_candidates"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['target']} = {item['values']} "
                    f"[{item['classification']}]"
                )
        else:
            lines.append("  - NONE")

        lines.append("")
        lines.append("OUTPUT CANDIDATES")
        if mapping["output_candidates"]:
            for item in mapping["output_candidates"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"[{item['classification']}]"
                )

                for field, value in item["fields"].items():
                    lines.append(
                        f"      {field} = {value}"
                    )
        else:
            lines.append("  - NONE")

        lines.append("")
        lines.append("HUMAN REVIEW CANDIDATES")
        if mapping["review_candidates"]:
            for item in mapping["review_candidates"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"[{item['classification']}] "
                    f"{item['evidence']}"
                )
        else:
            lines.append("  - NONE")

        lines.append("")
        lines.append("GOVERNANCE CANDIDATES")
        if mapping["governance_candidates"]:
            for item in mapping["governance_candidates"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"[{item['classification']}] "
                    f"{item['evidence']}"
                )
        else:
            lines.append("  - NONE")

        lines.append("")
        lines.append("MANDATORY REVIEW NOTES")
        for item in mapping["needs_review"]:
            lines.append(f"  - {item}")

    lines.append("")
    lines.append("=" * 125)
    lines.append("STEP 32A GLOBAL SUMMARY")
    lines.append("=" * 125)
    lines.append(f"Registry skills       : {len(registry.skill_ids)}")
    lines.append(f"Executable skills     : {len(registry.executable_ids)}")
    lines.append(f"Pending skills        : {registry.pending_ids}")
    lines.append(f"Source files observed : {total_files}")
    lines.append(f"Input candidates      : {total_input}")
    lines.append(f"Validation candidates : {total_validation}")
    lines.append(f"Conditional candidates: {total_conditional}")
    lines.append(f"Output candidates     : {total_outputs}")
    lines.append(f"Review candidates     : {total_review}")
    lines.append(f"Governance candidates : {total_governance}")
    lines.append("")
    lines.append(
        "NEXT STEP: Use this evidence map to build SkillDefinition contracts."
    )
    lines.append(
        "Ambiguous fields must remain NEEDS_REVIEW until confirmed from source."
    )
    lines.append("")
    lines.append(
        "NO SOURCE ENGINEERING IMPLEMENTATIONS WERE MODIFIED."
    )

    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"Report: {report}")
    print("")
    print("=== STEP 32A GLOBAL SUMMARY ===")
    print(f"Registry skills       : {len(registry.skill_ids)}")
    print(f"Executable skills     : {len(registry.executable_ids)}")
    print(f"Pending skills        : {registry.pending_ids}")
    print(f"Source files observed : {total_files}")
    print(f"Input candidates      : {total_input}")
    print(f"Validation candidates : {total_validation}")
    print(f"Conditional candidates: {total_conditional}")
    print(f"Output candidates     : {total_outputs}")
    print(f"Review candidates     : {total_review}")
    print(f"Governance candidates : {total_governance}")
    print("")
    print("No SkillDefinition contracts were modified.")
    print("No engineering implementations were modified.")
    print("STEP 32A AUDIT: PASS")


if __name__ == "__main__":
    main()
