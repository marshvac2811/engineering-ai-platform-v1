from skills.common import SkillRequest, SkillResult
from validators.governance import validate_governance_context
from . import source_calculator as engine
REV='bc5c25757ecb68bff3b7d96273340228ec368c52'
def _savings_trace(o):
    """Worked steps with the actual numbers so the report shows how the result was reached."""
    sr, sf = o['speed_ratio'], o['static_head_fraction']
    return [
        {'step': 1, 'operation': 'apply_affinity_law_cube_relationship',
         'detail': f"Power scales with speed cubed: {sr:g}^3 = {sr**3:.4f}; theoretical saving = 1 - {sr**3:.4f} = {o['savings_pct_pure']:g}% "
                   f"({o['motor_kw']:g} kW -> {o['reduced_power_kw_pure']:g} kW)"},
        {'step': 2, 'operation': 'apply_static_head_correction',
         'detail': f"Static head fraction {sf:g}% does not fall with speed: power ratio = {sf/100:g} + {1-sf/100:g} x {sr**3:.4f} = {sf/100 + (1-sf/100)*sr**3:.5f}; "
                   f"corrected saving = {o['savings_pct_corrected']:g}% ({o['reduced_power_kw_corrected']:g} kW)"},
        {'step': 3, 'operation': 'annualize_energy_and_cost',
         'detail': f"{o['motor_kw']:g} kW x (1 - {sf/100 + (1-sf/100)*sr**3:.5f}) x {o['annual_hours']:,.0f} h = {o['annual_savings_kwh_corrected']:,.0f} kWh/yr; "
                   f"x tariff {o['tariff_per_kwh']:g} = {o['annual_savings_cost_corrected']:,.0f} (currency of the tariff)"},
    ]


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
        return SkillResult(self.skill_id,'draft_ready',engineering_result=o,warnings=['Savings model uses the source static-head correction and should be validated against measured system behavior.'],calculation_trace=_savings_trace(o),source_revision=REV)
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
