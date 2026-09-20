from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='20d5a695a5304ba2f110bbaa89c9820743a23f0a'
class BMSAlarmEvaluationSkill:
 skill_id='bms_alarm_evaluation'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); i=r.inputs
  for k in ['point_type','point_id','value']:
   if k not in i:errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(i)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Thresholds are example planning values from the source dashboard, not project-specific alarm setpoints.','For production BMS use, thresholds should come from the actual equipment sequence/controls specification.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
