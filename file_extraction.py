import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.unit
import ifcopenshell.geom
from shapely.geometry import Polygon
from shapely.ops import unary_union

from building_modelling.topology import (
    Model, Site, Floor, Room, Wall, Roof, Slab, Window, MaterialLayer
)

def dms_to_decimal(dms_tuple) -> float | None:
    """Converts IFC DMS (Degrees, Minutes, Seconds, Microseconds) to decimal degrees."""
    if not dms_tuple or len(dms_tuple) < 3:
        return None
    deg = float(dms_tuple[0])
    minute = float(dms_tuple[1])
    sec = float(dms_tuple[2])
    micro = float(dms_tuple[3]) / 1_000_000.0 if len(dms_tuple) > 3 else 0.0
    
    sign = -1.0 if (deg < 0 or minute < 0 or sec < 0) else 1.0
    val = abs(deg) + (abs(minute) / 60.0) + ((abs(sec) + micro) / 3600.0)
    return round(sign * val, 5)

def get_vertices_and_area(ifc_element, geom_settings) -> tuple[list[tuple[float, float, float]]|None, float|None]:
    """Helper to extract 3D vertices and approximate area from IFC geometry."""
    try:
        shape = ifcopenshell.geom.create_shape(geom_settings, ifc_element)
        verts = shape.geometry.verts
        # Group flat list [x,y,z,x,y,z] into list of tuples [(x,y,z), (x,y,z)]
        grouped_verts = [(verts[i], verts[i+1], verts[i+2]) for i in range(0, len(verts), 3)]
        
        # Very rough area approximation using bounding box for now
        xs, ys, zs = verts[0::3], verts[1::3], verts[2::3]
        dx, dy, dz = max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)
        
        # If it's a vertical wall, area is length * height. If flat roof, length * width.
        area = max(dx*dy, dy*dz, dx*dz) 
        return grouped_verts, round(area, 2)
    except Exception:
        return None, None
        
def extract_room_geometry(ifc_space, geom_settings) -> tuple[list[tuple[float, float]]|None, float|None, float|None]:
    """Extracts 2D ordered perimeter footprint, height, and area for an IFC space."""
    try:
        shape = ifcopenshell.geom.create_shape(geom_settings, ifc_space)
        verts = shape.geometry.verts
        faces = shape.geometry.faces
        
        if not verts or not faces:
            return None, None, None
            
        zs = verts[2::3]
        min_z = min(zs)
        max_z = max(zs)
        height = round(max_z - min_z, 2)
        
        # Extract bottom triangles
        bottom_polys = []
        for i in range(0, len(faces), 3):
            i1, i2, i3 = faces[i], faces[i+1], faces[i+2]
            p1 = (verts[3*i1], verts[3*i1+1], verts[3*i1+2])
            p2 = (verts[3*i2], verts[3*i2+1], verts[3*i2+2])
            p3 = (verts[3*i3], verts[3*i3+1], verts[3*i3+2])
            if abs(p1[2] - min_z) < 0.05 and abs(p2[2] - min_z) < 0.05 and abs(p3[2] - min_z) < 0.05:
                bottom_polys.append(Polygon([(p1[0], p1[1]), (p2[0], p2[1]), (p3[0], p3[1])]))
                
        if not bottom_polys:
            return None, height, None
            
        merged = unary_union(bottom_polys)
        footprint_2d = [(round(p[0], 3), round(p[1], 3)) for p in list(merged.exterior.coords)[:-1]]
        area = round(merged.area, 2)
        
        return footprint_2d, height, area
    except Exception:
        return None, None, None


def extract_materials(ifc_element) -> list[MaterialLayer]:
    """Helper to extract IFC Material Layer Sets into our Python classes."""
    layers = []
    material_info = ifcopenshell.util.element.get_material(ifc_element)
    
    if not material_info:
        return layers
        
    material_layers = []
    
    # Catch both standard ways IFC stores layered materials
    if material_info.is_a("IfcMaterialLayerSetUsage"):
        material_layers = material_info.ForLayerSet.MaterialLayers
    elif material_info.is_a("IfcMaterialLayerSet"):
        material_layers = material_info.MaterialLayers
        
    for layer in material_layers:
        mat_name = layer.Material.Name if layer.Material else "Unknown"
        mat_layer = MaterialLayer(
            guid="mat_layer", # IFC materials often lack GUIDs
            name=mat_name,
            material_name=mat_name,
            thickness=layer.LayerThickness
        )
        layers.append(mat_layer)
        
    return layers


def extract_building_graph(ifc_file_path: str) -> tuple[Model, dict]:
    print(f"Loading {ifc_file_path}...")
    ifc_file = ifcopenshell.open(ifc_file_path)
    guid_to_obj = {}
    
    # Calculate global unit scale (e.g. 0.001 for mm -> m)
    unit_scale = ifcopenshell.util.unit.calculate_unit_scale(ifc_file) or 1.0
    
    # Initialize Geometry Engine (Using native C++ engine)
    geom_settings = ifcopenshell.geom.settings()
    
    # ==========================================
    # PASS 1: INSTANTIATION & DATA EXTRACTION
    # ==========================================
    
    # 1. Project, Building, & Site
    ifc_project = ifc_file.by_type("IfcProject")[0]
    my_model = Model(guid=ifc_project.GlobalId, name=ifc_project.Name or "Project")
    guid_to_obj[my_model.guid] = my_model
    
    ifc_buildings = ifc_file.by_type("IfcBuilding")
    if ifc_buildings: 
        guid_to_obj[ifc_buildings[0].GlobalId] = my_model
    
    ifc_sites = ifc_file.by_type("IfcSite")
    if ifc_sites:
        ifc_site = ifc_sites[0]
        site_elev = (float(ifc_site.RefElevation) * unit_scale) if ifc_site.RefElevation is not None else None
        my_site = Site(
            guid=ifc_site.GlobalId, 
            name=ifc_site.Name or "Site",
            latitude=dms_to_decimal(ifc_site.RefLatitude),
            longitude=dms_to_decimal(ifc_site.RefLongitude),
            elevation=site_elev
        )
        my_model.site = my_site
        guid_to_obj[my_site.guid] = my_site

    # 2. Floors
    for ifc_storey in ifc_file.by_type("IfcBuildingStorey"):
        storey_elev = (float(ifc_storey.Elevation) * unit_scale) if ifc_storey.Elevation is not None else 0.0
        floor = Floor(guid=ifc_storey.GlobalId, name=ifc_storey.Name or "Floor", elevation=storey_elev)
        guid_to_obj[floor.guid] = floor

    # 3. Rooms
    for ifc_space in ifc_file.by_type("IfcSpace"):
        room = Room(guid=ifc_space.GlobalId, name=ifc_space.Name or "Room")
        
        # 2D Geometry & Height Extraction
        footprint, height, area = extract_room_geometry(ifc_space, geom_settings)
        room.vertices = footprint
        room.height = height
        
        # Pset Extraction
        psets = ifcopenshell.util.element.get_psets(ifc_space)
        if "Energy Analysis" in psets:
            room.lighting_load = psets["Energy Analysis"].get("Specified Lighting Load")
            room.occupant_sensible_heat = psets["Energy Analysis"].get("Sensible Heat Gain per person")
            room.occupant_latent_heat = psets["Energy Analysis"].get("Latent Heat Gain per person")
            
        # Safely Calculate Volume
        qto = psets.get("Qto_SpaceBaseQuantities", {})
        base = psets.get("BaseQuantities", {})
        text_volume = qto.get("NetVolume") or base.get("NetVolume") or qto.get("GrossVolume") or base.get("GrossVolume")
        
        math_volume = None
        if area and height and not text_volume:
            math_volume = round(area * height, 2)
            
        room.volume = text_volume or math_volume
        guid_to_obj[room.guid] = room

    # 4. Main Surfaces (Walls, Roofs, Slabs)
    surface_mapping = {
        "IfcWall": Wall,
        "IfcRoof": Roof,
        "IfcSlab": Slab
    }
    
    for ifc_type, python_class in surface_mapping.items():
        for ifc_element in ifc_file.by_type(ifc_type):
            
            surface_obj = python_class(guid=ifc_element.GlobalId, name=ifc_element.Name or ifc_type)
            
            # Materials
            surface_obj.layers = extract_materials(ifc_element)
            for layer in surface_obj.layers:
                layer.belongs_to = surface_obj
            
            # Geometry
            verts, area = get_vertices_and_area(ifc_element, geom_settings)
            surface_obj.vertices = verts
            surface_obj.area = area
            
            # Psets (U-Values & Boundary Conditions)
            psets = ifcopenshell.util.element.get_psets(ifc_element)
            for pset_name, pset_data in psets.items():
                if "ThermalTransmittance" in pset_data:
                    surface_obj.u_value = pset_data["ThermalTransmittance"]
                    break
                    
            if "Pset_WallCommon" in psets and "IsExternal" in psets["Pset_WallCommon"]:
                surface_obj.isExternal = psets["Pset_WallCommon"]["IsExternal"]
                
            guid_to_obj[surface_obj.guid] = surface_obj

    # 5. Windows
    for ifc_window in ifc_file.by_type("IfcWindow"):
        window = Window(guid=ifc_window.GlobalId, name=ifc_window.Name or "Window")
        
        verts, area = get_vertices_and_area(ifc_window, geom_settings)
        window.vertices = verts
        window.area = area
        
        psets = ifcopenshell.util.element.get_psets(ifc_window)
        for pset_name, pset_data in psets.items():
            if "ThermalTransmittance" in pset_data:
                window.u_value = pset_data["ThermalTransmittance"]
            if "SolarHeatGainCoefficient" in pset_data:
                window.shgc = pset_data["SolarHeatGainCoefficient"]
                
        guid_to_obj[window.guid] = window


    # ==========================================
    # PASS 2: NATIVE TOPOLOGY (The "Explicit Glue")
    # ==========================================
    # We only connect what is explicitly written in the IFC file.
    
    # Hierarchical linking (Building -> Floor -> Room)
    for rel in ifc_file.by_type("IfcRelAggregates"):
        parent_obj = guid_to_obj.get(rel.RelatingObject.GlobalId)
        if not parent_obj: continue
        
        for child_ifc in rel.RelatedObjects:
            child_obj = guid_to_obj.get(child_ifc.GlobalId)
            if not child_obj: continue
            
            if isinstance(parent_obj, Model) and isinstance(child_obj, Floor):
                parent_obj.floors.append(child_obj)
                child_obj.building = parent_obj
            elif isinstance(parent_obj, Floor) and isinstance(child_obj, Room):
                parent_obj.rooms.append(child_obj)
                child_obj.floor = parent_obj

    return my_model, guid_to_obj


# ==========================================
# TEST BLOCK
# ==========================================
if __name__ == "__main__":
    # Run the extraction (Replace with your actual path if needed)
    my_model, guid_to_obj = extract_building_graph("Ifc4_SampleHouse.ifc")
    
    print(f"\nModel Site: Lat {my_model.site.latitude}, Lon {my_model.site.longitude}" if my_model.site else "No Site Info")
    
    print("\n--- Testing Topology & Extracted Data ---")
    for floor in my_model.floors:
        print(f"\nFloor: {floor.name}")
        for room in floor.rooms:
            print(f"  Room: {room.name} (Volume: {room.volume})")
            
    print("\n--- Testing Surface Geometries & Materials ---")
    all_walls = [obj for obj in guid_to_obj.values() if isinstance(obj, Wall)]
    
    for wall in all_walls:
        print(f"\nWall: {wall.name} | Area: {wall.area} m2 | Layers: {len(wall.layers)}")
        if wall.layers:
            for layer in wall.layers:
                print(f"    - Layer: {layer.material_name} ({layer.thickness}m)")