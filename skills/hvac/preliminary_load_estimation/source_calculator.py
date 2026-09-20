"""Controlled snapshot of hvac---load---estimator/calculator.py."""
import math
BUILDING_TYPES={"office":{"label":"Office / Commercial","base_sqft_per_ton":550},"retail":{"label":"Retail / Showroom","base_sqft_per_ton":450},"residential":{"label":"Residential","base_sqft_per_ton":650},"hospital":{"label":"Hospital / Healthcare","base_sqft_per_ton":400},"server_room":{"label":"Server Room / Data Center","base_sqft_per_ton":120},"restaurant":{"label":"Restaurant / F&B","base_sqft_per_ton":350},"auditorium":{"label":"Auditorium / Banquet Hall","base_sqft_per_ton":250},"hotel":{"label":"Hotel / Hospitality","base_sqft_per_ton":500},"educational":{"label":"Educational Institution","base_sqft_per_ton":500}}
CLIMATE_ZONES={"hot_dry":{"label":"Hot & Dry (e.g. Delhi NCR, Jaipur, Ahmedabad)","multiplier":1.00},"warm_humid":{"label":"Warm & Humid (e.g. Mumbai, Chennai, Kolkata)","multiplier":1.15},"composite":{"label":"Composite (e.g. Lucknow, Kanpur, Bhopal)","multiplier":1.05},"moderate":{"label":"Moderate (e.g. Bengaluru, Pune)","multiplier":0.82},"cold":{"label":"Cold (e.g. Shimla, Srinagar)","multiplier":0.60}}
STANDARD_OCCUPANCY_DENSITY={"office":1.0,"retail":1.5,"residential":0.4,"hospital":1.2,"server_room":0.1,"restaurant":2.5,"auditorium":5.0,"hotel":0.8,"educational":3.0}
TONS_PER_EXTRA_OCCUPANT=400/12000

def _round_up_to_half(value): return math.ceil(value*2)/2

def _suggest_equipment(tonnage):
    if tonnage<=5: return "Split / Ductable Split units (multiple units likely)"
    if tonnage<=20: return "Package Unit or small VRF system"
    if tonnage<=100: return "VRF/VRV system or air-cooled chiller"
    return "Water-cooled chiller plant with cooling tower"

def estimate_load(building_type, area_sqft, climate_zone, occupancy=None):
    if building_type not in BUILDING_TYPES: raise ValueError(f"Unknown building type: {building_type}")
    if climate_zone not in CLIMATE_ZONES: raise ValueError(f"Unknown climate zone: {climate_zone}")
    if area_sqft<=0: raise ValueError("Area must be greater than zero")
    bt=BUILDING_TYPES[building_type]; cz=CLIMATE_ZONES[climate_zone]
    effective_sqft_per_ton=bt["base_sqft_per_ton"]/cz["multiplier"]
    base_tonnage=area_sqft/effective_sqft_per_ton
    occupancy_addon=0.0; standard_occupants=0; extra_occupants=0
    if occupancy is not None and occupancy>0:
        standard_occupants=round((area_sqft/100)*STANDARD_OCCUPANCY_DENSITY[building_type])
        extra_occupants=max(0, occupancy-standard_occupants)
        occupancy_addon=extra_occupants*TONS_PER_EXTRA_OCCUPANT
    total_tonnage=base_tonnage+occupancy_addon
    return {"building_type_label":bt["label"],"climate_zone_label":cz["label"],"area_sqft":area_sqft,"base_sqft_per_ton":bt["base_sqft_per_ton"],"climate_multiplier":cz["multiplier"],"effective_sqft_per_ton":round(effective_sqft_per_ton,1),"base_tonnage":round(base_tonnage,2),"standard_occupants_assumed":standard_occupants,"actual_occupancy":occupancy,"extra_occupants":extra_occupants,"occupancy_addon_tons":round(occupancy_addon,2),"total_tonnage_raw":round(total_tonnage,2),"recommended_tonnage":_round_up_to_half(total_tonnage),"suggested_equipment":_suggest_equipment(_round_up_to_half(total_tonnage))}
