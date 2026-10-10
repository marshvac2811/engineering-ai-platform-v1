from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class ImplementationBinding:
    skill_id: str
    implementation_path: str
    implementation_class: str


# Compatibility map derived from the existing orchestrator/engine.py
# This layer does not replace or modify the existing orchestrator.
IMPLEMENTATION_BINDINGS: Tuple[ImplementationBinding, ...] = (
    ImplementationBinding("duct_sizing", "skills.hvac.duct_sizing.adapter", "DuctSizingSkill"),
    ImplementationBinding("pump_head", "skills.hvac.pump_head.adapter", "PumpHeadSkill"),
    ImplementationBinding("preliminary_load_estimation", "skills.hvac.preliminary_load_estimation.adapter", "PreliminaryLoadEstimationSkill"),
    ImplementationBinding("hvac_fault_diagnosis", "skills.hvac.fault_diagnosis.adapter", "HVAFaultDiagnosisSkill"),
    ImplementationBinding("bms_points_generation", "skills.bms.points.adapters", "BMSPointsGenerationSkill"),
    ImplementationBinding("bms_controller_sizing", "skills.bms.points.adapters", "BMSControllerSizingSkill"),
    ImplementationBinding("bms_cost_estimation", "skills.bms.cost.adapter", "BMSCostEstimationSkill"),
    ImplementationBinding("vfd_energy_savings", "skills.energy.vfd.adapters", "VFDEnergySavingsSkill"),
    ImplementationBinding("vfd_derating", "skills.energy.vfd.adapters", "VFDDeratingSkill"),
    ImplementationBinding("harmonic_screening", "skills.energy.vfd.adapters", "HarmonicScreeningSkill"),
    ImplementationBinding("hvac_decarbonisation", "skills.energy.decarbonisation.adapter", "HVACDecarbonisationSkill"),
    ImplementationBinding("cooling_tower", "skills.hvac.cooling_tower.adapter", "CoolingTowerSkill"),
    ImplementationBinding("refrigerant_pipe_sizing", "skills.hvac.refrigerant_pipe_sizing.adapter", "RefrigerantPipeSizingSkill"),
    ImplementationBinding("vrf_sizing", "skills.hvac.vrf_sizing.adapter", "VRFSizingSkill"),
    ImplementationBinding("cleanroom_ach", "skills.hvac.cleanroom_ach.adapter", "CleanroomACHSKill"),
    ImplementationBinding("duct_leakage", "skills.hvac.duct_leakage.adapter", "DuctLeakageSkill"),
    ImplementationBinding("chiller_selection_advisor", "skills.hvac.chiller_selection.adapter", "ChillerSelectionAdvisorSkill"),
    ImplementationBinding("energy_payback", "skills.energy.payback.adapter", "EnergyPaybackSkill"),
    ImplementationBinding("hvac_boq", "skills.commercial.boq.adapter", "HVACBOQSkill"),
    ImplementationBinding("deviation_statement", "skills.commercial.deviation.adapter", "DeviationStatementSkill"),
    ImplementationBinding("facade_u_factor", "skills.hvac.facade_u_factor.adapter", "FacadeUFactorSkill"),
    ImplementationBinding("bms_alarm_evaluation", "skills.bms.alarm.adapter", "BMSAlarmEvaluationSkill"),
    ImplementationBinding("fire_water_storage", "skills.fire.preliminary_water_storage.adapter", "FireWaterStorageSkill"),
    ImplementationBinding("hvac_design_package", "skills.hvac.design_package.adapter", "HVACDesignPackageSkill"),
    ImplementationBinding("plumbing_water_demand", "skills.plumbing.preliminary_water_demand.adapter", "PlumbingWaterDemandSkill"),
    ImplementationBinding("psychrometric_properties", "skills.calculators.adapters", "PsychrometricPropertiesSkill"),
    ImplementationBinding("cooling_coil_load", "skills.calculators.adapters", "CoolingCoilLoadSkill"),
    ImplementationBinding("ventilation_rate", "skills.calculators.adapters", "VentilationRateSkill"),
    ImplementationBinding("fan_power_sizing", "skills.calculators.adapters", "FanPowerSizingSkill"),
    ImplementationBinding("water_pipe_sizing", "skills.calculators.adapters", "WaterPipeSizingSkill"),
    ImplementationBinding("expansion_tank_sizing", "skills.calculators.adapters", "ExpansionTankSizingSkill"),
    ImplementationBinding("hydronic_flow_rate", "skills.calculators.adapters", "HydronicFlowRateSkill"),
    ImplementationBinding("heat_recovery_assessment", "skills.calculators.adapters", "HeatRecoveryAssessmentSkill"),
    ImplementationBinding("chiller_iplv", "skills.calculators.adapters", "ChillerIPLVSkill"),
    ImplementationBinding("duct_pressure_drop", "skills.calculators.adapters", "DuctPressureDropSkill"),
    ImplementationBinding("insulation_condensation", "skills.calculators.adapters", "InsulationCondensationSkill"),
    ImplementationBinding("cable_voltage_drop", "skills.calculators.adapters", "CableVoltageDropSkill"),
    ImplementationBinding("sprinkler_demand", "skills.calculators.adapters", "SprinklerDemandSkill"),
    ImplementationBinding("hot_water_heater_sizing", "skills.calculators.adapters", "HotWaterHeaterSizingSkill"),
    ImplementationBinding("rainwater_drainage", "skills.calculators.adapters", "RainwaterDrainageSkill"),
    ImplementationBinding("solar_pv_sizing", "skills.calculators.adapters", "SolarPVSizingSkill"),
    ImplementationBinding("carbon_emissions", "skills.calculators.adapters", "CarbonEmissionsSkill"),
)


def binding_map() -> Dict[str, ImplementationBinding]:
    return {item.skill_id: item for item in IMPLEMENTATION_BINDINGS}
