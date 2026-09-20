from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='a06eb9135305c86e097ffeadcb49f122679e32db'
class VRFSizingSkill:
 skill_id='vrf_sizing'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r)
  if not isinstance(r.inputs.get('zones'),list) or not r.inputs.get('zones'):errs.append('zones must be a non-empty list')
  if 'combination_ratio' not in r.inputs:errs.append('Missing required input: combination_ratio')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Generic VRF sizing conventions only; final indoor/outdoor models and piping limits require manufacturer selection software.','Source method rounds each zone to an IDU capacity step before summing connected HP, which can differ from raw thermal load.','Typical piping limits are reference values, not model-specific approvals.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
