import csv
from pathlib import Path
from typing import Any

# This import executes a background script that populates the honeybee_energy dictionaries.
import honeybee_energy_standards  # type: ignore # noqa: F401

from honeybee_energy.lib.materials import OPAQUE_MATERIALS, opaque_material_by_identifier
from honeybee_energy.lib.constructions import OPAQUE_CONSTRUCTIONS, opaque_construction_by_identifier
from honeybee_energy.lib.programtypes import PROGRAM_TYPES, program_type_by_identifier
from honeybee_energy.lib.schedules import SCHEDULES, schedule_by_identifier

def generate_material_lookup(output_dir: Path) -> None:
    csv_path: Path = output_dir / "materials.csv"
    
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer: Any = csv.writer(f)
        writer.writerow([
            "Material_Name", "Thickness_m", "Conductivity_W_mK", 
            "Density_kg_m3", "Specific_Heat_J_kgK", "Thermal_Resistance_m2K_W"
        ])
        
        for name in OPAQUE_MATERIALS:
            mat: Any = opaque_material_by_identifier(name)
            
            if hasattr(mat, 'conductivity') and hasattr(mat, 'density') and hasattr(mat, 'specific_heat'):
                writer.writerow([
                    name, 
                    round(mat.thickness, 4), 
                    round(mat.conductivity, 4),
                    round(mat.density, 2),
                    round(mat.specific_heat, 2),
                    ""
                ])
            elif hasattr(mat, 'r_value'):
                writer.writerow([
                    name, "", "", "", "", round(mat.r_value, 4)
                ])
    print(f"✅ Generated {csv_path.name} ({len(OPAQUE_MATERIALS)} materials)")
    pass

def generate_construction_lookup(output_dir: Path) -> None:
    csv_path: Path = output_dir / "constructions.csv"
    
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer: Any = csv.writer(f)
        writer.writerow([
            "Construction_Name", "U_Value_W_m2K", "R_Value_m2K_W", 
            "Layer_Count", "Outside_Material", "Inside_Material",
            "Area_Heat_Capacity_J_m2K", "Solar_Absorptance"
        ])
        
        for name in OPAQUE_CONSTRUCTIONS:
            con: Any = opaque_construction_by_identifier(name)
            
            # Check if it has physical material layers (skips AirBoundaryConstruction)
            if hasattr(con, 'materials'):
                layer_count: int = len(con.materials)
                outside_mat: str = con.materials[0].identifier if layer_count > 0 else ""
                inside_mat: str = con.materials[-1].identifier if layer_count > 0 else ""
                area_heat_cap = round(con.area_heat_capacity, 2) if (hasattr(con, 'area_heat_capacity') and con.area_heat_capacity is not None) else ""
                solar_abs = round(con.materials[0].solar_absorptance, 4) if (con.materials and hasattr(con.materials[0], 'solar_absorptance') and con.materials[0].solar_absorptance is not None) else ""
                
                writer.writerow([
                    name,
                    round(con.u_value, 4) if hasattr(con, 'u_value') else "",
                    round(con.r_value, 4) if hasattr(con, 'r_value') else "",
                    layer_count,
                    outside_mat,
                    inside_mat,
                    area_heat_cap,
                    solar_abs
                ])
            else:
                # Handle Air Boundaries or purely topological constructions
                writer.writerow([name, "", "", 0, "Air", "Air", "", ""])
                
    print(f"Generated {csv_path.name} ({len(OPAQUE_CONSTRUCTIONS)} constructions)")
    pass

def generate_room_loads_lookup(output_dir: Path) -> None:
    csv_path: Path = output_dir / "room_loads.csv"
    
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer: Any = csv.writer(f)
        writer.writerow([
            "Room_Type", "Lighting_W_m2", "Equipment_W_m2", 
            "People_Density_per_m2", "Sensible_Heat_W_person", "Latent_Heat_W_person",
            "Infiltration_m3_s_m2", "Ventilation_L_s_person", "Ventilation_L_s_m2"
        ])
        
        for name in PROGRAM_TYPES:
            prog: Any = program_type_by_identifier(name)
            
            lighting: float = round(prog.lighting.watts_per_area, 2) if prog.lighting else 0.0
            equipment: float = round(prog.electric_equipment.watts_per_area, 2) if prog.electric_equipment else 0.0
            people_density: float = round(prog.people.people_per_area, 4) if prog.people else 0.0
            
            sensible: float = 0.0
            latent: float = 0.0
            if prog.people:
                total_heat: float = 120.0 
                latent_obj: Any = getattr(prog.people, 'latent_fraction', None)
                latent_frac: float = float(latent_obj) if isinstance(latent_obj, (float, int)) else 0.45
                sensible = round(total_heat * (1.0 - latent_frac), 2)
                latent = round(total_heat * latent_frac, 2)
                
            infiltration: float = round(prog.infiltration.flow_per_exterior_area, 6) if prog.infiltration else 0.0
            vent_person: float = round(prog.ventilation.flow_per_person * 1000, 2) if prog.ventilation else 0.0 
            vent_area: float = round(prog.ventilation.flow_per_area * 1000, 2) if prog.ventilation else 0.0
            
            writer.writerow([
                name, lighting, equipment, people_density, 
                sensible, latent, infiltration, vent_person, vent_area
            ])
    print(f"✅ Generated {csv_path.name} ({len(PROGRAM_TYPES)} room types)")
    pass

def generate_schedules_lookup(output_dir: Path) -> None:
    csv_path: Path = output_dir / "schedules.csv"
    
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer: Any = csv.writer(f)
        writer.writerow(["Schedule_Name", "Schedule_Type"])
        
        for name in SCHEDULES:
            sch: Any = schedule_by_identifier(name)
            
            # Use .identifier instead of .name!
            sch_type: str = sch.schedule_type_limit.identifier if hasattr(sch, 'schedule_type_limit') and sch.schedule_type_limit else "Unknown"
            
            writer.writerow([name, sch_type])
            
    print(f"✅ Generated {csv_path.name} ({len(SCHEDULES)} schedules)")
    pass

if __name__ == "__main__":
    current_dir: Path = Path(__file__).parent
    lookup_dir: Path = current_dir / "lookup_tables"
    lookup_dir.mkdir(parents=True, exist_ok=True)
    
    print("Extracting ASHRAE standards from Honeybee-Energy...")
    generate_material_lookup(lookup_dir)
    generate_construction_lookup(lookup_dir)
    generate_room_loads_lookup(lookup_dir)
    generate_schedules_lookup(lookup_dir)
    print("Done! You now have a local database for the Repair Layer.")