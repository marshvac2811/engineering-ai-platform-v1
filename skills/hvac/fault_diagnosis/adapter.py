from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
SOURCE_REVISION='1abcf2c385280721763c2fbebcf423fd424b149c'
class HVAFaultDiagnosisSkill:
    skill_id='hvac_fault_diagnosis'; version='1.0.0'
    def validate(self,r):
        e=validate_governance_context(r); i=r.inputs
        if 'rule_id' not in i:e.append('Missing required input: rule_id')
        if 'values' not in i or not isinstance(i.get('values'),dict):e.append('values must be an object/dict')
        if 'rule_id' in i and i['rule_id'] not in engine.RULES:e.append(f"Unknown rule: {i['rule_id']}")
        return e
    def run(self,r):
        e=self.validate(r)
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=SOURCE_REVISION)
        try:out=engine.evaluate_rule(r.inputs['rule_id'],r.inputs['values'])
        except (ValueError,KeyError,TypeError) as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=SOURCE_REVISION)
        warnings=['Rule-based diagnostic support only; conclusion is the source rule result, not a final field diagnosis.','Inspect the underlying equipment, controls and measurement chain before corrective action.']
        if not out['all_conditions_met']:warnings.append('Not all rule conditions are met; no source-rule conclusion is returned.')
        return SkillResult(self.skill_id,'draft_ready',engineering_result=out,warnings=warnings,calculation_trace=[{'step':1,'operation':'evaluate_explicit_AND_conditions','rule_id':r.inputs['rule_id']}],source_revision=SOURCE_REVISION)
