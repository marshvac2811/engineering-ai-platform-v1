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

VALIDATE_NAMES = {
    "validate",
    "_validate",
    "validate_inputs",
    "_validate_inputs",
}

RESULT_NAMES = {
    "SkillResult",
    "SkillRequest",
}

COMMON_INPUT_PATTERNS = [
    re.compile(r'require_positive\(\s*[^,]+,\s*["\']([^"\']+)["\']'),
    re.compile(r'require_non_negative\(\s*[^,]+,\s*["\']([^"\']+)["\']'),
    re.compile(r'require_enum\(\s*[^,]+,\s*["\']([^"\']+)["\']'),
]


def source_files_for_skill(skill_id):
    parts = skill_id.split("_")

    candidates = []

    # Direct directory/name matching.
    for p in SKILLS_ROOT.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore").lower()
        normalized = p.as_posix().lower()

        if skill_id.lower() in normalized:
            candidates.append(p)
            continue

        # Also capture files in likely skill directories.
        if all(part in text for part in parts[:1]):
            if any(part in normalized for part in parts):
                candidates.append(p)

    # Broader fallback: search for exact skill ID in source.
    if not candidates:
        for p in SKILLS_ROOT.rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
            if skill_id.lower() in text:
                candidates.append(p)

    return sorted(set(candidates))


def extract_string_literals(node):
    values = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.append(child.value)
    return values


def extract_validation_fields(tree, source):
    fields = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                fn = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn = node.func.attr
            else:
                fn = ""

            if fn in VALIDATE_NAMES:
                if node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Attribute):
                        fields.add(first.attr)
                    elif isinstance(first, ast.Subscript):
                        if isinstance(first.slice, ast.Constant):
                            fields.add(str(first.slice.value))

            for pattern in COMMON_INPUT_PATTERNS:
                for match in pattern.finditer(
                    ast.get_source_segment(source, node) or ""
                ):
                    fields.add(match.group(1))

    # Common direct request.inputs["field"] / inputs.get("field") patterns.
    for pattern in (
        r'(?:request\.inputs|inputs)\s*\[\s*["\']([^"\']+)["\']\s*\]',
        r'(?:request\.inputs|inputs)\.get\(\s*["\']([^"\']+)["\']',
    ):
        fields.update(re.findall(pattern, source))

    return sorted(fields)


def extract_question_like_fields(source):
    fields = set()

    patterns = [
        r'["\']([A-Za-z][A-Za-z0-9_]+)["\']\s*:\s*["\'][^"\']{3,120}',
        r'field\s*=\s*["\']([A-Za-z][A-Za-z0-9_]+)["\']',
        r'name\s*=\s*["\']([A-Za-z][A-Za-z0-9_]+)["\']',
    ]

    for pattern in patterns:
        fields.update(re.findall(pattern, source))

    return sorted(fields)


def extract_return_contract(tree):
    result_fields = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = ""
            if isinstance(node.func, ast.Name):
                fn = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn = node.func.attr

            if fn == "SkillResult":
                for kw in node.keywords:
                    if kw.arg:
                        result_fields.add(kw.arg)

    return sorted(result_fields)


def inspect_skill(skill_id):
    files = source_files_for_skill(skill_id)

    validation_fields = set()
    return_fields = set()
    source_hits = []
    classes = []
    methods = []

    for path in files:
        source = path.read_text(encoding="utf-8", errors="ignore")

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            source_hits.append(
                f"SYNTAX_ERROR:{path.relative_to(ROOT)}:{exc}"
            )
            continue

        validation_fields.update(
            extract_validation_fields(tree, source)
        )
        return_fields.update(
            extract_return_contract(tree)
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in VALIDATE_NAMES or "run" in node.name.lower():
                    methods.append(node.name)

        for line_no, line in enumerate(source.splitlines(), 1):
            if any(
                marker in line
                for marker in (
                    "require_positive(",
                    "require_non_negative(",
                    "require_enum(",
                    "request.inputs",
                    "inputs.get(",
                    "SkillResult(",
                )
            ):
                source_hits.append(
                    f"{path.relative_to(ROOT)}:{line_no}: {line.strip()}"
                )

    return {
        "files": [str(p.relative_to(ROOT)) for p in files],
        "validation_fields": sorted(validation_fields),
        "return_fields": sorted(return_fields),
        "classes": sorted(set(classes)),
        "methods": sorted(set(methods)),
        "source_hits": source_hits,
    }


def main():
    registry = load_skill_registry(REGISTRY)

    assert len(registry.skill_ids) == 22
    assert len(registry.executable_ids) == 21
    assert registry.pending_ids == ["chiller_efficiency"]

    executable = registry.executable_ids

    report_path = ROOT / (
        f"STEP29_ACTUAL_SKILL_CONTRACT_EXTRACTION_"
        f"{datetime.now():%Y%m%d_%H%M%S}.txt"
    )

    lines = []
    lines.append("STEP 29 - ACTUAL SKILL CONTRACT EXTRACTION")
    lines.append("=" * 120)
    lines.append(f"Registry skills : {len(registry.skill_ids)}")
    lines.append(f"Executable      : {len(executable)}")
    lines.append(f"Pending         : {registry.pending_ids}")
    lines.append("")
    lines.append(
        "IMPORTANT: This report extracts evidence from existing source code."
    )
    lines.append(
        "It does NOT invent missing requirements, standards, assumptions or rules."
    )
    lines.append("")

    for index, skill_id in enumerate(executable, 1):
        skill = registry.get(skill_id)
        info = inspect_skill(skill_id)

        lines.append("=" * 120)
        lines.append(f"{index:02d}. {skill_id}")
        lines.append(f"Name                 : {skill.name}")
        lines.append(f"Domain               : {skill.domain}")
        lines.append(f"Execution type       : {skill.execution_type}")
        lines.append(
            f"Current registry binding: "
            f"{'YES' if skill.implementation_binding else 'NO'}"
        )
        lines.append(
            f"Implementation files : {len(info['files'])}"
        )

        lines.append("Source files:")
        for f in info["files"]:
            lines.append(f"  - {f}")

        lines.append("Classes:")
        for c in info["classes"]:
            lines.append(f"  - {c}")

        lines.append("Relevant methods:")
        for m in info["methods"]:
            lines.append(f"  - {m}")

        lines.append(
            "Validation/input fields detected:"
        )
        if info["validation_fields"]:
            for field in info["validation_fields"]:
                lines.append(f"  - {field}")
        else:
            lines.append("  - NONE DETECTED")

        lines.append("SkillResult fields detected:")
        if info["return_fields"]:
            for field in info["return_fields"]:
                lines.append(f"  - {field}")
        else:
            lines.append("  - NONE DETECTED")

        lines.append("Evidence lines:")
        if info["source_hits"]:
            for hit in info["source_hits"][:80]:
                lines.append(f"  - {hit}")
        else:
            lines.append("  - NONE DETECTED")

    lines.append("")
    lines.append("=" * 120)
    lines.append("STEP 29 SUMMARY")
    lines.append("=" * 120)
    lines.append(
        "The extracted fields are evidence for the next SkillDefinition mapping step."
    )
    lines.append(
        "No engineering constants, standards, assumptions, formulas or missing inputs "
        "have been invented."
    )
    lines.append(
        "The pending chiller_efficiency skill remains outside executable extraction."
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Report: {report_path}")
    print("")
    print("=== STEP 29 EXECUTABLE SKILLS ===")
    print(f"Registry total : {len(registry.skill_ids)}")
    print(f"Executable     : {len(executable)}")
    print(f"Pending        : {registry.pending_ids}")
    print("")

    for skill_id in executable:
        info = inspect_skill(skill_id)
        fields = info["validation_fields"]
        outputs = info["return_fields"]
        print(
            f"{skill_id:32} "
            f"FILES={len(info['files']):2} "
            f"INPUT_EVIDENCE={len(fields):2} "
            f"RESULT_FIELDS={len(outputs):2}"
        )

    print("")
    print("=== STEP 29 VERIFICATION ===")
    assert len(executable) == 21
    assert "chiller_efficiency" not in executable

    missing_source = [
        skill_id
        for skill_id in executable
        if not inspect_skill(skill_id)["files"]
    ]

    print(
        "Executable skills with no source file discovered:",
        missing_source,
    )

    assert missing_source == []
    print("All 21 executable skills have source evidence.")
    print("STEP 29 EXTRACTION: PASS")


if __name__ == "__main__":
    main()
