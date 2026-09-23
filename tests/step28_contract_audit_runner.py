import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skill_framework.registry import load_skill_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "skill_registry" / "registry.yaml"
ENGINE = ROOT / "orchestrator" / "engine.py"

CONTRACT_SECTIONS = (
    "required_inputs",
    "optional_inputs",
    "conditional_inputs",
    "standards",
    "assumptions",
    "validation_rules",
    "warning_rules",
    "perfection_filter_rules",
    "output_fields",
    "audit_fields",
)

def section_state(value):
    if value is None:
        return "MISSING"
    if isinstance(value, (list, tuple, dict, set)):
        return "PRESENT" if len(value) else "EMPTY"
    return "PRESENT"

def main():
    registry = load_skill_registry(REGISTRY)
    engine_text = ENGINE.read_text(encoding="utf-8")

    rows = []

    for skill_id in registry.skill_ids:
        skill = registry.get(skill_id)

        # Current architecture keeps implementation bindings in orchestrator/engine.py.
        binding_in_engine = (
            skill.executable
            and skill_id in engine_text
        )

        row = {
            "skill_id": skill.skill_id,
            "name": skill.name,
            "domain": skill.domain,
            "executable": skill.executable,
            "binding_contract": bool(skill.implementation_binding),
            "binding_current_engine": binding_in_engine,
        }

        for section in CONTRACT_SECTIONS:
            row[section] = section_state(getattr(skill, section))

        rows.append(row)

    report = ROOT / f"STEP28_SKILL_CONTRACT_AUDIT_{__import__('datetime').datetime.now():%Y%m%d_%H%M%S}.txt"

    lines = []
    lines.append("STEP 28 - SKILL CONTRACT GAP AUDIT")
    lines.append("=" * 120)
    lines.append(f"Registry skills: {len(registry.skill_ids)}")
    lines.append(f"Executable: {len(registry.executable_ids)}")
    lines.append(f"Pending: {registry.pending_ids}")
    lines.append("")
    lines.append("IMPORTANT: EMPTY/MISSING CONTRACT SECTIONS ARE REPORTED, NOT INVENTED.")
    lines.append("Implementation binding is currently checked against orchestrator/engine.py.")
    lines.append("")

    header = (
        f"{'SKILL ID':32} {'DOMAIN':12} {'EXEC':5} "
        f"{'CONTRACT_BIND':12} {'ENGINE_BIND':11} "
        f"{'REQ':7} {'OPT':7} {'COND':7} {'STD':7} {'ASM':7} "
        f"{'VAL':7} {'WARN':7} {'PF':7} {'OUT':7} {'AUDIT':7}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for r in rows:
        lines.append(
            f"{r['skill_id']:32} "
            f"{r['domain']:12} "
            f"{str(r['executable']):5} "
            f"{str(r['binding_contract']):12} "
            f"{str(r['binding_current_engine']):11} "
            f"{r['required_inputs']:7} "
            f"{r['optional_inputs']:7} "
            f"{r['conditional_inputs']:7} "
            f"{r['standards']:7} "
            f"{r['assumptions']:7} "
            f"{r['validation_rules']:7} "
            f"{r['warning_rules']:7} "
            f"{r['perfection_filter_rules']:7} "
            f"{r['output_fields']:7} "
            f"{r['audit_fields']:7}"
        )

    lines.append("")
    lines.append("SECTION COUNTS")
    lines.append("=" * 120)

    for section in CONTRACT_SECTIONS:
        present = sum(r[section] == "PRESENT" for r in rows)
        empty = sum(r[section] == "EMPTY" for r in rows)
        missing = sum(r[section] == "MISSING" for r in rows)
        lines.append(
            f"{section:28} PRESENT={present:2} EMPTY={empty:2} MISSING={missing:2}"
        )

    lines.append("")
    lines.append("IMPLEMENTATION BINDING")
    lines.append("=" * 120)
    lines.append(
        f"SkillDefinition binding populated: "
        f"{sum(r['binding_contract'] for r in rows)}"
    )
    lines.append(
        f"Current engine binding detected: "
        f"{sum(r['binding_current_engine'] for r in rows)}"
    )
    lines.append(
        f"Executable skills without current engine binding: "
        f"{sum(r['executable'] and not r['binding_current_engine'] for r in rows)}"
    )

    report.write_text("\n".join(lines), encoding="utf-8")

    # Verification assertions.
    assert len(rows) == 22
    assert len(registry.executable_ids) == 21
    assert registry.pending_ids == ["chiller_efficiency"]

    executable_without_engine = [
        r["skill_id"]
        for r in rows
        if r["executable"] and not r["binding_current_engine"]
    ]
    assert executable_without_engine == []

    print(f"Audit report: {report}")
    print("")
    print("=== CONTRACT GAP MATRIX ===")
    print(header)
    print("-" * len(header))
    for line in lines[lines.index("-" * len(header)) + 1:]:
        if line.startswith("SECTION COUNTS"):
            break
        if line.strip():
            print(line)

    print("")
    print("=== SECTION COUNTS ===")
    for section in CONTRACT_SECTIONS:
        present = sum(r[section] == "PRESENT" for r in rows)
        empty = sum(r[section] == "EMPTY" for r in rows)
        missing = sum(r[section] == "MISSING" for r in rows)
        print(f"{section:28} PRESENT={present:2} EMPTY={empty:2} MISSING={missing:2}")

    print("")
    print("=== VERIFICATION ===")
    print("Registry skills:", len(registry.skill_ids))
    print("Executable:", len(registry.executable_ids))
    print("Pending:", registry.pending_ids)
    print(
        "Current engine bindings detected:",
        sum(r["binding_current_engine"] for r in rows),
    )
    print("SkillDefinition bindings populated:", sum(r["binding_contract"] for r in rows))
    print("STEP 28A AUDIT: PASS")

if __name__ == "__main__":
    main()

