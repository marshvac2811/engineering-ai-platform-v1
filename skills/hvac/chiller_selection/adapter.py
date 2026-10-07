from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='75eedd78305e88e8fc2440559cb94f3839db515d'
class ChillerSelectionAdvisorSkill:
 skill_id='chiller_selection_advisor'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); i=r.inputs
  for k in ['total_load_tr','efficiency_kw_per_tr','annual_hours','load_factor_pct','tariff_per_kwh','redundancy_level']:
   if k not in i:errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(i)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Generic advisory only; final model, sound, footprint, part-load and certified performance require manufacturer selection data.','Efficiency benchmark values are source-tool user inputs, not live market data.','Duty-module count is not inferred without an explicit module-capacity basis; module configuration remains a recommendation/site/vendor decision.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
