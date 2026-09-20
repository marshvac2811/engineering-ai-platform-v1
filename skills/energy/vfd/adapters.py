from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='bc5c25757ecb68bff3b7d96273340228ec368c52'
class _Base:
    def validate(self,r): return validate_governance_context(r)
class VFDEnergySavingsSkill(_Base):
    skill_id='vfd_energy_savings'
    def run(self,r):
        e=self.validate(r); keys=['motor_kw','speed_reduction_pct','static_head_fraction','annual_hours','tariff_per_kwh']
        e += [f'Missing required input: {k}' for k in keys if k not in r.inputs]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.calculate_energy_savings(**{k:float(r.inputs[k]) for k in keys})
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Savings model uses the source static-head correction and should be validated against measured system behavior.'],calculation_trace=[{'step':1,'operation':'apply_affinity_law_cube_relationship'},{'step':2,'operation':'apply_static_head_correction'},{'step':3,'operation':'annualize_energy_and_cost'}],source_revision=REV)
class VFDDeratingSkill(_Base):
    skill_id='vfd_derating'
    def run(self,r):
        e=self.validate(r); keys=['motor_kw','ambient_temp_c','altitude_m']; e += [f'Missing required input: {k}' for k in keys if k not in r.inputs]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.calculate_sizing(**{k:float(r.inputs[k]) for k in keys})
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Temperature/altitude factors are generic reference values from the source and must be checked against the selected VFD manufacturer/model datasheet.'],source_revision=REV)
class HarmonicScreeningSkill(_Base):
    skill_id='harmonic_screening'
    def run(self,r):
        e=self.validate(r); keys=['total_vfd_kva','transformer_kva']; e += [f'Missing required input: {k}' for k in keys if k not in r.inputs]
        if e:return SkillResult(self.skill_id,'input_validation_failed',validation_errors=e,source_revision=REV)
        try:o=engine.screen_harmonics_risk(**{k:float(r.inputs[k]) for k in keys})
        except Exception as ex:return SkillResult(self.skill_id,'calculation_failed',validation_errors=[str(ex)],source_revision=REV)
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Screening heuristic only; not an IEEE 519 harmonic study.'],source_revision=REV)
