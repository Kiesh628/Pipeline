import os
import csv
from pathlib import Path
from typing import Literal, Any


from building_modelling.topology import BIM_Node, MaterialLayer, Construction, Room
from building_modelling.hvac import PlantSystem, AirLoop, ZoneTerminal, Thermostat
from diagnosis import Mutation, DataSwap

current_dir = os.path.dirname(os.path.abspath(__file__))

def safe_float(val: str | None) -> float | None:
    if val and val.strip():
        return float(val)
    return None

def safe_int(val: str | None) -> int | None:
    if val and val.strip():
        return int(val)
    return None

def node_packer(lookup_type: Literal['constructions', 'materials', 'room_loads', 'schedules', 'hvac_equipment', 'hvac_templates'],
                name: str) -> BIM_Node | None:
    csv_path = Path(os.path.join(current_dir, "lookup_tables", f"{lookup_type}.csv"))
    
    if not csv_path.exists():
        raise FileNotFoundError(f'{csv_path} not found')
    
    data_row: dict[str, str] = {}
    with open(csv_path, mode='r', newline='', encoding='utf-8') as lookup_table:
        reader = csv.DictReader(lookup_table)
        if not reader.fieldnames:
            return None
        first_column: str = reader.fieldnames[0]
        
        for row in reader:
            if row[first_column] == name:
                data_row = dict(row)
                break
                
    if not data_row:
        return None
    
    match lookup_type:
        case 'materials':
            return MaterialLayer(
                guid=None, 
                name=data_row.get("Material_Name"),
                thickness=safe_float(data_row.get("Thickness_m")),
                material_name=data_row.get("Material_Name"),
                conductivity=safe_float(data_row.get("Conductivity_W_mK")),
                density=safe_float(data_row.get("Density_kg_m3")),
                specific_heat=safe_float(data_row.get("Specific_Heat_J_kgK")),
                resistance=safe_float(data_row.get("Thermal_Resistance_m2K_W"))
            )
            
        case 'constructions':
            return Construction(
                guid=None,
                name=data_row.get("Construction_Name", ""),
                u_value=safe_float(data_row.get("U_Value_W_m2K")),
                resistance=safe_float(data_row.get("R_Value_m2K_W")),
                layer_count=safe_int(data_row.get("Layer_Count")),
                outside_material=data_row.get("Outside_Material"),
                inside_material=data_row.get("Inside_Material"),
                area_heat_capacity=safe_float(data_row.get("Area_Heat_Capacity_J_m2K")),
                solar_absorptance=safe_float(data_row.get("Solar_Absorptance"))
            )
            
        case 'room_loads':
            room_name = data_row.get("Template_Name") or data_row.get("Room_Type", "")
            room = Room(guid=None, name=room_name)
            room.lighting_load = safe_float(data_row.get("Lighting_Load_W_m2") or data_row.get("Lighting_W_m2"))
            room.equipment_load = safe_float(data_row.get("Equipment_Load_W_m2") or data_row.get("Equipment_W_m2"))
            room.people_density = safe_float(data_row.get("People_Density_per_m2"))
            room.occupant_sensible_heat = safe_float(data_row.get("Occupant_Sensible_W") or data_row.get("Sensible_Heat_W_person"))
            room.occupant_latent_heat = safe_float(data_row.get("Occupant_Latent_W") or data_row.get("Latent_Heat_W_person"))
            room.infiltration_rate = safe_float(data_row.get("Infiltration_ACH") or data_row.get("Infiltration_m3_s_m2"))
            room.ventilation_rate = safe_float(data_row.get("Ventilation_L_s_person"))
            return room
            
        case 'schedules':
            room = Room(guid=None, name=data_row.get("Template_Name", ""))
            room.occupancy_schedule = data_row.get("Occupancy_Schedule")
            room.lighting_schedule = data_row.get("Lighting_Schedule")
            room.equipment_schedule = data_row.get("Equipment_Schedule")
            return room
            
        case 'hvac_equipment':
            category = data_row.get("Category")
            eq_type: Any = data_row.get("Type")
            if category == 'PlantSystem':
                plant = PlantSystem(guid=None, name=data_row.get("Equipment_Name", ""), plant_type=eq_type)
                plant.efficiency = safe_float(data_row.get("Efficiency"))
                plant.min_supply_temp = safe_float(data_row.get("Min_Supply_Temp_C"))
                plant.max_supply_temp = safe_float(data_row.get("Max_Supply_Temp_C"))
                if plant.min_supply_temp is None or plant.max_supply_temp is None:
                    design = safe_float(data_row.get("Design_Supply_Temp_C"))
                    if eq_type == "Chiller":
                        plant.min_supply_temp, plant.max_supply_temp = 5.5, 11.0
                    elif eq_type == "HeatPump":
                        plant.min_supply_temp, plant.max_supply_temp = 30.0, 50.0
                    elif eq_type == "Boiler":
                        plant.min_supply_temp, plant.max_supply_temp = 45.0, 82.0
                    elif design is not None:
                        plant.min_supply_temp, plant.max_supply_temp = design - 5.0, design + 5.0
                fuel: Any = data_row.get("Fuel_Type")
                if fuel and fuel != "None":
                    plant.fuel_type = fuel
                return plant
            elif category == 'ZoneTerminal':
                terminal = ZoneTerminal(guid=None, name=data_row.get("Equipment_Name", ""), terminal_type=eq_type)
                terminal.efficiency = safe_float(data_row.get("Efficiency"))
                terminal.min_supply_temp = safe_float(data_row.get("Min_Supply_Temp_C"))
                terminal.max_supply_temp = safe_float(data_row.get("Max_Supply_Temp_C"))
                return terminal
        
    return None

def unpack_hvac_template(template_name: str, target_room: Room) -> list[Mutation]:
    """
    Unpacks an HVAC template (e.g. 'VAV_Chiller_Boiler') into real PlantSystem,
    AirLoop, ZoneTerminal, and Thermostat nodes, returning the exact mutations
    needed to graft them into the building model.
    """
    # 1. Look up the template in hvac_templates.csv
    csv_path = Path(os.path.join(current_dir, "lookup_tables", "hvac_templates.csv"))
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found")
        
    family = "VAV"
    with open(csv_path, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Template_Name") == template_name:
                family = row.get("System_Family", "VAV")
                break
                
    # 2. Check for existing central plant in BIM_Node.registry, or instantiate new ones
    cooling_type = "None"
    if "Chiller" in template_name:
        cooling_type = "Chiller"
    elif "HeatPump" in template_name or "ASHP" in template_name or family in ("VRF", "WSHP"):
        cooling_type = "HeatPump"

    cooling_plant: PlantSystem | None = None
    match cooling_type:
        case "Chiller":
            existing_chillers = [n for n in BIM_Node.registry if isinstance(n, PlantSystem) and n.plant_type == "Chiller"]
            if existing_chillers:
                cooling_plant = existing_chillers[0]
            else:
                cooling_plant = PlantSystem(name="Central_Chiller", plant_type="Chiller")
                cooling_plant.fuel_type = "Electricity"
                cooling_plant.efficiency = 5.80
                cooling_plant.min_supply_temp = 5.5
                cooling_plant.max_supply_temp = 11.0
        case "HeatPump":
            existing_hps = [n for n in BIM_Node.registry if isinstance(n, PlantSystem) and n.plant_type == "HeatPump"]
            if existing_hps:
                cooling_plant = existing_hps[0]
            else:
                cooling_plant = PlantSystem(name="Central_HeatPump", plant_type="HeatPump")
                cooling_plant.fuel_type = "Electricity"
                cooling_plant.efficiency = 3.50
                cooling_plant.min_supply_temp = 30.0
                cooling_plant.max_supply_temp = 50.0
        case _:
            cooling_plant = None

    heating_type = "None"
    if "Boiler" in template_name:
        heating_type = "Boiler"
    elif cooling_plant and cooling_plant.plant_type == "HeatPump":
        heating_type = "HeatPump"

    heating_plant: PlantSystem | None = None
    match heating_type:
        case "Boiler":
            existing_boilers = [n for n in BIM_Node.registry if isinstance(n, PlantSystem) and n.plant_type == "Boiler"]
            if existing_boilers:
                heating_plant = existing_boilers[0]
            else:
                heating_plant = PlantSystem(name="Central_Boiler", plant_type="Boiler")
                heating_plant.fuel_type = "NaturalGas"
                heating_plant.efficiency = 0.92
                heating_plant.min_supply_temp = 45.0
                heating_plant.max_supply_temp = 82.0
        case "HeatPump":
            heating_plant = cooling_plant
        case _:
            heating_plant = None

    # 3. Check for existing AirLoop or instantiate
    ahu: AirLoop | None = None
    match family:
        case "VAV" | "PVAV" | "FCUwithDOAS" | "VRFwithDOAS" | "RadiantwithDOAS" | "WSHPwithDOAS":
            existing_ahus = [n for n in BIM_Node.registry if isinstance(n, AirLoop)]
            if existing_ahus:
                ahu = existing_ahus[0]
            else:
                ahu = AirLoop(name="Central_AHU")
                ahu.design_air_flow_rate = 2.5
                ahu.fan_efficiency = 0.65
                if cooling_plant and ahu not in cooling_plant.served_air_loops:
                    ahu.cooling_source = cooling_plant
                    cooling_plant.served_air_loops.append(ahu)
                if heating_plant and ahu not in heating_plant.served_air_loops:
                    ahu.heating_source = heating_plant
                    heating_plant.served_air_loops.append(ahu)

        case "PSZ" | "ForcedAirFurnace":
            ahu = AirLoop(name=f"{target_room.name}_PSZ_AHU")
            ahu.design_air_flow_rate = 0.5
            ahu.fan_efficiency = 0.60
            if cooling_plant and ahu not in cooling_plant.served_air_loops:
                ahu.cooling_source = cooling_plant
                cooling_plant.served_air_loops.append(ahu)
            if heating_plant and ahu not in heating_plant.served_air_loops:
                ahu.heating_source = heating_plant
                heating_plant.served_air_loops.append(ahu)

        case _:
            ahu = None

    # 4. Instantiate the ZoneTerminal for this Room
    terminal: ZoneTerminal
    match family:
        case "VAV" | "PVAV":
            terminal = ZoneTerminal(name=f"{target_room.name}_VAV", terminal_type="VAV")
            terminal.air_loop = ahu
            if heating_plant:
                terminal.heating_source = heating_plant

        case "PSZ" | "ForcedAirFurnace":
            terminal = ZoneTerminal(name=f"{target_room.name}_CAV", terminal_type="CAV")
            terminal.air_loop = ahu

        case "FCU" | "FCUwithDOAS":
            terminal = ZoneTerminal(name=f"{target_room.name}_FCU", terminal_type="FCU")
            terminal.cooling_source = cooling_plant
            terminal.heating_source = heating_plant

        case "Radiant" | "RadiantwithDOAS" | "Baseboard":
            terminal = ZoneTerminal(name=f"{target_room.name}_Radiator", terminal_type="Radiator")
            terminal.heating_source = heating_plant

        case "PTAC" | "WindowAC":
            terminal = ZoneTerminal(name=f"{target_room.name}_PTAC", terminal_type="PTAC")
            terminal.efficiency = 3.00
            terminal.min_supply_temp = 12.0
            terminal.max_supply_temp = 40.0

        case "VRF" | "VRFwithDOAS":
            terminal = ZoneTerminal(name=f"{target_room.name}_VRF", terminal_type="FCU")
            terminal.cooling_source = cooling_plant
            terminal.heating_source = heating_plant

        case _:
            terminal = ZoneTerminal(name=f"{target_room.name}_SplitAC", terminal_type="SplitAC")
            terminal.efficiency = 3.80
            terminal.min_supply_temp = 12.0
            terminal.max_supply_temp = 25.0

    terminal.room = target_room
    if ahu and terminal not in ahu.served_terminals:
        ahu.served_terminals.append(terminal)
    if cooling_plant and terminal not in cooling_plant.served_terminals and not ahu:
        cooling_plant.served_terminals.append(terminal)
    if heating_plant and terminal not in heating_plant.served_terminals and not ahu:
        heating_plant.served_terminals.append(terminal)

    # 5. Build Mutations for the Room
    mutations: list[Mutation] = [
        Mutation(node=target_room, variable_name='equipment', new_value=terminal, operation='Append')
    ]
    
    # 6. Ensure Room Thermostat is present and controls the terminal
    if target_room.thermostat is None:
        import uuid
        thermo = Thermostat(guid=str(uuid.uuid4()), name=f"{target_room.name}_Thermostat")
        thermo.room = target_room
        thermo.controls_terminal = terminal
        thermo.heating_setpoint = 21.0
        thermo.cooling_setpoint = 24.0
        mutations.append(Mutation(node=target_room, variable_name='thermostat', new_value=thermo, operation='Set'))
    else:
        target_room.thermostat.controls_terminal = terminal

    return mutations

def swap(dataswap: DataSwap, selected_name: str) -> list[Mutation]:
    return dataswap.resolve(selected_name)

