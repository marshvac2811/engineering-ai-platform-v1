"""Catalogue of governed calculators: metadata (single source for registry + routing) and execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

from skills.common import SkillRequest, SkillResult
from skills.calculators import formulas as F

VERSION = "1.0.0"
SOURCE_REV = "internal-governed-2026-10-10"


@dataclass(frozen=True)
class Calc:
    skill_id: str
    class_name: str
    title: str
    domain: str
    fn: Callable
    required: Tuple[Tuple[str, str, str], ...]   # (name, type, description)
    optional: Tuple[Tuple[str, str, str], ...]
    routing: Tuple[str, ...]


N, S, A = "number", "string", "array"

CALCULATORS: Tuple[Calc, ...] = (
    Calc("psychrometric_properties", "PsychrometricPropertiesSkill", "Psychrometric Properties", "HVAC", F.psychrometrics,
         (("dry_bulb_c", N, "Dry-bulb temperature, deg C."), ("rh_pct", N, "Relative humidity, %.")),
         (("altitude_m", N, "Site altitude in m (default 0)."),),
         ("psychrometric", "dew point", "humidity ratio", "wet bulb from", "enthalpy of air", "moist air properties")),
    Calc("cooling_coil_load", "CoolingCoilLoadSkill", "Cooling Coil Load", "HVAC", F.coil_load,
         (("airflow_m3h", N, "Coil airflow, m3/h."), ("entering_db_c", N, "Entering dry-bulb, deg C."), ("entering_rh_pct", N, "Entering RH, %."),
          ("leaving_db_c", N, "Leaving dry-bulb, deg C."), ("leaving_rh_pct", N, "Leaving RH, %.")),
         (("altitude_m", N, "Site altitude in m (default 0)."),),
         ("cooling coil load", "coil load", "ahu coil", "sensible heat ratio", "shr of coil", "coil capacity")),
    Calc("ventilation_rate", "VentilationRateSkill", "Ventilation Outdoor-Air Rate", "HVAC", F.ventilation_rate,
         (("floor_area_m2", N, "Zone floor area, m2."), ("occupants", N, "Number of occupants.")),
         (("space_type", S, "office, conference, lobby, retail, classroom, restaurant_dining, gym, hospital_patient_room."),
          ("rp_l_s_person", N, "Outdoor air per person, L/s (overrides table)."), ("ra_l_s_m2", N, "Outdoor air per m2, L/s (overrides table)."),
          ("zone_air_distribution_effectiveness", N, "Ez, default 1.0.")),
         ("ventilation rate", "fresh air requirement", "outdoor air requirement", "ashrae 62.1", "fresh air quantity", "ventilation requirement")),
    Calc("fan_power_sizing", "FanPowerSizingSkill", "Fan Power and Motor Sizing", "HVAC", F.fan_power,
         (("airflow_m3h", N, "Fan airflow, m3/h."), ("total_static_pressure_pa", N, "Total fan pressure, Pa.")),
         (("fan_efficiency_pct", N, "Fan total efficiency, % (default 65)."), ("drive_efficiency_pct", N, "Drive efficiency, % (default 95)."),
          ("motor_efficiency_pct", N, "Motor efficiency, % (default 92)."), ("motor_margin_pct", N, "Motor margin, % (default 15).")),
         ("fan power", "fan motor", "fan kw", "specific fan power", "fan sizing")),
    Calc("water_pipe_sizing", "WaterPipeSizingSkill", "Water Pipe Sizing", "HVAC", F.water_pipe_sizing,
         (("flow_m3h", N, "Water flow, m3/h."),),
         (("target_velocity_ms", N, "Target velocity m/s (default 2.0)."), ("length_m", N, "Straight length, m (default 100)."),
          ("water_temp_c", N, "Water temperature, deg C (default 20)."), ("roughness_mm", N, "Pipe roughness, mm (default 0.045).")),
         ("water pipe sizing", "size the water pipe", "chilled water pipe", "pipe size for", "pipe diameter for", "hydronic pipe")),
    Calc("expansion_tank_sizing", "ExpansionTankSizingSkill", "Expansion Tank Sizing", "HVAC", F.expansion_tank,
         (("system_volume_l", N, "Total system water volume, L."), ("max_temp_c", N, "Maximum water temperature, deg C."),
          ("fill_pressure_bar_g", N, "Fill/precharge pressure, bar(g)."), ("max_pressure_bar_g", N, "Maximum allowed pressure, bar(g).")),
         (("min_temp_c", N, "Minimum (fill) water temperature, deg C (default 10)."),),
         ("expansion tank", "expansion vessel", "expansion volume")),
    Calc("hydronic_flow_rate", "HydronicFlowRateSkill", "Hydronic Flow Rate", "HVAC", F.hydronic_flow,
         (("load", N, "Cooling/heating load."),),
         (("load_unit", S, "kw or tr (default kw)."), ("delta_t_c", N, "Water temperature difference, deg C (default 5.5)."),
          ("chiller_cop", N, "Chiller COP, to also get condenser heat rejection.")),
         ("chilled water flow", "water flow rate", "gpm per tr", "hydronic flow", "flow rate for chiller", "flow for tr")),
    Calc("heat_recovery_assessment", "HeatRecoveryAssessmentSkill", "Heat Recovery Assessment", "ENERGY", F.heat_recovery,
         (("outdoor_air_m3h", N, "Outdoor airflow through the recovery device, m3/h."), ("effectiveness_pct", N, "Device effectiveness, %."),
          ("outdoor_db_c", N, "Outdoor dry-bulb, deg C."), ("outdoor_rh_pct", N, "Outdoor RH, %."),
          ("exhaust_db_c", N, "Exhaust/return dry-bulb, deg C."), ("exhaust_rh_pct", N, "Exhaust/return RH, %.")),
         (("recovery_type", S, "sensible or total (default total)."), ("altitude_m", N, "Altitude, m."),
          ("annual_hours", N, "Operating hours per year."), ("load_factor_pct", N, "Average load factor of the design recovery, %.")),
         ("heat recovery", "energy recovery wheel", "enthalpy wheel", "energy recovery ventilator", "heat recovery wheel", "exhaust air heat recovery")),
    Calc("chiller_iplv", "ChillerIPLVSkill", "Chiller IPLV", "ENERGY", F.chiller_iplv,
         (("cop_100", N, "COP at 100% load."), ("cop_75", N, "COP at 75% load."), ("cop_50", N, "COP at 50% load."), ("cop_25", N, "COP at 25% load.")),
         (), ("iplv", "part load value", "part-load efficiency", "ahri 550", "integrated part load")),
    Calc("duct_pressure_drop", "DuctPressureDropSkill", "Duct Pressure Drop", "HVAC", F.duct_pressure_drop,
         (("airflow_m3h", N, "Airflow, m3/h."), ("length_m", N, "Straight duct length, m.")),
         (("diameter_mm", N, "Round duct diameter, mm."), ("width_mm", N, "Rectangular width, mm."), ("height_mm", N, "Rectangular height, mm."),
          ("roughness_mm", N, "Roughness, mm (default 0.09)."), ("fittings", A, "List of {name, k, quantity}.")),
         ("duct pressure drop", "duct static pressure", "duct friction loss", "duct pressure loss", "pressure drop in duct")),
    Calc("insulation_condensation", "InsulationCondensationSkill", "Insulation for Condensation Control", "HVAC", F.insulation_condensation,
         (("fluid_temp_c", N, "Fluid temperature, deg C."), ("ambient_db_c", N, "Ambient dry-bulb, deg C."), ("ambient_rh_pct", N, "Ambient RH, %."),
          ("pipe_outer_diameter_mm", N, "Bare pipe outer diameter, mm.")),
         (("insulation_k_w_mk", N, "Insulation conductivity, W/m.K (default 0.035)."), ("surface_coeff_w_m2k", N, "Outside surface coefficient, W/m2.K (default 8)."),
          ("dew_point_margin_c", N, "Margin above dew point, deg C (default 1).")),
         ("insulation thickness", "condensation control", "pipe condensation", "pipe insulation", "sweating pipe", "dew point insulation")),
    Calc("cable_voltage_drop", "CableVoltageDropSkill", "Cable Current and Voltage Drop", "ELECTRICAL", F.cable_voltage_drop,
         (("load_kw", N, "Electrical load, kW."), ("length_m", N, "Cable route length, m.")),
         (("voltage_v", N, "Line voltage, V (default 415)."), ("power_factor", N, "Power factor (default 0.85)."), ("efficiency_pct", N, "Motor efficiency, % (default 100)."),
          ("conductor", S, "copper or aluminium."), ("cross_section_mm2", N, "Cable size to check, mm2."), ("parallel_runs", N, "Parallel cables per phase."),
          ("limit_pct", N, "Voltage-drop limit, % (default 5)."), ("reactance_ohm_km", N, "Cable reactance, ohm/km (default 0.08).")),
         ("voltage drop", "cable sizing", "cable size for", "motor current", "full load current")),
    Calc("sprinkler_demand", "SprinklerDemandSkill", "Sprinkler Water Demand", "FIRE", F.sprinkler_demand,
         (("hazard_class", S, "light, ordinary_1, ordinary_2, extra_1 or extra_2."),),
         (("design_density_l_min_m2", N, "Override density, L/min/m2."), ("design_area_m2", N, "Override design area, m2."),
          ("hose_allowance_l_min", N, "Override hose allowance, L/min."), ("duration_min", N, "Override duration, min."),
          ("pump_head_bar", N, "Pump head, bar, to compute pump kW."), ("pump_efficiency_pct", N, "Pump efficiency, % (default 65).")),
         ("sprinkler demand", "sprinkler design", "sprinkler flow", "hazard class", "sprinkler density", "fire pump power")),
    Calc("hot_water_heater_sizing", "HotWaterHeaterSizingSkill", "Hot Water Heater Sizing", "PLUMBING", F.hot_water_heater,
         (("storage_volume_l", N, "Storage volume, L."),),
         (("cold_water_c", N, "Cold water temperature, deg C (default 25)."), ("hot_water_c", N, "Delivery temperature, deg C (default 55)."),
          ("heat_up_time_h", N, "Heat-up time, h (default 2)."), ("heater_efficiency_pct", N, "Efficiency or COP in %, default 95.")),
         ("water heater", "geyser", "hot water heater", "hot water storage", "heat pump water heater")),
    Calc("rainwater_drainage", "RainwaterDrainageSkill", "Rainwater Drainage Sizing", "PLUMBING", F.rainwater_drainage,
         (("catchment_area_m2", N, "Roof/paved catchment area, m2."), ("rainfall_intensity_mm_h", N, "Design rainfall intensity, mm/h.")),
         (("runoff_coefficient", N, "Runoff coefficient (default 0.9)."), ("pipe_slope", N, "Pipe slope, m/m (default 0.01)."), ("manning_n", N, "Manning n (default 0.013).")),
         ("rainwater", "storm water", "stormwater", "roof drain", "rainfall drainage", "rain water pipe")),
    Calc("solar_pv_sizing", "SolarPVSizingSkill", "Solar PV Sizing", "ENERGY", F.solar_pv_sizing,
         (("annual_consumption_kwh", N, "Annual electricity consumption, kWh."),),
         (("offset_pct", N, "Share of consumption to offset, % (default 100)."), ("specific_yield_kwh_kwp_yr", N, "Specific yield, kWh/kWp/year (default 1500)."),
          ("area_per_kwp_m2", N, "Roof area per kWp, m2 (default 6)."), ("available_area_m2", N, "Available roof area, m2.")),
         ("solar pv", "rooftop solar", "kwp of solar", "solar plant size", "solar sizing", "solar capacity")),
    Calc("carbon_emissions", "CarbonEmissionsSkill", "Carbon Emissions Estimate", "ENERGY", F.carbon_emissions,
         (("annual_consumption_kwh", N, "Annual electricity consumption, kWh."),),
         (("grid_factor_kg_kwh", N, "Grid emission factor, kg CO2e/kWh."), ("reduction_kwh", N, "Annual kWh saving to convert to avoided CO2e."),
          ("refrigerant_charge_kg", N, "Refrigerant charge, kg."), ("leak_rate_pct", N, "Annual leak rate, %."), ("refrigerant_gwp", N, "Refrigerant GWP.")),
         ("carbon emissions", "co2 emissions", "tco2e", "scope 2", "carbon footprint", "emission factor")),
)

BY_ID: Dict[str, Calc] = {c.skill_id: c for c in CALCULATORS}


def make_skill_class(calc: Calc):
    def validate(self, request: SkillRequest):
        missing = [n for n, _, _ in calc.required if request.inputs.get(n) in (None, "")]
        return [f"Missing required input: {n}" for n in missing]

    def run(self, request: SkillRequest) -> SkillResult:
        errors = self.validate(request)
        if errors:
            return SkillResult(skill_id=calc.skill_id, status="input_validation_failed", validation_errors=errors,
                               source_revision=SOURCE_REV, skill_version=VERSION)
        try:
            result, trace, assumptions, warnings = calc.fn(dict(request.inputs))
        except F.CalcError as exc:
            return SkillResult(skill_id=calc.skill_id, status="input_validation_failed", validation_errors=[str(exc)],
                               source_revision=SOURCE_REV, skill_version=VERSION)
        except (ArithmeticError, ValueError, TypeError) as exc:
            return SkillResult(skill_id=calc.skill_id, status="calculation_failed", validation_errors=[f"{type(exc).__name__}: {exc}"],
                               source_revision=SOURCE_REV, skill_version=VERSION)
        warnings = list(warnings) + ["Preliminary calculation for engineering review; verify against project standards and vendor data before use."]
        return SkillResult(skill_id=calc.skill_id, status="draft_ready", engineering_result=result, assumptions=assumptions,
                           warnings=warnings, calculation_trace=trace, source_revision=SOURCE_REV, skill_version=VERSION)

    return type(calc.class_name, (), {"skill_id": calc.skill_id, "version": VERSION, "source_revision": SOURCE_REV,
                                      "validate": validate, "run": run, "__module__": "skills.calculators.adapters"})
