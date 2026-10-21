from typing import Any
import ifcopenshell
from ifcopenshell.entity_instance import entity_instance
from building_modelling import BIM_Node
from building_modelling.topology import *
from extraction.geometry import *
from extraction.materials import get_material_layers
from extraction.properties import *

def extract_surfaces(
    ifc_file: ifcopenshell.file,
    geom_settings: Any,
    guid_map: dict[str, BIM_Node],
) -> None:
    surface_mapping: dict[str, type[Wall] | type[Roof] | type[Slab]] = {
        "IfcWall": Wall,
        "IfcRoof": Roof,
        "IfcSlab": Slab
    }
    
    for ifc_type, python_class in surface_mapping.items():
        ifc_elements: list[entity_instance] = ifc_file.by_type(ifc_type)
        for ifc_element in ifc_elements:
            surface_obj = python_class(guid=ifc_element.GlobalId, name=ifc_element.Name or ifc_type)
            
            surface_obj.layers = get_material_layers(ifc_element)
            for layer in surface_obj.layers:
                layer.belongs_to = surface_obj
                
            verts = get_vertices(ifc_element, geom_settings)
            surface_obj.vertices = verts
            
            psets = get_psets(ifc_element)
            
            text_area = get_area(psets)
            surface_obj.area = (
                text_area
                if text_area is not None
                else calculate_fallback_area(verts) if verts is not None else None
            )
            
            surface_obj.u_value = get_u_value(psets)
            surface_obj.isExternal = is_external(psets)
            
            guid_map[surface_obj.guid] = surface_obj

    ifc_windows: list[entity_instance] = ifc_file.by_type("IfcWindow")
    for ifc_window in ifc_windows:
        window = Window(guid=ifc_window.GlobalId, name=ifc_window.Name or "Window")
        
        verts = get_vertices(ifc_window, geom_settings)
        window.vertices = verts
        
        psets = get_psets(ifc_window)
        
        text_area = get_area(psets)
        window.area = (
            text_area
            if text_area is not None
            else calculate_fallback_area(verts) if verts is not None else None
        )
        
        window.u_value = get_u_value(psets)
        window.shgc = get_shgc(psets)
        
        guid_map[window.guid] = window