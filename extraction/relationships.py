import ifcopenshell
from ifcopenshell.entity_instance import entity_instance
from building_modelling import BIM_Node
from building_modelling.topology import Model, Floor, Room

def resolve_spatial_relationships(
    ifc_file: ifcopenshell.file,
    guid_map: dict[str, BIM_Node],
) -> None:
    relationships: list[entity_instance] = ifc_file.by_type("IfcRelAggregates")
    for rel in relationships:
        parent_ifc = rel.RelatingObject
        if not parent_ifc:
            continue
            
        parent_obj = guid_map.get(parent_ifc.GlobalId)
        if not parent_obj:
            continue
            
        for child_ifc in rel.RelatedObjects:
            child_obj = guid_map.get(child_ifc.GlobalId)
            if not child_obj:
                continue
                
            if isinstance(parent_obj, Model) and isinstance(child_obj, Floor):
                parent_obj.floors.append(child_obj)
                child_obj.building = parent_obj
                
            elif isinstance(parent_obj, Floor) and isinstance(child_obj, Room):
                parent_obj.rooms.append(child_obj)
                child_obj.floor = parent_obj