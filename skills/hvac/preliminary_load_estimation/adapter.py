from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context, resolve_standards_context
from . import source_calculator as engine
SOURCE_REVISION='9046682a3500d347f57353d4f6313df8ea2543d'
class PreliminaryLoadEstimationSkill:
    skill_id='preliminary_load_estimation'; version='1.0.0'
    def validate(self,r):
        e=validate_governance_context(r); i=r.inputs
        for k in ('building_type','area_sqft','climate_zone'):
            if k not in i: e.append(f'Missing required input: {k}')
        if 'area_sqft' in i:
            try:
                if float(i['area_sqft'])<=0:e.append('area_sqft must be greater than zero')
            except: e.append('area_sqft must be numeric')
        if 'occupancy' in i and i['occupancy'] is not None:
            try:
                if int(i['occupancy'])<0:e.append('occupancy must be non-negative')
            except: e.append('occupancy must be numeric')
        return e
    def run(self,r):
        e=self.validate(r)
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=SOURCE_REVISION)
        i=r.inputs
        try: out=engine.estimate_load(i['building_type'],float(i['area_sqft']),i['climate_zone'],None if i.get('occupancy') is None else int(i['occupancy']))
        except (ValueError,TypeError) as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=SOURCE_REVISION)
        warnings=['Preliminary/budgetary rule-of-thumb only; not a detailed Manual J/CLTD/HAP calculation.','Source climate labels/multipliers are preserved as source data and require project/standards validation before design use.','Final equipment selection requires detailed load calculation and local design conditions.']
        return SkillResult(self.skill_id,'draft_ready',engineering_result=out,standards=resolve_standards_context(r.standards_context),warnings=warnings,calculation_trace=[{'step':1,'operation':'select_building_type_and_base_sqft_per_ton'},{'step':2,'operation':'apply_source_climate_multiplier'},{'step':3,'operation':'apply_occupancy_addon_if_applicable'},{'step':4,'operation':'round_up_to_half_ton'}],source_revision=SOURCE_REVISION)
