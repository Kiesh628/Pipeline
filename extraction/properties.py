import ifcopenshell
from ifcopenshell.entity_instance import entity_instance
import ifcopenshell.util.element

def get_psets(ifc_element: entity_instance) -> dict:
    try:
        return ifcopenshell.util.element.get_psets(ifc_element) or {}
    except Exception:
        return {}

def get_volume(psets: dict) -> float | None:
    if "Qto_SpaceBaseQuantities" in psets:
        vol = psets["Qto_SpaceBaseQuantities"].get("NetVolume")
        if vol is not None: return float(vol)
        
    if "BaseQuantities" in psets:
        vol = psets["BaseQuantities"].get("NetVolume") or psets["BaseQuantities"].get("GrossVolume")
        if vol is not None: return float(vol)
        
    if "Pset_SpaceCommon" in psets:
        vol = psets["Pset_SpaceCommon"].get("Volume")
        if vol is not None: return float(vol)
        
    return None

def get_area(psets: dict) -> float | None:
    qto_names = [
        "Qto_WallBaseQuantities", 
        "Qto_RoofBaseQuantities", 
        "Qto_SlabBaseQuantities", 
        "Qto_WindowBaseQuantities",
        "BaseQuantities"
    ]
    
    for qto in qto_names:
        if qto in psets:
            area = (psets[qto].get("NetSideArea") or 
                    psets[qto].get("NetArea") or 
                    psets[qto].get("Area"))
            if area is not None:
                return float(area)
                
    return None

def get_u_value(psets: dict) -> float | None:
    for pset_name, pset_data in psets.items():
        if "ThermalTransmittance" in pset_data:
            val = pset_data["ThermalTransmittance"]
            if val is not None: return float(val)
    return None

def get_shgc(psets: dict) -> float | None:
    for pset_name, pset_data in psets.items():
        if "SolarHeatGainCoefficient" in pset_data:
            val = pset_data["SolarHeatGainCoefficient"]
            if val is not None: return float(val)
    return None

def is_external(psets: dict) -> bool | None:
    common_psets = ["Pset_WallCommon", "Pset_RoofCommon", "Pset_SlabCommon"]
    for pset in common_psets:
        if pset in psets and "IsExternal" in psets[pset]:
            return bool(psets[pset]["IsExternal"])
    return None

def get_space_loads(psets: dict) -> tuple[float | None, float | None]:
    lighting_load = None
    sensible_heat = None
    
    if "Energy Analysis" in psets:
        lighting_load = psets["Energy Analysis"].get("Specified Lighting Load")
        sensible_heat = psets["Energy Analysis"].get("Sensible Heat Gain per person")
        
    return (
        float(lighting_load) if lighting_load is not None else None,
        float(sensible_heat) if sensible_heat is not None else None
    )