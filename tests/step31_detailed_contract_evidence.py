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


def skill_files(skill_id):
    files = []

    for path in SKILLS_ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix().lower()
        text = path.read_text(encoding="utf-8", errors="ignore").lower()

        if skill_id.lower() in rel or skill_id.lower() in text:
            files.append(path)

    return sorted(set(files))


def source_segment(source, node):
    return ast.get_source_segment(source, node) or ""


def call_name(node):
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def expression_text(source, node):
    return source_segment(source, node).strip()


def inspect_source(path):
    source = path.read_text(encoding="utf-8", errors="ignore")

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "error": str(exc),
            "inputs": [],
            "validations": [],
            "outputs": [],
            "enums": [],
            "units": [],
            "defaults": [],
            "conditionals": [],
            "reviews": [],
            "governance": [],
        }

    inputs = []
    validations = []
    outputs = []
    enums = []
    units = []
    defaults = []
    conditionals = []
    reviews = []
    governance = []

    for node in ast.walk(tree):

        # request.inputs["field"]
        if isinstance(node, ast.Subscript):
            text = expression_text(source, node)

            if "inputs" in text.lower():
                inputs.append(
                    {
                        "line": node.lineno,
                        "expression": text,
                        "kind": "input_access",
                    }
                )

        # inputs.get("field", default)
        if isinstance(node, ast.Call):
            fn = call_name(node)

            if fn == "get" and node.args:
                parent = node.func.value if isinstance(node.func, ast.Attribute) else None
                if parent is not None:
                    parent_text = expression_text(source, parent)
                    if "inputs" in parent_text.lower():
                        inputs.append(
                            {
                                "line": node.lineno,
                                "expression": expression_text(source, node),
                                "kind": "input_get",
                            }
                        )

            # validation helper calls
            if fn in {
                "require_positive",
                "require_non_negative",
                "require_enum",
                "require",
                "validate",
                "_validate",
            }:
                validations.append(
                    {
                        "line": node.lineno,
                        "function": fn,
                        "expression": expression_text(source, node),
                    }
                )

            # SkillResult
            if fn == "SkillResult":
                fields = []
                for kw in node.keywords:
                    if kw.arg:
                        fields.append(
                            {
                                "field": kw.arg,
                                "value": expression_text(source, kw.value),
                            }
                        )

                outputs.append(
                    {
                        "line": node.lineno,
                        "fields": fields,
                    }
                )

            # review flags
            if "human_review" in expression_text(source, node).lower():
                reviews.append(
                    {
                        "line": node.lineno,
                        "expression": expression_text(source, node),
                    }
                )

            # governance / assumptions / standards
            call_text = expression_text(source, node).lower()

            if any(
                word in call_text
                for word in (
                    "assumption",
                    "standard",
                    "governance",
                    "override",
                    "source_revision",
                )
            ):
                governance.append(
                    {
                        "line": node.lineno,
                        "expression": expression_text(source, node),
                    }
                )

        # Assignment defaults:
        # x = inputs.get(...)
        if isinstance(node, ast.Assign):
            value_text = expression_text(source, node.value)

            if "inputs.get(" in value_text.lower():
                targets = [
                    expression_text(source, target)
                    for target in node.targets
                ]

                defaults.append(
                    {
                        "line": node.lineno,
                        "targets": targets,
                        "expression": expression_text(source, node),
                    }
                )

        # Conditional blocks involving inputs
        if isinstance(node, ast.If):
            test = expression_text(source, node.test)

            if "input" in test.lower() or "inputs" in test.lower():
                conditionals.append(
                    {
                        "line": node.lineno,
                        "condition": test,
                    }
                )

        # Literal lists / tuples associated with enum-like names
        if isinstance(node, ast.Assign):
            target_text = ", ".join(
                expression_text(source, target)
                for target in node.targets
            )

            if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                values = []

                for item in node.value.elts:
                    if isinstance(item, ast.Constant):
                        values.append(item.value)

                if values:
                    enums.append(
                        {
                            "line": node.lineno,
                            "target": target_text,
                            "values": values,
                        }
                    )

        # Unit-bearing strings in source.
        text_line = ""
        if hasattr(node, "lineno"):
            lines = source.splitlines()
            if 0 < node.lineno <= len(lines):
                text_line = lines[node.lineno - 1]

        if text_line:
            for unit in (
                "kg/m3",
                "kg/m³",
                "m3/s",
                "m³/s",
                "m2/s",
                "m²/s",
                "Pa.s",
                "Pa",
                "kW",
                "kWh",
                "kWh/yr",
                "TR",
                "sqft",
                "ft2",
                "mm",
                "%",
                "C",
                "°C",
                "bar",
            ):
                if unit.lower() in text_line.lower():
                    units.append(
                        {
                            "line": node.lineno,
                            "unit": unit,
                            "text": text_line.strip(),
                        }
                    )

    return {
        "error": None,
        "inputs": inputs,
        "validations": validations,
        "outputs": outputs,
        "enums": enums,
        "units": units,
        "defaults": defaults,
        "conditionals": conditionals,
        "reviews": reviews,
        "governance": governance,
    }


def inspect_skill(skill_id):
    aggregate = {
        "files": [],
        "inputs": [],
        "validations": [],
        "outputs": [],
        "enums": [],
        "units": [],
        "defaults": [],
        "conditionals": [],
        "reviews": [],
        "governance": [],
        "errors": [],
    }

    for path in skill_files(skill_id):
        rel = path.relative_to(ROOT).as_posix()
        aggregate["files"].append(rel)

        info = inspect_source(path)

        if info["error"]:
            aggregate["errors"].append(
                f"{rel}: {info['error']}"
            )
            continue

        for key in (
            "inputs",
            "validations",
            "outputs",
            "enums",
            "units",
            "defaults",
            "conditionals",
            "reviews",
            "governance",
        ):
            for item in info[key]:
                item = dict(item)
                item["file"] = rel
                aggregate[key].append(item)

    return aggregate


def unique_items(items, key_fields):
    seen = set()
    result = []

    for item in items:
        key = tuple(
            repr(item.get(field))
            for field in key_fields
        )

        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def main():
    registry = load_skill_registry(REGISTRY)

    assert len(registry.skill_ids) == 22
    assert len(registry.executable_ids) == 21
    assert registry.pending_ids == ["chiller_efficiency"]

    report = ROOT / (
        f"STEP31_DETAILED_CONTRACT_EVIDENCE_"
        f"{datetime.now():%Y%m%d_%H%M%S}.txt"
    )

    lines = []
    lines.append("STEP 31 - DETAILED CONTRACT EVIDENCE EXTRACTION")
    lines.append("=" * 125)
    lines.append("SOURCE OF TRUTH: EXISTING EXECUTABLE SKILL IMPLEMENTATIONS")
    lines.append("")
    lines.append(
        "This report is evidence only. It does not create or infer missing"
    )
    lines.append(
        "engineering requirements, standards, assumptions, limits or formulas."
    )
    lines.append("")

    summary = []

    for number, skill_id in enumerate(registry.executable_ids, 1):
        skill = registry.get(skill_id)
        info = inspect_skill(skill_id)

        inputs = unique_items(
            info["inputs"],
            ("expression", "kind"),
        )
        validations = unique_items(
            info["validations"],
            ("function", "expression"),
        )
        outputs = unique_items(
            info["outputs"],
            ("line", "fields"),
        )
        conditionals = unique_items(
            info["conditionals"],
            ("condition",),
        )
        defaults = unique_items(
            info["defaults"],
            ("expression",),
        )
        enums = unique_items(
            info["enums"],
            ("target", "values"),
        )
        units = unique_items(
            info["units"],
            ("unit", "text"),
        )
        reviews = unique_items(
            info["reviews"],
            ("expression",),
        )
        governance = unique_items(
            info["governance"],
            ("expression",),
        )

        summary.append(
            (
                skill_id,
                len(inputs),
                len(validations),
                len(conditionals),
                len(defaults),
                len(enums),
                len(units),
                len(outputs),
                len(reviews),
                len(governance),
            )
        )

        lines.append("=" * 125)
        lines.append(f"{number:02d}. {skill_id}")
        lines.append(f"Name   : {skill.name}")
        lines.append(f"Domain : {skill.domain}")
        lines.append("")

        lines.append("A. INPUT EVIDENCE")
        if inputs:
            for item in inputs:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"[{item['kind']}] {item['expression']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("B. VALIDATION EVIDENCE")
        if validations:
            for item in validations:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['expression']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("C. CONDITIONAL LOGIC")
        if conditionals:
            for item in conditionals:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['condition']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("D. DEFAULTS / OPTIONAL-BEHAVIOR EVIDENCE")
        if defaults:
            for item in defaults:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['expression']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("E. ENUM / ALLOWED-VALUE EVIDENCE")
        if enums:
            for item in enums:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['target']} = {item['values']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("F. UNIT EVIDENCE")
        if units:
            for item in units:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['unit']} | {item['text']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("G. OUTPUT / SkillResult EVIDENCE")
        if outputs:
            for item in outputs:
                lines.append(
                    f"  - {item['file']}:{item['line']}"
                )
                for field in item["fields"]:
                    lines.append(
                        f"      {field['field']} = {field['value']}"
                    )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("H. HUMAN REVIEW EVIDENCE")
        if reviews:
            for item in reviews:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['expression']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("I. GOVERNANCE / ASSUMPTION / STANDARD EVIDENCE")
        if governance:
            for item in governance:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['expression']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        if info["errors"]:
            lines.append("")
            lines.append("J. PARSE ERRORS")
            for error in info["errors"]:
                lines.append(f"  - {error}")

    lines.append("")
    lines.append("=" * 125)
    lines.append("STEP 31 SUMMARY")
    lines.append("=" * 125)
    lines.append(
        "Each row below reports source-code evidence counts only."
    )
    lines.append("")
    lines.append(
        f"{'SKILL ID':32} "
        f"{'IN':4} {'VAL':4} {'COND':5} {'DEF':4} "
        f"{'ENUM':5} {'UNIT':5} {'OUT':5} {'REV':5} {'GOV':5}"
    )
    lines.append("-" * 90)

    for row in summary:
        lines.append(
            f"{row[0]:32} "
            f"{row[1]:4} {row[2]:4} {row[3]:5} {row[4]:4} "
            f"{row[5]:5} {row[6]:5} {row[7]:5} {row[8]:5} {row[9]:5}"
        )

    lines.append("")
    lines.append(
        "No SkillDefinition objects were generated or modified by this step."
    )

    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"Report: {report}")
    print("")
    print("=== STEP 31 EVIDENCE SUMMARY ===")
    print(
        f"{'SKILL ID':32} "
        f"{'IN':4} {'VAL':4} {'COND':5} {'DEF':4} "
        f"{'ENUM':5} {'UNIT':5} {'OUT':5} {'REV':5} {'GOV':5}"
    )
    print("-" * 90)

    for row in summary:
        print(
            f"{row[0]:32} "
            f"{row[1]:4} {row[2]:4} {row[3]:5} {row[4]:4} "
            f"{row[5]:5} {row[6]:5} {row[7]:5} {row[8]:5} {row[9]:5}"
        )

    print("")
    print("Registry total :", len(registry.skill_ids))
    print("Executable     :", len(registry.executable_ids))
    print("Pending        :", registry.pending_ids)

    assert len(summary) == 21
    assert all(
        len(inspect_skill(skill_id)["files"]) > 0
        for skill_id in registry.executable_ids
    )

    print("Detailed source coverage: 21/21")
    print("STEP 31 EXTRACTION: PASS")


if __name__ == "__main__":
    main()
