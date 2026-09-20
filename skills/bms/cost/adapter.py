from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='5061af18947e0c37f533ff6518e68c672c088407'
class BMSCostEstimationSkill:
    skill_id='bms_cost_estimation'
    def run(self,r):
        e=validate_governance_context(r)
        keys=['ahu_count','chiller_count','pump_count','vfd_count','misc_points','points_per_controller','controllers_per_panel','cost_per_point','cost_per_controller','cost_per_panel','bms_software_cost','engineering_pct']
        e += [f'Missing required input: {k}' for k in keys if k not in r.inputs]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.estimate_cost(**{k:float(r.inputs[k]) for k in keys})
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Budgetary framework only; market unit rates are user inputs and point counts are planning-stage estimates.'],source_revision=REV)
