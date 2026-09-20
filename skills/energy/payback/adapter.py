from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='e51a1c9603fe8da53b0cf68fcc1ebada93d38e0c'
class EnergyPaybackSkill:
 skill_id='energy_payback'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); req=['capacity_old','efficiency_old','capacity_new','efficiency_new','annual_hours','load_factor_pct','tariff_per_kwh','investment']
  for k in req:
   if k not in r.inputs:errs.append(f'Missing required input: {k}')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Financial estimate only; tariff, operating hours, load factor and incremental O&M are user assumptions.','Does not include financing, discount rate, degradation, escalation or taxes beyond the simple source model.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
