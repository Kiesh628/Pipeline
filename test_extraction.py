from extraction.main_extractor import extract_ifc
from building_modelling.topology import Wall, Window, Roof, Slab

def run_test():
    file_name = "Ifc4_SampleHouse.ifc"
    print(f"--- Starting Extraction Test on {file_name} ---")
    
    # Run the orchestrator
    my_model, obj_map = extract_ifc(file_name)
    
    if not my_model:
        print("Extraction failed.")
        return

    # 1. Site Data
    print("\n" + "="*40)
    print(" 🌍 SITE & LOCATION DATA")
    print("="*40)
    if my_model.site:
        print(f"Latitude:  {my_model.site.latitude}")
        print(f"Longitude: {my_model.site.longitude}")
        print(f"Elevation: {my_model.site.elevation}")
    else:
        print("No Site data found.")

    # 2. Rooms and Internal Loads
    print("\n" + "="*40)
    print(" 🏠 ROOMS & INTERNAL LOADS")
    print("="*40)
    for floor in my_model.floors:
        print(f"\n[Floor] {floor.name}")
        for room in floor.rooms:
            print(f"  -> [Room] {room.name}")
            print(f"     - Volume:    {room.volume} m3")
            print(f"     - Lighting:  {room.lighting_load} W")
            print(f"     - Occupants: {room.occupant_sensible_heat} W/person")

    # 3. Surfaces, Geometry, and Thermodynamics
    print("\n" + "="*40)
    print(" 🧱 SURFACES (Area, U-Values, Materials)")
    print("="*40)
    
    walls = [obj for obj in obj_map.values() if isinstance(obj, Wall)]
    windows = [obj for obj in obj_map.values() if isinstance(obj, Window)]
    roofs = [obj for obj in obj_map.values() if isinstance(obj, Roof)]
    slabs = [obj for obj in obj_map.values() if isinstance(obj, Slab)]
    
    print(f"Found {len(walls)} Walls, {len(windows)} Windows, {len(roofs)} Roofs, {len(slabs)} Slabs.\n")

    for wall in walls:
        ext_str = "(External)" if wall.isExternal else "(Internal)"
        print(f"[Wall] {wall.name} {ext_str}")
        print(f"  - Area:    {wall.area} m2")
        print(f"  - U-Value: {wall.u_value}")
        if wall.layers:
            print(f"  - Materials ({len(wall.layers)} layers):")
            for layer in wall.layers:
                # We show thickness and check if the material hunt found conductivity
                cond_str = f"| Cond: {layer.conductivity}" if layer.conductivity else ""
                print(f"      * {layer.material_name} (Thick: {layer.thickness} {cond_str})")
        else:
            print("  - Materials: None")
        print()

    # 4. Windows (Checking for SHGC)
    if windows:
        print("\n" + "="*40)
        print(" 🪟 WINDOWS (U-Values & SHGC)")
        print("="*40)
        for win in windows:
            print(f"[Window] {win.name}")
            print(f"  - Area:    {win.area} m2")
            print(f"  - U-Value: {win.u_value}")
            print(f"  - SHGC:    {win.shgc}")
            print()

if __name__ == "__main__":
    run_test()