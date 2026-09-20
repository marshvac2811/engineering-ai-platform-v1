from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='1afd6bdc704c7b73daa6ca573fe07a820ed5ffd5'
class RefrigerantPipeSizingSkill:
 skill_id='refrigerant_pipe_sizing'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); req=['refrigerant','capacity_kw','suction_velocity','liquid_velocity','suction_length','liquid_length']
  for k in req:
   if k not in r.inputs:errs.append(f'Missing required input: {k}')
  if 'refrigerant' in r.inputs and r.inputs['refrigerant'] not in e.PROPS:errs.append('Unsupported refrigerant')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Preliminary sizing only; manufacturer piping guide must finalize pipe diameter, oil-return provisions and capacity corrections.','Refrigerant properties are fixed typical values from the source tool and vary with operating conditions.','Long-line, elevation and accessory effects beyond the source model are not captured.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
