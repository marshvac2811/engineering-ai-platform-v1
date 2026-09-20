from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='4eb8a9514431f0ede94df31824e539f23ee49ea'
class HVACBOQSkill:
 skill_id='hvac_boq'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r)
  if not isinstance(r.inputs.get('categories'),list):errs.append('categories must be a list')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Commercial estimate; quantities and rates are preparer inputs.','Tax/markup calculations follow the source tool and do not validate commercial or tax compliance.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
