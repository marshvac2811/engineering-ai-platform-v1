from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='9e617d33020beb18de05754940e37214f8616b8d'
class HVACDecarbonisationSkill:
    skill_id='hvac_decarbonisation'
    def run(self,r):
        e=validate_governance_context(r); i=r.inputs
        mode=i.get('mode','impact'); fn=engine.compute_scenarios if mode=='scenarios' else engine.compute_impact
        required=['annual_energy_kwh','tariff']
        e += [f'Missing required input: {k}' for k in required if k not in i]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=fn(i)
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Scenario/impact model is assumption-driven; site data, current tariffs and governed emission factors should be verified before proposal use.'],source_revision=REV)
