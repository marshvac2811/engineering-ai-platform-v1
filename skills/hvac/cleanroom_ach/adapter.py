from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='bd163a0f7e51971c613172c5f768b682027d2b05'
class CleanroomACHSKill:
 skill_id='cleanroom_ach'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r); i=r.inputs
  for k in ['room_type','length_m','width_m','height_m']:
   if k not in i:errs.append(f'Missing required input: {k}')
  if 'room_type' in i and i['room_type'] not in e.ROOM_TYPES:errs.append('Unknown room_type')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(i)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Reference ACH values are source-tool planning data and must be verified against the applicable standard/edition and project authority.','This tool does not establish cleanroom classification compliance by itself.','Pressure relationship and outdoor-air values require project sequence/authority confirmation.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
