from skills.common import SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as e
REV='babc94e0dba720cdcc04edec52bdfafb12d9deb'
class DeviationStatementSkill:
 skill_id='deviation_statement'; version='1.0.0'
 def run(self,r):
  errs=validate_governance_context(r)
  if not isinstance(r.inputs.get('rows'),list):errs.append('rows must be a list')
  if errs:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=errs,source_revision=REV)
  try:o=e.calc(r.inputs)
  except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
  warns=['Compliance percentage is a document-control metric, not a substitute for technical or contractual review.','Clause interpretation remains subject to the tender/project specification.']
  return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=warns,source_revision=REV)
