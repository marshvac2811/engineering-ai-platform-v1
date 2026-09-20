from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='aa6e95dbce04dfe71c99af16f07d7fc105193785'
class DuctLeakageSkill:
 skill_id='duct_leakage'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); i=r.inputs
  for k in ['sections','test_pressure_pa','measured_leakage_ls','target_class']:
   if k not in i:errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(i)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Leakage class is calculated using the source-tool SMACNA-formula implementation.','Project specification should govern the required leakage class over generic reference ranges.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
