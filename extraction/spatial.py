from typing import Any

import ifcopenshell
from ifcopenshell.entity_instance import entity_instance
from building_modelling import BIM_Node
from building_modelling.topology import *
from extraction.properties import *
from extraction.geometry import *

def extract_spatial_hierarchy(
    ifc_file: ifcopenshell.file,
    geom_settings: Any,
    guid_map: dict[str, BIM_Node],
) -> Model | None:
    ifc_projects: list[entity_instance] = ifc_file.by_type("IfcProject")
    if not ifc_projects:
        return None
        
    ifc_project = ifc_projects[0]
    model = Model(guid=ifc_project.GlobalId, name=ifc_project.Name or "Project")
    guid_map[model.guid] = model
    
    ifc_buildings: list[entity_instance] = ifc_file.by_type("IfcBuilding")
    if ifc_buildings:
        guid_map[ifc_buildings[0].GlobalId] = model

    ifc_sites: list[entity_instance] = ifc_file.by_type("IfcSite")
    if ifc_sites:
        ifc_site = ifc_sites[0]
        lat = float(ifc_site.RefLatitude[0]) if ifc_site.RefLatitude else None
        lon = float(ifc_site.RefLongitude[0]) if ifc_site.RefLongitude else None
        
        site = Site(
            guid=ifc_site.GlobalId,
            name=ifc_site.Name or "Site",
            latitude=lat,
            longitude=lon,
            elevation=ifc_site.RefElevation
        )
        model.site = site
        guid_map[site.guid] = site

    ifc_storeys: list[entity_instance] = ifc_file.by_type("IfcBuildingStorey")
    for ifc_storey in ifc_storeys:
        floor = Floor(guid=ifc_storey.GlobalId, name=ifc_storey.Name or "Floor")
        guid_map[floor.guid] = floor

    ifc_spaces: list[entity_instance] = ifc_file.by_type("IfcSpace")
    for ifc_space in ifc_spaces:
        room = Room(guid=ifc_space.GlobalId, name=ifc_space.Name or "Room")
        
        psets = get_psets(ifc_space)
        text_volume = get_volume(psets)
        lighting, sensible = get_space_loads(psets)
        
        room.lighting_load = lighting
        room.occupant_sensible_heat = sensible
        
        verts = get_vertices(ifc_space, geom_settings)
        room.vertices = verts
        
        if not text_volume and verts:
            fallback_area = calculate_fallback_area(verts)
            room.volume = calculate_fallback_volume(verts, fallback_area)
        else:
            room.volume = text_volume
            
        guid_map[room.guid] = room

    return model