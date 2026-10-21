import os
import re
from pathlib import Path
from typing import Any

import honeybee_energy # Required to dynamically register .to_idf() on Honeybee Model
from honeybee.model import Model as HBModel, Room as HBRoom, Face as HBFace, Aperture as HBAperture
from honeybee.facetype import Floor as HBFloor, RoofCeiling as HBRoofCeiling, Wall as HBWall
from honeybee.boundarycondition import Outdoors as HBOutdoors, Ground as HBGround
from ladybug_geometry.geometry3d import Point3D, Face3D
from ladybug.epw import EPW

from building_modelling.topology import Model, Room, Wall, Window, Floor, Roof, Slab
from building_modelling.hvac import ZoneTerminal, Thermostat
from consts import BUILDING_FILE_FOLDER

def _pt3d(x: float, y: float, z: float) -> Point3D:
    return Point3D(x, y, z) # type: ignore

def ensure_safe_name(name: str | None, default: str = "Object") -> str:
    """Cleans a name to make it a safe identifier for EnergyPlus."""
    if not name:
        return default
    # Replace invalid EnergyPlus characters with underscores
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return safe

def room_to_honeybee(room: Room, default_floor_z: float = 0.0) -> HBRoom | None:
    """
    Reconstructs a 3D Honeybee Room from a topological Room's 2D vertices, 
    elevation, and height.
    """
    if not room.vertices or len(room.vertices) < 3:
        return None
        
    floor_z = room.floor.elevation if room.floor and room.floor.elevation is not None else default_floor_z
    height = room.height if room.height and room.height > 0 else 3.0
    ceiling_z = floor_z + height
    
    verts_2d = room.vertices
    n = len(verts_2d)
    
    # 1. Floor Face (Downwards normal)
    # Reversing order of polygon vertices gives a downward-facing normal in right-hand rule
    floor_pts = [_pt3d(v[0], v[1], floor_z) for v in reversed(verts_2d)]
    floor_face = HBFace(
        identifier=f"{ensure_safe_name(room.name)}_Floor",
        geometry=Face3D(floor_pts),
        type=HBFloor(),
        boundary_condition=HBGround() if abs(floor_z) < 0.1 else HBOutdoors()
    )
    
    # 2. Roof / Ceiling Face (Upwards normal)
    ceiling_pts = [_pt3d(v[0], v[1], ceiling_z) for v in verts_2d]
    ceiling_face = HBFace(
        identifier=f"{ensure_safe_name(room.name)}_Ceiling",
        geometry=Face3D(ceiling_pts),
        type=HBRoofCeiling(),
        boundary_condition=HBOutdoors()
    )
    
    # 3. Perimeter Wall Faces
    faces = [floor_face, ceiling_face]
    for i in range(n):
        p1 = verts_2d[i]
        p2 = verts_2d[(i + 1) % n]
        
        wall_pts = [
            _pt3d(p1[0], p1[1], floor_z),
            _pt3d(p2[0], p2[1], floor_z),
            _pt3d(p2[0], p2[1], ceiling_z),
            _pt3d(p1[0], p1[1], ceiling_z)
        ]
        
        wall_face = HBFace(
            identifier=f"{ensure_safe_name(room.name)}_Wall_{i+1}",
            geometry=Face3D(wall_pts),
            type=HBWall(),
            boundary_condition=HBOutdoors()
        )
        
        # Check if any window belongs to this room/wall and matches coplanarity
        if room.walls:
            for w in room.walls:
                if w.windows:
                    for win in w.windows:
                        if win.vertices and len(win.vertices) >= 3:
                            try:
                                win_pts = [_pt3d(v[0], v[1], v[2]) for v in win.vertices]
                                ap = HBAperture(
                                    identifier=ensure_safe_name(win.name, f"Window_{i}"),
                                    geometry=Face3D(win_pts)
                                )
                                wall_face.add_aperture(ap)
                            except Exception:
                                pass # Window not coplanar with this segment
                                
        faces.append(wall_face)
        
    hb_room = HBRoom(
        identifier=ensure_safe_name(room.name, f"Room_{id(room)}"),
        faces=faces,
        tolerance=0.01 # type: ignore
    )
    return hb_room

def export_to_honeybee(model: Model) -> HBModel:
    """
    Converts our topological Model into a complete Honeybee Model,
    reconstructing 3D zone geometries and solving adjacencies between rooms.
    """
    hb_rooms: list[HBRoom] = []
    
    for floor in model.floors:
        floor_elev = floor.elevation if floor.elevation is not None else 0.0
        for room in floor.rooms:
            hb_r = room_to_honeybee(room, default_floor_z=floor_elev)
            if hb_r:
                hb_rooms.append(hb_r)
                
    model_name = ensure_safe_name(model.name, "BuildingModel")
    hb_model = HBModel(identifier=model_name, rooms=hb_rooms)
    
    # Solve adjacency between touching rooms (changes boundary condition to Surface)
    if len(hb_rooms) > 1:
        try:
            hb_model.solve_adjacency(tolerance=0.05)
        except Exception:
            pass
            
    return hb_model

def generate_sizing_idf(model: Model, output_idf_path: Path) -> Path:
    """
    Generates a complete, ready-to-simulate EnergyPlus IDF configured
    specifically for the Design-Day Sizing Pass.
    """
    output_idf_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 1. Convert to Honeybee Model
    hb_model = export_to_honeybee(model)
    hb_idf_body: str = getattr(hb_model, 'to_idf')() # type: ignore
    
    # 2. Get Weather & Design Days
    weather_file_str = model.site.weather_file if model.site and model.site.weather_file else None
    if not weather_file_str or not os.path.exists(weather_file_str):
        # Fallback to local default weather if available
        default_epw = Path(__file__).parent / "weather_data" / "chennai.epw"
        if default_epw.exists():
            weather_file_str = str(default_epw.absolute())
        else:
            raise FileNotFoundError(f"No valid weather file found for site: {weather_file_str}")
            
    epw = EPW(weather_file_str)
    loc_str = epw.location.to_idf()
    design_days = epw.best_available_design_days()
    ddy_str = "\n\n".join(d.to_idf() for d in design_days)
    
    # 3. EnergyPlus Sizing Control Header
    bldg_name = ensure_safe_name(model.name, "Building")
    header = f"""Version, 25.2;

Building,
  {bldg_name},
  0.0,
  Suburbs,
  0.04,
  0.4,
  FullExterior,
  25,
  6;

GlobalGeometryRules,
  UpperLeftCorner,
  CounterClockWise,
  Relative;

Timestep, 4;

SimulationControl,
  Yes,                    !- Do Zone Sizing Calculation
  No,                     !- Do System Sizing Calculation
  No,                     !- Do Plant Sizing Calculation
  Yes,                    !- Run Simulation for Sizing Periods
  No;                     !- Run Simulation for Weather File Run Periods

{loc_str}

{ddy_str}

ScheduleTypeLimits, Temperature, -60, 200, Continuous;
ScheduleTypeLimits, Control Type, 0, 4, Discrete;

Schedule:Constant, AlwaysOn_Control, Control Type, 4;
"""

    # 4. Generate Sizing:Zone and IdealLoadsAirSystem for each conditioned room
    zone_hvac_objects = []
    
    for floor in model.floors:
        for room in floor.rooms:
            # Only condition rooms that have equipment or a thermostat
            if not room.equipment and not room.thermostat:
                continue
                
            safe_room_name = ensure_safe_name(room.name)
            heat_temp = room.thermostat.heating_setpoint if room.thermostat and room.thermostat.heating_setpoint is not None else 21.0
            cool_temp = room.thermostat.cooling_setpoint if room.thermostat and room.thermostat.cooling_setpoint is not None else 24.0
            
            zone_hvac_objects.append(f"""
Schedule:Constant, {safe_room_name}_CoolSet, Temperature, {cool_temp:.1f};
Schedule:Constant, {safe_room_name}_HeatSet, Temperature, {heat_temp:.1f};

ThermostatSetpoint:DualSetpoint,
  {safe_room_name}_DualSetPoint,
  {safe_room_name}_HeatSet,
  {safe_room_name}_CoolSet;

ZoneControl:Thermostat,
  {safe_room_name}_ThermostatControl,
  {safe_room_name},
  AlwaysOn_Control,
  ThermostatSetpoint:DualSetpoint,
  {safe_room_name}_DualSetPoint;

Sizing:Zone,
  {safe_room_name},
  SupplyAirTemperature, 14.0, ,
  SupplyAirTemperature, 40.0, ,
  0.0085, 0.008, , , ,
  DesignDay, , , , ,
  DesignDay, , , , ;

ZoneHVAC:EquipmentConnections,
  {safe_room_name},
  {safe_room_name}_EquipmentList,
  {safe_room_name}_InletNode,
  {safe_room_name}_ExhaustNode,
  {safe_room_name}_AirNode,
  {safe_room_name}_ReturnNode;

ZoneHVAC:EquipmentList,
  {safe_room_name}_EquipmentList,
  SequentialLoad,
  ZoneHVAC:IdealLoadsAirSystem,
  {safe_room_name}_IdealAir,
  1, 1;

ZoneHVAC:IdealLoadsAirSystem,
  {safe_room_name}_IdealAir,
  ,
  {safe_room_name}_InletNode,
  {safe_room_name}_ExhaustNode,
  ,
  50, 13, 0.015, 0.009,
  NoLimit, , ,
  NoLimit, , ;
""")

    full_idf = header + "\n" + "\n".join(zone_hvac_objects) + "\n\n" + hb_idf_body
    
    with open(output_idf_path, "w", encoding="utf-8") as f:
        f.write(full_idf)
        
    return output_idf_path
