P = {}
P["1. HVAC loads and design"] = [
"""HVAC design package, room by room load, airflow, duct sizing and equipment schedule for an office building in New Delhi. Design conditions: outdoor 43 C DB / 23 C WB summer, indoor 24 C and 50% RH.
Rooms:
Reception, 60 sqm, 10 people
Open office, 250 sqm, 60 people
Conference room 1, 40 sqm, 20 people
MD cabin, 25 sqm, 4 people
Server room, 30 sqm, 2 people
Cafeteria, 80 sqm, 40 people""",
"""Design HVAC for a hospital ward block in Mumbai.
Rooms:
Patient ward, 150 sqm, 12 people
Nurse station, 20 sqm, 3 people
Doctor room, 18 sqm, 2 people
Treatment room, 25 sqm, 4 people""",
"Estimate the cooling load for a 25000 sq ft IT office in Hyderabad with 180 people, composite climate",
"Calculate the cooling coil load for 12000 m3/h airflow, entering air 35 C 50% RH, leaving air 14 C 90% RH",
"Calculate the ventilation rate for a 400 m2 office floor with 60 occupants, space type office",
]
P["2. HVAC plant and distribution"] = [
"Select chillers for 450 TR total load, chiller efficiency 0.65 kW/TR, 4500 annual hours, load factor 70%, tariff Rs 9 per kWh, redundancy N+1",
"Size a cooling tower for direct heat rejection of 2000 kW: range 5.5 C, wet bulb 28 C, approach 4 C, cycles of concentration 4, drift 0.01 %",
"Size a rectangular supply air duct for 8500 CFM using the velocity method at 5 m/s",
"Calculate pump head for 120 m3/hr chilled water flow, pipe diameter 200 mm, straight length 150 m, static head 25 m and margin 10 %",
"Size the expansion tank for system volume 5000 litres, max temperature 45 C, fill pressure 1.5 bar g, max pressure 6 bar g",
]
P["3. Energy audit and decarbonisation"] = [
"Energy payback for replacing an old 300 TR chiller at 1.1 kW/TR with a new 300 TR chiller at 0.6 kW/TR, 4000 annual hours, load factor 65%, tariff Rs 9 per kWh, investment Rs 1.2 crore",
"VFD energy savings for a 55 kW chilled water pump, speed reduction 20%, static head 30%, 6000 annual hours, tariff Rs 8 per kWh",
"HVAC decarbonisation for annual energy 1,800,000 kWh at tariff Rs 9 per kWh",
"""Energy optimisation study for annual consumption 2,400,000 kWh and tariff Rs 9 per kWh.
Measures:
VFD on chilled water pumps | vfd | 55 kW | speed reduction 20% | static head 30% | 6000 hours | investment Rs 4 lakh
Rooftop solar | solar | 150 kWp | investment Rs 75 lakh
LED lighting retrofit | saves 120000 kWh | investment Rs 18 lakh""",
"""Retrofit study for an existing chiller plant, tariff Rs 9 per kWh, measured consumption 2,100,000 kWh.
Survey:
Chiller 1 | 400 kW | load factor 70% | 4500 hours
Chilled water pump | 55 kW | load factor 80% | 6000 hours
Cooling tower fan | 22 kW | load factor 75% | 4500 hours
Measures:
Replace chiller 1 | existing 0.9 kW/TR | new 0.6 kW/TR | survey item Chiller 1 | investment Rs 1.5 crore
VFD on pump | vfd | 55 kW | speed reduction 20% | static head 30% | 6000 hours | investment Rs 4 lakh""",
]
P["4. Electrical"] = [
"Size a transformer for a connected load of 850 kW",
"Size a generator for a connected load of 600 kW",
"Cable voltage drop for a 75 kW load over a 120 m cable run",
"VFD derating for a 90 kW motor at ambient 45 C and altitude 1200 m",
"Harmonic screening for total VFD load 400 kVA on a transformer 1000 kVA",
]
P["5. Fire protection"] = [
"Fire water storage for required flow 2850 lpm for a duration of 120 min",
"Sprinkler demand for ordinary hazard group 2 with a design area of 139 sqm",
"Fire water storage for a 5 floor office building: required flow 2850 lpm for a duration of 2 hours",
"Fire water storage for flow 4500 lpm and duration 90 min",
"Sprinkler demand for light hazard occupancy",
]
P["6. Plumbing"] = [
"Domestic water tank sizing for 470 occupants",
"Plumbing water demand for 20 water closets at 10 lpm, 10 urinals at 6 lpm and 20 wash basins at 6 lpm",
"Hot water heater sizing for storage volume 500 litres",
"Rainwater drainage for catchment area 1200 m2 and rainfall intensity 100 mm/h",
"Domestic water tank sizing for 1200 occupants in a hospital",
]
P["7. BMS"] = [
"Size the BMS controllers for 1200 total points, 40 points per controller and 6 controllers per panel",
"BMS alarm evaluation for point type analog, point id AHU1_SAT and value 19",
"Generate BMS points for 6 AHUs, 2 chillers and 4 pumps with 40 points per controller and 6 controllers per panel",
"BMS cost estimation for 6 AHUs, 2 chillers, 8 pumps and 4 VFDs with 40 points per controller and 6 controllers per panel, 60 misc points, cost per point Rs 4500, cost per controller Rs 60000, cost per panel Rs 150000, software Rs 5 lakh and engineering 10 %",
"Size the BMS controllers for 600 total points with 32 points per controller and 8 controllers per panel",
]
P["8. Commercial BOQ"] = [
"BOQ takeoff for gypsum false ceiling 1200 sqft, vitrified tile flooring 800 sqft, gypsum wall partition 1500 sqft",
"Material takeoff for GI duct fabrication 450 sqm, duct thermal insulation 450 sqm, cable tray 300 m",
"""Deviation statement for tender compliance.
Clause 4.1 Chiller COP | 5.8 | 5.6 | partial | Offered COP slightly lower
Clause 4.2 Cooling capacity | 450 TR | 450 TR | comply
Clause 5.3 Refrigerant | R134a | R513A | deviate | Lower GWP alternative
Clause 6.1 BMS interface | BACnet | BACnet | comply""",
"""HVAC BOQ with contingency 5 %, overhead 10 % and GST 18 %.
Category: Ducting
GI sheet metal duct | kg | 4500 | 220
Duct insulation | sqm | 450 | 480
Category: Piping
MS chilled water pipe 150 mm | m | 400 | 3200
Valves and fittings | lot | 1 | 450000""",
"Quantity takeoff for MS chilled water pipe 400 m and fresh air louvers 12 sqm",
]
P["9. MEP building"] = [
"""Generate MEP BOQ and layout for a 5 floor office building in Delhi.
Floor: Typical floor x5
Open office | 250 sqm | 60 people
Conference room | 40 sqm | 20 people
MD cabin | 25 sqm | 4 people
Pantry | 30 sqm | 10 people
Server room | 30 sqm | 2 people
Reception | 60 sqm | 10 people""",
"""Generate MEP BOQ for a hospital building.
Floor: Ground x1
OPD hall | 300 sqm | 80 people
Pharmacy | 40 sqm | 6 people
Floor: Ward floor x4
Patient ward | 200 sqm | 24 people
Nurse station | 30 sqm | 5 people
Treatment room | 40 sqm | 6 people""",
"""Generate MEP BOQ for a 3 floor retail mall.
Floor: Retail floor x3
Shop area | 600 sqm | 150 people
Food court | 200 sqm | 120 people
Corridor | 150 sqm | 40 people""",
"""Generate MEP BOQ for a 10 floor hotel building.
Floor: Guest floor x9
Guest room | 30 sqm | 2 people
Guest room | 30 sqm | 2 people
Corridor | 60 sqm | 10 people
Floor: Lobby floor x1
Lobby | 250 sqm | 60 people
Restaurant | 200 sqm | 120 people""",
"""Generate MEP BOQ for a 5 floor school building.
Floor: Classroom floor x5
Classroom | 60 sqm | 40 people
Classroom 2 | 60 sqm | 40 people
Staff room | 40 sqm | 10 people
Library | 100 sqm | 30 people""",
]
P["10. Specialised HVAC and envelope"] = [
"Cleanroom air changes for an ISO 7 cleanroom 12 m long, 8 m wide, 3 m high",
"""VRF sizing with combination ratio 120 %.
Zones:
Zone A, 120 sqm, 150 W/sqm
Zone B, 80 sqm, 180 W/sqm
Zone C, 60 sqm, 200 W/sqm
Zone D, 45 sqm, 160 W/sqm""",
"Refrigerant pipe sizing for R410A, capacity 50 kW, suction velocity 10 m/s, liquid velocity 1 m/s, suction line length 30 m, liquid line length 30 m",
"""Facade U-factor calculation for a curtain wall facade.
Double glazed unit, 450 sqm, U 1.8
Spandrel panel, 120 sqm, U 0.6
Aluminium frame, 60 sqm, U 3.5""",
"Insulation condensation check for a chilled water pipe at fluid 7 C, outer diameter 60 mm, ambient 35 C 70% RH",
]
