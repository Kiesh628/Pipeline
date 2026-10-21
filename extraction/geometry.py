import math
from typing import Any

import ifcopenshell.geom
from ifcopenshell.entity_instance import entity_instance

def get_geom_settings() -> Any:
    settings = ifcopenshell.geom.settings()
    return settings

def get_vertices(ifc_element: entity_instance,
                 settings: Any) -> list[tuple[float, float, float]] | None:
    try:
        shape = ifcopenshell.geom.create_shape(settings, ifc_element)
        native_shape: Any = shape
        verts = native_shape.geometry.verts
        
        grouped_verts: list[tuple[float, float, float]] = []
        for i in range(0, len(verts), 3):
            grouped_verts.append((float(verts[i]), float(verts[i+1]), float(verts[i+2])))
            
        return grouped_verts
    except Exception:
        return None

def get_bounding_box(vertices: list[tuple[float, float, float]]) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:

    if not vertices:
        return None
        
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))

def calculate_fallback_area(vertices: list[tuple[float, float, float]]) -> float | None:
    if not vertices:
        return None
        
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    
    height = max(zs) - min(zs)
    
    max_length = 0.0
    for i in range(len(vertices)):
        for j in range(i + 1, len(vertices)):
            dist = math.hypot(xs[i] - xs[j], ys[i] - ys[j])
            if dist > max_length:
                max_length = dist
                
    if height > 0.1:
        return round(max_length * height, 2)
    else:
        width = max(xs) - min(xs)
        depth = max(ys) - min(ys)
        return round(width * depth, 2)

def calculate_fallback_volume(vertices: list[tuple[float, float, float]], fallback_area: float | None) -> float | None:
    if not vertices or not fallback_area:
        return None
        
    zs = [v[2] for v in vertices]
    height = max(zs) - min(zs)
    
    return round(fallback_area * height, 2)