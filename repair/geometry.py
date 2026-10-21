
from building_modelling.topology import *

def room_volume(room: Room) -> float:
    if room.height and room.vertices:
        return abs(0.5*room.height*sum(room.vertices[i-1][0]*room.vertices[i][1]-room.vertices[i][0]*room.vertices[i-1][1] for i in range(len(room.vertices))))
    raise ValueError('Invalid room node')

def bounding_box(vertices:list[tuple[float, float, float]]) -> list[tuple[float,float,float]]:
    return [(min([point[0] for point in vertices]),min([point[1] for point in vertices]),min([point[2] for point in vertices])),
            (max([point[0] for point in vertices]),max([point[1] for point in vertices]),max([point[2] for point in vertices]))]

def isIntersecting(box_1: list[tuple[float,float,float]],
                   box_2: list[tuple[float,float,float]],
                   tolerance: float) -> bool:
    return (box_1[0][0] <= box_2[1][0] + tolerance and box_2[0][0] <= box_1[1][0] + tolerance and # X-axis
            box_1[0][1] <= box_2[1][1] + tolerance and box_2[0][1] <= box_1[1][1] + tolerance and # Y-axis
            box_1[0][2] <= box_2[1][2] + tolerance and box_2[0][2] <= box_1[1][2] + tolerance)    # Z-axis

def centriod(vertices:list[tuple[float, float, float]]) -> tuple[float,float,float]:
    if len(vertices) > 0:
        return(sum(vertex[0] for vertex in vertices)/len(vertices),sum(vertex[1] for vertex in vertices)/len(vertices),sum(vertex[2] for vertex in vertices)/len(vertices))
    return (0.0,0.0,0.0)
def distance_to_plane(point: tuple[float,float,float], plane_vertices: list[tuple[float,float,float]]) -> float:
    """Calculates the perpendicular distance from a 3D point to a plane defined by vertices."""
    import numpy as np
    
    if len(plane_vertices) < 3:
        return float('inf')
        
    p = np.array(point)
    p1 = np.array(plane_vertices[0])
    p2 = np.array(plane_vertices[1])
    p3 = np.array(plane_vertices[2])
    
    # Create two vectors on the plane
    v1 = p2 - p1
    v2 = p3 - p1
    
    # Find normal vector
    normal = np.cross(v1, v2)
    mag = np.linalg.norm(normal)
    
    if mag == 0: # Collinear points
        return float('inf')
        
    # Distance is the dot product of (point - p1) and the unit normal vector
    return float(np.abs(np.dot(p - p1, normal / mag)))
