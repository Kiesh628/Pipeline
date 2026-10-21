from building_modelling import BIM_Node
from extraction.geometry import get_geom_settings
from extraction.spatial import extract_spatial_hierarchy
from extraction.surfaces import extract_surfaces
from extraction.relationships import resolve_spatial_relationships
from building_modelling.topology import Model, Wall

import ifcopenshell

def extract_ifc(file_path: str) -> tuple[Model | None, dict[str, BIM_Node]]:
    print(f"Loading {file_path}...")
    ifc_file = ifcopenshell.open(file_path)
    guid_map: dict[str, BIM_Node] = {}
    
    geom_settings = get_geom_settings()
    
    # Pass 1: Extraction
    model = extract_spatial_hierarchy(ifc_file, geom_settings, guid_map)
    if not model:
        print("Failed to find IfcProject in the file.")
        return None, guid_map
        
    extract_surfaces(ifc_file, geom_settings, guid_map)
    
    # Pass 2: Resolution
    resolve_spatial_relationships(ifc_file, guid_map)
    
    return model, guid_map


if __name__ == "__main__":
    # Test the clean, modular pipeline
    my_model, obj_map = extract_ifc("Ifc4_SampleHouse.ifc")
    
    if my_model:
        site_lat = my_model.site.latitude if my_model.site else "None"
        site_lon = my_model.site.longitude if my_model.site else "None"
        print(f"\nModel Site: Lat {site_lat}, Lon {site_lon}")
        
        print("\n--- Topology ---")
        for floor in my_model.floors:
            print(f"Floor: {floor.name}")
            for room in floor.rooms:
                print(f"  Room: {room.name} (Volume: {room.volume})")
                
        print("\n--- Surfaces ---")
        walls = [obj for obj in obj_map.values() if isinstance(obj, Wall)]
        for wall in walls:
            print(f"Wall: {wall.name} | Area: {wall.area} m2 | Layers: {len(wall.layers)}")