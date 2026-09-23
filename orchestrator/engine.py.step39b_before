from __future__ import annotations
from typing import Dict
from skills.common import SkillRequest, SkillResult
from skills.hvac.duct_sizing.adapter import DuctSizingSkill
from skills.hvac.pump_head.adapter import PumpHeadSkill
from skills.hvac.preliminary_load_estimation.adapter import PreliminaryLoadEstimationSkill
from skills.hvac.fault_diagnosis.adapter import HVAFaultDiagnosisSkill
from skills.bms.points.adapters import BMSPointsGenerationSkill,BMSControllerSizingSkill
from skills.bms.cost.adapter import BMSCostEstimationSkill
from skills.energy.vfd.adapters import VFDEnergySavingsSkill,VFDDeratingSkill,HarmonicScreeningSkill
from skills.energy.decarbonisation.adapter import HVACDecarbonisationSkill
from skills.hvac.cooling_tower.adapter import CoolingTowerSkill
from skills.hvac.refrigerant_pipe_sizing.adapter import RefrigerantPipeSizingSkill
from skills.hvac.vrf_sizing.adapter import VRFSizingSkill
from skills.hvac.cleanroom_ach.adapter import CleanroomACHSKill
from skills.hvac.duct_leakage.adapter import DuctLeakageSkill
from skills.hvac.chiller_selection.adapter import ChillerSelectionAdvisorSkill
from skills.energy.payback.adapter import EnergyPaybackSkill
from skills.commercial.boq.adapter import HVACBOQSkill
from skills.commercial.deviation.adapter import DeviationStatementSkill
from skills.bms.alarm.adapter import BMSAlarmEvaluationSkill
SKILLS={
'duct_sizing':DuctSizingSkill(),'pump_head':PumpHeadSkill(),'preliminary_load_estimation':PreliminaryLoadEstimationSkill(),'hvac_fault_diagnosis':HVAFaultDiagnosisSkill(),
'bms_points_generation':BMSPointsGenerationSkill(),'bms_controller_sizing':BMSControllerSizingSkill(),'bms_cost_estimation':BMSCostEstimationSkill(),
'vfd_energy_savings':VFDEnergySavingsSkill(),'vfd_derating':VFDDeratingSkill(),'harmonic_screening':HarmonicScreeningSkill(),'hvac_decarbonisation':HVACDecarbonisationSkill(),
'cooling_tower':CoolingTowerSkill(),'refrigerant_pipe_sizing':RefrigerantPipeSizingSkill(),'vrf_sizing':VRFSizingSkill(),'cleanroom_ach':CleanroomACHSKill(),'duct_leakage':DuctLeakageSkill(),'chiller_selection_advisor':ChillerSelectionAdvisorSkill(),
'energy_payback':EnergyPaybackSkill(),'hvac_boq':HVACBOQSkill(),'deviation_statement':DeviationStatementSkill(),'bms_alarm_evaluation':BMSAlarmEvaluationSkill()}
def execute(request:SkillRequest)->SkillResult:
    skill=SKILLS.get(request.skill_id)
    if skill is None:return SkillResult(request.skill_id,'skill_not_registered',validation_errors=[f'Skill is not executable in current batch adapter set: {request.skill_id}'])
    return skill.run(request)
def registered_skills():return sorted(SKILLS)
