import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
from pyenergyplus.api import EnergyPlusAPI

from building_modelling import BIM_Node
from building_modelling.topology import Model, Room
from building_modelling.hvac import ZoneTerminal, AirLoop, PlantSystem
from diagnosis import Mutation
from consts import SIMULATION_OUTPUT_FOLDER
from convert import generate_sizing_idf, ensure_safe_name

# Global cache to prevent redundant EnergyPlus sizing runs
_SIZING_RESULTS_CACHE: dict[int, dict[str, Any]] = {}

def clear_sizing_cache():
    """Clears the internal sizing cache."""
    global _SIZING_RESULTS_CACHE
    _SIZING_RESULTS_CACHE.clear()

def _get_parent_model(equipment: ZoneTerminal | AirLoop | PlantSystem) -> Model:
    """Finds the parent Model node associated with this HVAC equipment."""
    # 1. From ZoneTerminal -> Room -> Floor -> Model
    if isinstance(equipment, ZoneTerminal):
        if equipment.room and equipment.room.floor and equipment.room.floor.building:
            return equipment.room.floor.building
            
    # 2. From AirLoop -> served terminals -> Room -> Model
    if isinstance(equipment, AirLoop) and equipment.served_terminals:
        for term in equipment.served_terminals:
            if term.room and term.room.floor and term.room.floor.building:
                return term.room.floor.building
                
    # 3. From PlantSystem -> served terminals or air loops -> Model
    if isinstance(equipment, PlantSystem):
        for term in equipment.served_terminals:
            if term.room and term.room.floor and term.room.floor.building:
                return term.room.floor.building
        for loop in equipment.served_air_loops:
            for term in loop.served_terminals:
                if term.room and term.room.floor and term.room.floor.building:
                    return term.room.floor.building
                    
    # 4. Fallback: Lookup in BIM_Node.registry
    models = [n for n in BIM_Node.registry if isinstance(n, Model)]
    if models:
        return models[0]
        
    raise ValueError(f"Could not locate parent building Model for equipment '{equipment.name}'")

def run_model_sizing_pass(model: Model) -> dict[str, Any]:
    """
    Executes the EnergyPlus design-day sizing pass for the entire building model
    and parses zone peak loads and required air and water flow rates.
    Caches the results to prevent re-simulating on subsequent calls.
    """
    model_id = id(model)
    if model_id in _SIZING_RESULTS_CACHE:
        return _SIZING_RESULTS_CACHE[model_id]
        
    sizing_dir = SIMULATION_OUTPUT_FOLDER / "sizing"
    sizing_dir.mkdir(parents=True, exist_ok=True)
    
    idf_path = sizing_dir / "sizing_model.idf"
    generate_sizing_idf(model, idf_path)
    
    weather_file = model.site.weather_file if model.site and model.site.weather_file else None
    if not weather_file or not os.path.exists(weather_file):
        raise FileNotFoundError(f"Weather file not configured on site or missing: {weather_file}")
        
    # Execute EnergyPlus design-day sizing pass
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()
    args: list[str | bytes] = [
        "-d", str(sizing_dir.absolute()),
        "-w", str(Path(weather_file).absolute()),
        str(idf_path.absolute())
    ]
    code = api.runtime.run_energyplus(state, args)
    api.state_manager.delete_state(state)
    
    if code != 0:
        err_file = sizing_dir / "eplusout.err"
        err_msg = ""
        if err_file.exists():
            with open(err_file, "r", encoding="utf-8", errors="ignore") as f:
                err_msg = f.read()[-1000:]
        raise RuntimeError(f"EnergyPlus sizing simulation failed with exit code {code}.\n{err_msg}")
        
    # Parse epluszsz.csv for Zone Design Day sizing peaks
    zsz_csv = sizing_dir / "epluszsz.csv"
    if not zsz_csv.exists():
        raise FileNotFoundError(f"Expected sizing output file not found: {zsz_csv}")
        
    df = pd.read_csv(zsz_csv)
    
    # Air & Water thermal constants
    air_density = 1.204   # kg/m3
    rho_cp_delta_t_water = 1000.0 * 4180.0 * 5.5  # J/m3 (5.5 C delta-T for chilled/hot water)
    
    zone_results: dict[str, dict[str, float]] = {}
    
    # Identify unique zone names from columns (Format: "ZONENAME:ENVNAME:FIELD")
    col_pattern = re.compile(r"^([^:]+):")
    zone_names = set()
    for col in df.columns:
        m = col_pattern.match(col)
        if m:
            zone_names.add(m.group(1).strip())
            
    def _safe_max_col(col_list: list[str]) -> float:
        m_val = 0.0
        for c in col_list:
            try:
                v = df[c].max()
                m_val = max(m_val, float(v)) # type: ignore
            except (ValueError, TypeError):
                pass
        return m_val

    for zone in zone_names:
        # Find maximum loads and mass flows across all design periods
        cool_load_cols = [c for c in df.columns if c.startswith(zone) and "Des Sens Cool Load" in c]
        heat_load_cols = [c for c in df.columns if c.startswith(zone) and "Des Heat Load" in c]
        cool_flow_cols = [c for c in df.columns if c.startswith(zone) and "Des Cool Mass Flow" in c]
        heat_flow_cols = [c for c in df.columns if c.startswith(zone) and "Des Heat Mass Flow" in c]
        
        max_cool_load: float = _safe_max_col(cool_load_cols)
        max_heat_load: float = _safe_max_col(heat_load_cols)
        max_cool_mass_flow: float = _safe_max_col(cool_flow_cols)
        max_heat_mass_flow: float = _safe_max_col(heat_flow_cols)
        
        peak_mass_flow = max(max_cool_mass_flow, max_heat_mass_flow)
        peak_volume_flow = peak_mass_flow / air_density if air_density > 0 else 0.0
        
        peak_load = max(max_cool_load, max_heat_load)
        water_flow = peak_load / rho_cp_delta_t_water if rho_cp_delta_t_water > 0 else 0.0
        
        # Sizing minimum threshold (avoid exact 0)
        if peak_volume_flow < 0.01:
            peak_volume_flow = 0.015
        if water_flow < 0.00005:
            water_flow = 0.0001
            
        zone_results[zone] = {
            "cooling_load_w": max_cool_load,
            "heating_load_w": max_heat_load,
            "peak_air_flow_m3s": peak_volume_flow,
            "peak_water_flow_m3s": water_flow
        }
        
    parsed = {"zones": zone_results}
    _SIZING_RESULTS_CACHE[model_id] = parsed
    return parsed

def autosize(equipment: ZoneTerminal | AirLoop | PlantSystem) -> list[Mutation]:
    """
    Autosizes an individual HVAC equipment node by running (or retrieving)
    the EnergyPlus design-day sizing pass for its parent building,
    and returns the list of Mutations containing the exact calculated physical ratings.
    """
    model = _get_parent_model(equipment)
    sizing_data = run_model_sizing_pass(model)
    mutations: list[Mutation] = []
    
    # -------------------------------------------------------------------------
    # 1. ZoneTerminal Autosizing
    # -------------------------------------------------------------------------
    if isinstance(equipment, ZoneTerminal):
        if not equipment.room:
            raise ValueError(f"ZoneTerminal '{equipment.name}' is not assigned to any Room.")
            
        safe_room = ensure_safe_name(equipment.room.name).upper()
        # Search zone results case-insensitively
        z_vals = None
        for z_name, vals in sizing_data["zones"].items():
            if z_name.upper() == safe_room:
                z_vals = vals
                break
                
        if not z_vals:
            # Fallback if zone name was formatted differently
            z_vals = next(iter(sizing_data["zones"].values()), {
                "peak_air_flow_m3s": 0.05,
                "peak_water_flow_m3s": 0.0002,
                "cooling_load_w": 1000.0,
                "heating_load_w": 500.0
            })
            
        # Air flow rate (for VAV, CAV, FCU, SplitAC, PTAC)
        if equipment.terminal_type in ["VAV", "CAV", "SplitAC", "PTAC", "FCU"]:
            mutations.append(Mutation(
                node=equipment,
                variable_name="max_air_flow_rate",
                new_value=round(z_vals["peak_air_flow_m3s"], 4),
                operation="Set"
            ))
            
        # Hydronic water flow rate (for FCU, Radiator)
        if equipment.terminal_type in ["FCU", "Radiator"]:
            mutations.append(Mutation(
                node=equipment,
                variable_name="max_water_flow_rate",
                new_value=round(z_vals["peak_water_flow_m3s"], 5),
                operation="Set"
            ))
            
    # -------------------------------------------------------------------------
    # 2. AirLoop (AHU) Autosizing
    # -------------------------------------------------------------------------
    elif isinstance(equipment, AirLoop):
        if not equipment.served_terminals:
            raise ValueError(f"AirLoop '{equipment.name}' has no served terminals connected.")
            
        total_terminal_airflow = 0.0
        for term in equipment.served_terminals:
            if term.room:
                safe_room = ensure_safe_name(term.room.name).upper()
                for z_name, vals in sizing_data["zones"].items():
                    if z_name.upper() == safe_room:
                        total_terminal_airflow += vals["peak_air_flow_m3s"]
                        break
                        
        # Apply diversity factor: VAV diversity ~ 0.90, CAV ~ 1.0
        diversity = 0.90 if any(t.terminal_type == "VAV" for t in equipment.served_terminals) else 1.0
        design_loop_flow = max(total_terminal_airflow * diversity, 0.05)
        
        mutations.append(Mutation(
            node=equipment,
            variable_name="design_air_flow_rate",
            new_value=round(design_loop_flow, 3),
            operation="Set"
        ))
        
    # -------------------------------------------------------------------------
    # 3. PlantSystem (Chiller, Boiler, HeatPump) Autosizing
    # -------------------------------------------------------------------------
    elif isinstance(equipment, PlantSystem):
        total_cooling_load = 0.0
        total_heating_load = 0.0
        
        # Collect served rooms across all served AirLoops and direct terminals
        served_rooms: set[Room] = set()
        for loop in equipment.served_air_loops:
            for term in loop.served_terminals:
                if term.room:
                    served_rooms.add(term.room)
        for term in equipment.served_terminals:
            if term.room:
                served_rooms.add(term.room)
                
        for room in served_rooms:
            safe_room = ensure_safe_name(room.name).upper()
            for z_name, vals in sizing_data["zones"].items():
                if z_name.upper() == safe_room:
                    total_cooling_load += vals["cooling_load_w"]
                    total_heating_load += vals["heating_load_w"]
                    break
                    
        # Apply standard ASHRAE sizing factor (1.15 = 15% safety factor)
        safety_factor = 1.15
        rho_cp_delta_t_water = 1000.0 * 4180.0 * 5.5
        
        if equipment.plant_type == "Chiller":
            capacity = max(total_cooling_load * safety_factor, 3000.0)
            pump_flow = capacity / rho_cp_delta_t_water
        elif equipment.plant_type == "Boiler":
            capacity = max(total_heating_load * safety_factor, 2000.0)
            pump_flow = capacity / rho_cp_delta_t_water
        elif equipment.plant_type == "HeatPump":
            capacity = max(max(total_cooling_load, total_heating_load) * safety_factor, 3500.0)
            pump_flow = capacity / rho_cp_delta_t_water
        else: # CoolingTower
            capacity = max(total_cooling_load * 1.25 * safety_factor, 4000.0)
            pump_flow = capacity / rho_cp_delta_t_water
            
        mutations.append(Mutation(
            node=equipment,
            variable_name="capacity",
            new_value=round(capacity, 1),
            operation="Set"
        ))
        mutations.append(Mutation(
            node=equipment,
            variable_name="pump_flow_rate",
            new_value=round(pump_flow, 5),
            operation="Set"
        ))
        
    return mutations
