from .models import ComplianceCheck, ComplianceStatus, CodeRequirement

class ComplianceEngine:
    OPERATORS = {
        "<=": lambda a, b: a <= b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        ">": lambda a, b: a > b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    def evaluate(self, requirement: CodeRequirement, input_value, *, applicable=True, evidence=None):
        if not applicable:
            return ComplianceCheck(
                requirement.requirement_id, ComplianceStatus.NOT_APPLICABLE,
                input_value, requirement.required_value, requirement.unit,
                "Applicability rule evaluated false.",
                f"{requirement.document.code_name} {requirement.document.edition}, Clause {requirement.clause}",
                requirement.document.authority, requirement.document.code_name, requirement.document.edition,
                requirement.requirement_type.value, evidence or {},
            )
        if input_value is None:
            return ComplianceCheck(
                requirement.requirement_id, ComplianceStatus.NOT_VERIFIABLE,
                None, requirement.required_value, requirement.unit,
                "Required engineering value was not available.",
                f"{requirement.document.code_name} {requirement.document.edition}, Clause {requirement.clause}",
                requirement.document.authority, requirement.document.code_name, requirement.document.edition,
                requirement.requirement_type.value, evidence or {},
            )
        fn = self.OPERATORS.get(requirement.operator)
        if fn is None:
            raise ValueError(f"Unsupported compliance operator: {requirement.operator}")
        if isinstance(input_value, bool) or isinstance(requirement.required_value, bool):
            passed = fn(input_value, requirement.required_value)
        else:
            passed = fn(float(input_value), float(requirement.required_value))
        return ComplianceCheck(
            requirement.requirement_id,
            ComplianceStatus.PASS if passed else ComplianceStatus.FAIL,
            float(input_value), requirement.required_value, requirement.unit,
            f"{input_value} {requirement.operator} {requirement.required_value}",
            f"{requirement.document.code_name} {requirement.document.edition}, Clause {requirement.clause}",
            requirement.document.authority, requirement.document.code_name, requirement.document.edition,
            requirement.requirement_type.value, evidence or {},
        )
