from pathlib import Path
import ast
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skill_framework.registry import load_skill_registry


REGISTRY = ROOT / "skill_registry" / "registry.yaml"
SKILLS_ROOT = ROOT / "skills"


def source_files_for_skill(skill_id):
    found = []

    for path in SKILLS_ROOT.rglob("*.py"):
        normalized = path.as_posix().lower()
        if skill_id.lower() in normalized:
            found.append(path)

    if not found:
        for path in SKILLS_ROOT.rglob("*.py"):
            source = path.read_text(encoding="utf-8", errors="ignore")
            if skill_id.lower() in source.lower():
                found.append(path)

    return sorted(set(found))


def literal_value(node):
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = []
        for item in node.elts:
            value = literal_value(item)
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


def names_from_expression(node):
    names = []

    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.append(child.id)
        elif isinstance(child, ast.Attribute):
            names.append(child.attr)

    return sorted(set(names))


def call_name(node):
    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return ""


def inspect_file(path):
    source = path.read_text(encoding="utf-8", errors="ignore")

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "error": str(exc),
            "classes": [],
            "methods": [],
            "validate_blocks": [],
            "run_blocks": [],
            "request_access": [],
            "result_calls": [],
            "constants": [],
        }

    classes = []
    methods = []
    validate_blocks = []
    run_blocks = []
    request_access = []
    result_calls = []
    constants = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(node.name)

            if node.name in {"validate", "_validate", "validate_inputs", "_validate_inputs"}:
                validate_blocks.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "args": [
                            arg.arg
                            for arg in node.args.args
                        ],
                        "source": ast.get_source_segment(source, node) or "",
                    }
                )

            if node.name == "run":
                run_blocks.append(
                    {
                        "line": node.lineno,
                        "args": [
                            arg.arg
                            for arg in node.args.args
                        ],
                        "source": ast.get_source_segment(source, node) or "",
                    }
                )

        if isinstance(node, ast.Call):
            fn = call_name(node)

            if fn in {"SkillResult", "SkillRequest"}:
                result_calls.append(
                    {
                        "function": fn,
                        "line": node.lineno,
                        "keywords": {
                            kw.arg: ast.get_source_segment(source, kw.value)
                            for kw in node.keywords
                            if kw.arg
                        },
                    }
                )

            if fn in {
                "require_positive",
                "require_non_negative",
                "require_enum",
            }:
                constants.append(
                    {
                        "function": fn,
                        "line": node.lineno,
                        "arguments": [
                            ast.get_source_segment(source, arg)
                            for arg in node.args
                        ],
                    }
                )

        if isinstance(node, ast.Subscript):
            text = ast.get_source_segment(source, node) or ""

            if "inputs" in text:
                request_access.append(
                    {
                        "line": node.lineno,
                        "expression": text,
                    }
                )

    return {
        "error": None,
        "classes": sorted(set(classes)),
        "methods": sorted(set(methods)),
        "validate_blocks": validate_blocks,
        "run_blocks": run_blocks,
        "request_access": request_access,
        "result_calls": result_calls,
        "constants": constants,
    }


def inspect_skill(skill_id):
    files = source_files_for_skill(skill_id)

    aggregate = {
        "files": [],
        "classes": set(),
        "methods": set(),
        "validation": [],
        "run": [],
        "inputs": [],
        "results": [],
        "rules": [],
        "errors": [],
    }

    for path in files:
        info = inspect_file(path)
        rel = str(path.relative_to(ROOT))
        aggregate["files"].append(rel)

        if info["error"]:
            aggregate["errors"].append(f"{rel}: {info['error']}")
            continue

        aggregate["classes"].update(info["classes"])
        aggregate["methods"].update(info["methods"])

        for item in info["validate_blocks"]:
            item = dict(item)
            item["file"] = rel
            aggregate["validation"].append(item)

        for item in info["run_blocks"]:
            item = dict(item)
            item["file"] = rel
            aggregate["run"].append(item)

        for item in info["request_access"]:
            item = dict(item)
            item["file"] = rel
            aggregate["inputs"].append(item)

        for item in info["result_calls"]:
            item = dict(item)
            item["file"] = rel
            aggregate["results"].append(item)

        for item in info["constants"]:
            item = dict(item)
            item["file"] = rel
            aggregate["rules"].append(item)

    return aggregate


def main():
    registry = load_skill_registry(REGISTRY)

    assert len(registry.skill_ids) == 22
    assert len(registry.executable_ids) == 21
    assert registry.pending_ids == ["chiller_efficiency"]

    report = ROOT / (
        f"STEP30_EXACT_ADAPTER_CONTRACT_INSPECTION_"
        f"{datetime.now():%Y%m%d_%H%M%S}.txt"
    )

    lines = []
    lines.append("STEP 30 - EXACT ADAPTER CONTRACT INSPECTION")
    lines.append("=" * 120)
    lines.append("Purpose: inspect existing adapter implementation contracts.")
    lines.append("No engineering implementation or formula is modified.")
    lines.append("No missing engineering requirement is invented.")
    lines.append("")

    for number, skill_id in enumerate(registry.executable_ids, 1):
        skill = registry.get(skill_id)
        info = inspect_skill(skill_id)

        lines.append("=" * 120)
        lines.append(f"{number:02d}. {skill_id}")
        lines.append(f"Name       : {skill.name}")
        lines.append(f"Domain     : {skill.domain}")
        lines.append(f"Execution  : {skill.execution_type}")
        lines.append("")

        lines.append("SOURCE FILES")
        for item in info["files"]:
            lines.append(f"  - {item}")

        lines.append("")
        lines.append("CLASSES")
        for item in sorted(info["classes"]):
            lines.append(f"  - {item}")

        lines.append("")
        lines.append("METHODS")
        for item in sorted(info["methods"]):
            lines.append(f"  - {item}")

        lines.append("")
        lines.append("VALIDATION METHODS")
        if info["validation"]:
            for item in info["validation"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['name']}({', '.join(item['args'])})"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("DIRECT INPUT ACCESS")
        if info["inputs"]:
            for item in info["inputs"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['expression']}"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("VALIDATION RULE CALLS")
        if info["rules"]:
            for item in info["rules"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['function']}("
                    f"{', '.join(item['arguments'])})"
                )
        else:
            lines.append("  - NONE DETECTED")

        lines.append("")
        lines.append("SkillResult / SkillRequest USAGE")
        if info["results"]:
            for item in info["results"]:
                lines.append(
                    f"  - {item['file']}:{item['line']} "
                    f"{item['function']}"
                )
                for key, value in item["keywords"].items():
                    lines.append(f"      {key} = {value}")
        else:
            lines.append("  - NONE DETECTED")

        if info["errors"]:
            lines.append("")
            lines.append("PARSE ERRORS")
            for item in info["errors"]:
                lines.append(f"  - {item}")

    lines.append("")
    lines.append("=" * 120)
    lines.append("STEP 30 VERIFICATION")
    lines.append("=" * 120)
    lines.append(f"Registry skills : {len(registry.skill_ids)}")
    lines.append(f"Executable      : {len(registry.executable_ids)}")
    lines.append(f"Pending         : {registry.pending_ids}")
    lines.append("")
    lines.append(
        "All 21 executable registry entries were inspected against source files."
    )
    lines.append(
        "The report is evidence only and is not yet a SkillDefinition migration."
    )

    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"Report: {report}")
    print("")
    print("=== EXACT ADAPTER INSPECTION SUMMARY ===")

    for skill_id in registry.executable_ids:
        info = inspect_skill(skill_id)

        print(
            f"{skill_id:32} "
            f"FILES={len(info['files']):2} "
            f"VALIDATE={len(info['validation']):2} "
            f"INPUT_ACCESS={len(info['inputs']):2} "
            f"RULE_CALLS={len(info['rules']):2} "
            f"RESULT_CALLS={len(info['results']):2}"
        )

    print("")
    print("Registry total :", len(registry.skill_ids))
    print("Executable     :", len(registry.executable_ids))
    print("Pending        :", registry.pending_ids)

    assert len(registry.skill_ids) == 22
    assert len(registry.executable_ids) == 21
    assert registry.pending_ids == ["chiller_efficiency"]

    missing_source = [
        skill_id
        for skill_id in registry.executable_ids
        if not inspect_skill(skill_id)["files"]
    ]

    assert missing_source == []

    print("Source coverage: 21/21")
    print("STEP 30 INSPECTION: PASS")


if __name__ == "__main__":
    main()
