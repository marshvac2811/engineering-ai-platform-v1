from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='a8c28e363bb8c58bb74e40038d8ade858beefeb5'
class BMSPointsGenerationSkill:
    skill_id='bms_points_generation'
    def run(self,r):
        e=validate_governance_context(r); i=r.inputs
        if not isinstance(i.get('equipment_counts'),dict):e.append('equipment_counts must be an object')
        for k in ('points_per_controller','controllers_per_panel'):
            if k not in i:e.append(f'Missing required input: {k}')
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.build_full_report(i['equipment_counts'],int(i['points_per_controller']),int(i['controllers_per_panel']))
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Generic planning-stage points template; final points must follow project scope, sequence of operations, gateway capabilities and owner requirements.'],source_revision=REV)
class BMSControllerSizingSkill:
    skill_id='bms_controller_sizing'
    def run(self,r):
        e=validate_governance_context(r); i=r.inputs
        for k in ('total_points','points_per_controller','controllers_per_panel'):
            if k not in i:e.append(f'Missing required input: {k}')
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.calculate_controller_sizing(int(i['total_points']),int(i['points_per_controller']),int(i['controllers_per_panel']))
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Controller capacity must be checked against actual selected controller I/O and project architecture.'],source_revision=REV)
