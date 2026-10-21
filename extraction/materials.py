import ifcopenshell
from ifcopenshell.entity_instance import entity_instance
import ifcopenshell.util.element
from building_modelling.topology import MaterialLayer

def extract_material_properties(ifc_material: entity_instance) -> dict[str, float | None]:
    """
    Digs into an IfcMaterial to find attached thermal properties.
    Returns a dictionary of properties if found.
    """
    props: dict[str, float | None] = {
        "conductivity": None,
        "density": None,
        "specific_heat": None
    }
    
    # In IFC, materials have property sets just like walls do!
    # They are usually stored in IfcExtendedMaterialProperties or IfcThermalMaterialProperties
    if hasattr(ifc_material, "HasProperties") and ifc_material.HasProperties:
        for mat_prop_set in ifc_material.HasProperties:
            if mat_prop_set.is_a("IfcMaterialProperties"):
                for prop in getattr(mat_prop_set, "Properties", []):
                    prop_name = prop.Name.lower() if hasattr(prop, "Name") else ""
                    
                    if "conductivity" in prop_name or prop_name == "thermalconductivity":
                        props["conductivity"] = float(prop.NominalValue.wrappedValue)
                    elif "density" in prop_name or prop_name == "massdensity":
                        props["density"] = float(prop.NominalValue.wrappedValue)
                    elif "specific" in prop_name and "heat" in prop_name:
                        props["specific_heat"] = float(prop.NominalValue.wrappedValue)
    
    return props

def get_material_layers(ifc_element: entity_instance) -> list[MaterialLayer]:
    """
    Extracts ordered MaterialLayerSets from a Wall, Roof, or Slab.
    """
    layers: list[MaterialLayer] = []
    
    # Safely get the material mapping using IfcOpenShell's utility
    try:
        material_info = ifcopenshell.util.element.get_material(ifc_element)
    except Exception:
        return layers
        
    if not material_info:
        return layers
        
    material_layers_ifc: list[entity_instance] = []
    
    # Handle the two different ways architects export layered materials
    if material_info.is_a("IfcMaterialLayerSetUsage"):
        material_layers_ifc = material_info.ForLayerSet.MaterialLayers
    elif material_info.is_a("IfcMaterialLayerSet"):
        material_layers_ifc = material_info.MaterialLayers
        
    # Iterate through from Outside to Inside (standard IFC ordering)
    for layer_ifc in material_layers_ifc:
        ifc_mat = layer_ifc.Material
        
        # 1. Base properties
        mat_name = ifc_mat.Name if ifc_mat else "Unknown Material"
        thickness = layer_ifc.LayerThickness if hasattr(layer_ifc, "LayerThickness") else 0.0
        
        # 2. Hunt for thermal properties (LOD 400 models)
        thermal_props = extract_material_properties(ifc_mat) if ifc_mat else {}
        
        # 3. Instantiate our clean Python Class
        mat_layer = MaterialLayer(
            guid=ifc_mat.GlobalId if (ifc_mat and hasattr(ifc_mat, "GlobalId")) else "no_guid",
            name=mat_name,
            thickness=thickness,
            conductivity=thermal_props.get("conductivity"),
            density=thermal_props.get("density"),
            specific_heat=thermal_props.get("specific_heat")
        )
        layers.append(mat_layer)
        
    return layers