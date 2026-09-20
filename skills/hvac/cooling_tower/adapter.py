from skills.common import SkillRequest,SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='ed5447d4be48ebe71112f454b3c139136d4bfa9c'
class CoolingTowerSkill:
 skill_id='cooling_tower'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r)
  for k in ['load_method','range_c','wet_bulb_c','approach_c','coc','drift_pct']:
   if k not in r.inputs: errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calculate(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  if r.inputs['load_method']=='chiller':
   for k in ['chiller_tr','chiller_cop']:
    if k not in r.inputs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=[f'Missing required input: {k}'],source_revision=REV)
  else:
   if 'direct_load_kw' not in r.inputs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=['Missing required input: direct_load_kw'],source_revision=REV)
  warns=['Preliminary cooling-tower sizing support; final tower selection requires vendor performance-curve verification.','Design wet-bulb temperature must be project/site specific.','Water-treatment and water-quality constraints are not modeled.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,human_review_required=True,source_revision=REV)
