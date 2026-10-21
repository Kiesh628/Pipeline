from __future__ import annotations
from typing import TYPE_CHECKING
from building_modelling import BIM_Node

if TYPE_CHECKING:
    from building_modelling.hvac import *

from diagnosis.issues import *

class Model(BIM_Node):
    indexing: list['Model'] = list()

    def __init__(self, guid: str|None, name: str|None):
        super().__init__(guid, name)
        Model.indexing.append(self)
        self.floors:list[Floor] = list()
        self.site: Site|None = None
        pass

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()

class Site(BIM_Node):
    indexing: list['Site'] = list()

    def __init__(self, guid: str|None, name: str|None,
                 latitude: float|None = None,
                 longitude: float|None = None,
                 elevation: float|None = None,
                 true_north: float|None = None,
                 weather_file: str|None = None):
        super().__init__(guid, name)
        Site.indexing.append(self)
        self.latitude: float|None = latitude
        self.longitude: float|None = longitude
        self.elevation: float|None = elevation
        self.true_north: float|None = true_north
        self.weather_file: str|None = weather_file
        pass

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
    def verify(self,
               IssueList: list[Issue]):
        
            if not self.guid:
                IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
            if not self.name:
                IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
            
            if self.latitude is None:
                IssueList.append(MissingValueIssue(self,'Missing latitude data from file.','latitude'))
            elif self.latitude < -90.0 or self.latitude > 90.0:
                    IssueList.append(ValueSanityIssue(self,f'Invalid latitude value of {self.latitude}','latitude',(-90.0,90.0)))
            
            if self.longitude is None:
                IssueList.append(MissingValueIssue(self,'Missing longitude data from file.','longitude'))
            elif self.longitude < -180.0 or self.longitude > 180.0:
                IssueList.append(ValueSanityIssue(self,f'Invalid longitude value of {self.longitude}','longitude',(-180.0,180.0)))

            if not self.weather_file:
                IssueList.append(MissingValueIssue(self, 'Missing weather file (.epw) for building site.', 'weather_file'))
        
            pass

class Floor(BIM_Node):
    indexing: list['Floor'] = list()

    def __init__(self, guid: str|None, name: str|None,
                 elevation: float|None = None,
                 building: Model|None = None):
        super().__init__(guid, name)
        Floor.indexing.append(self)
        self.elevation: float|None = elevation
        self.building: Model|None = building
        self.rooms: list[Room] = list()
        pass

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
    def verify(self,
               IssueList: list[Issue]):
            if not self.guid:
                IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
            if not self.name:
                IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
                
            if self.elevation is None:
                IssueList.append(MissingValueIssue(self, 'Missing elevation', 'elevation'))
                
            if not self.building:
                IssueList.append(MissingEdgeIssue(self, 'Floor must have a building pointer', 'building'))
                
            if len(self.rooms) < 1:
                IssueList.append(MissingEdgeIssue(self, 'Floor must have at least 1 room', 'rooms'))
        
            pass

class Room(BIM_Node):
    indexing: list['Room'] = list()
    
    def __init__(self, guid: str|None, name: str|None,
                 height: float|None = None,
                 type: str|None = None):
        super().__init__(guid, name)
        
        Room.indexing.append(self)
                
        self.height: float|None = height
        self.type: str|None = type
        self.vertices: list[tuple[float, float]]|None = None
        
        self.lighting_load: float|None = None          # Watts
        self.equipment_load: float|None = None         # Watts
        self.people_density: float|None = None         # people/m2
        self.process_load: float = 0.0                 # Watts
        self.ventilation_rate: float|None = None       # m3/s
        self.furniture_heat_capacity: float = 20_000.0 # J/(m2·K) of floor area
        self.occupant_sensible_heat: float|None = None # Watts/person
        self.occupant_latent_heat: float|None = None   # Watts/person
        self.infiltration_rate: float|None = None      # Air Changes per Hour (ACH)
        
        self.occupancy_schedule: str|None = None
        self.lighting_schedule: str|None = None
        self.equipment_schedule: str|None = None
        
        self.walls: list[Wall] = list()
        self.roofs: list[Roof] = list()
        self.slabs: list[Slab] = list()
        self.equipment: list[ZoneTerminal] = list()
        self.thermostat: Thermostat | None = None
        self.floor: Floor|None = None
        pass
    
    def verify(self, 
               IssueList: list[Issue]):
        
            if not self.guid:
                IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
            if not self.name:
                IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
            
            if not self.height:
                IssueList.append(MissingValueIssue(self, f'Missing height data from room {self.name}', 'height'))
            elif self.height <= 0:
                IssueList.append(ValueSanityIssue(self, f'Invalid height of room {self.name}', 'height', (0.001, float('inf'))))
            
            # Assuming self.type is optional
        
            if not self.vertices:
                IssueList.append(MissingValueIssue(self, f'Missing room vertex information for {self.name}', 'vertices'))
            
            if not self.lighting_load:
                IssueList.append(MissingValueIssue(self, f'Lighting load data missing from room {self.name}', 'lighting_load'))
            elif self.lighting_load < 0:
                IssueList.append(ValueSanityIssue(self, f'Invalid lighting load data of {self.lighting_load} for room {self.name}', 'lighting_load', (0.0, float('inf'))))
            
            # Ignoring equipment_load and equipment_schedule
            
            if self.people_density is None:
                IssueList.append(MissingValueIssue(self, f'People density missing from room {self.name}', 'people_density'))
            elif self.people_density < 0:
                IssueList.append(ValueSanityIssue(self, f'Invalid people density of {self.people_density} for room {self.name}', 'people_density', (0.0, float('inf'))))
                
            if self.process_load < 0:
                IssueList.append(ValueSanityIssue(self, f'Invalid process load of {self.process_load} for room {self.name}', 'process_load', (0.0, float('inf'))))
                
            if self.ventilation_rate is not None and self.ventilation_rate < 0:
                IssueList.append(ValueSanityIssue(self, f'Invalid ventilation rate of {self.ventilation_rate} for room {self.name}', 'ventilation_rate', (0.0, float('inf'))))
                
            if self.furniture_heat_capacity is None:
                IssueList.append(MissingValueIssue(self, f'Furniture heat capacity missing from room {self.name}', 'furniture_heat_capacity'))
            elif self.furniture_heat_capacity <= 0:
                IssueList.append(ValueSanityIssue(self, f'Furniture heat capacity of {self.furniture_heat_capacity} for room {self.name} must be > 0 J/(m2·K)', 'furniture_heat_capacity', (0.001, float('inf'))))
            
            if not self.occupant_sensible_heat:
                IssueList.append(MissingValueIssue(self, f'Occupant sensible heat data missing from room {self.name}', 'occupant_sensible_heat'))
            elif self.occupant_sensible_heat <= 0:
                IssueList.append(ValueSanityIssue(self, f'Invalid occupant sensible heat data of {self.occupant_sensible_heat} for room {self.name}', 'occupant_sensible_heat', (0.001, float('inf'))))
            
            if not self.occupant_latent_heat:
                IssueList.append(MissingValueIssue(self, f'Occupant latent heat data missing from room {self.name}', 'occupant_latent_heat'))
            elif self.occupant_latent_heat <= 0:
                IssueList.append(ValueSanityIssue(self, f'Invalid occupant latent heat data of {self.occupant_latent_heat} for room {self.name}', 'occupant_latent_heat', (0.001, float('inf'))))
            
            if not self.infiltration_rate:
                IssueList.append(MissingValueIssue(self, f'Inflitration rate data missing from room {self.name}', 'infiltration_rate'))
            elif self.infiltration_rate < 0:
                IssueList.append(ValueSanityIssue(self, f'Invalid infiltration rate data of {self.infiltration_rate} for room {self.name}', 'infiltration_rate', (0.0, float('inf'))))
            
            if not self.occupancy_schedule:
                IssueList.append(MissingValueIssue(self, f'Occupancy schedule data missing from room {self.name}', 'occupancy_schedule'))
                
            if not self.lighting_schedule:
                IssueList.append(MissingValueIssue(self, f'Lighting schedule data missing from room {self.name}', 'lighting_schedule'))
        
            # Equipment & Thermostat verification
            if self.equipment and not self.thermostat:
                IssueList.append(MissingEdgeIssue(self, f"Room {self.name} has HVAC equipment, but no thermostat assigned to control it.", "thermostat"))
            
            has_top = bool(self.roofs or self.slabs)
            has_bottom = bool(self.slabs)
            
            if not has_top:
                IssueList.append(MissingEdgeIssue(self, f'Room {self.name} must be connected to at least one roof or slab (top cover).', 'roofs'))
                
            if not has_bottom:
                IssueList.append(MissingEdgeIssue(self, f'Room {self.name} must be connected to a floor or slab (bottom cover).', 'floor'))
        
            pass
    
    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()

class Wall(BIM_Node):
    indexing: list['Wall'] = list()
    
    def __init__(self, guid: str|None, name: str|None,
                 u_value: float|None = None,
                 isExternal: bool|None = None,
                 vertices: list[tuple[float, float, float]]|None = None,
                 area: float|None = None,
                 azimuth: float|None = None,
                 tilt: float|None = None,
                 sun_exposure: bool|None = None,
                 wind_exposure: bool|None = None,
                 is_ground: bool|None = None):
        super().__init__(guid, name)
        Wall.indexing.append(self)
        self.u_value: float|None = u_value
        self.isExternal: bool|None = isExternal
        
        self.vertices: list[tuple[float, float, float]]|None = vertices
        self.area: float|None = area          # m2
        self.azimuth: float|None = azimuth    # Degrees
        self.tilt: float|None = tilt          # Degrees
        
        self.sun_exposure: bool = sun_exposure if sun_exposure is not None else bool(isExternal)
        self.wind_exposure: bool = wind_exposure if wind_exposure is not None else bool(isExternal)
        self.is_ground: bool = is_ground if is_ground is not None else False
        
        self.rooms: list[Room] = list()
        self.windows: list[Window] = list()
        self.layers: list[MaterialLayer] | Construction = list()
        pass
    
    def verify(self,
               IssueList: list[Issue]):
            if not self.guid:
                IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
            if not self.name:
                IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
                
            if not self.u_value:
                IssueList.append(MissingValueIssue(self, 'Missing U-Value', 'u_value'))
            elif self.u_value <= 0:
                IssueList.append(ValueSanityIssue(self, 'Invalid U-Value', 'u_value', (0.001, float('inf'))))
                
            if self.isExternal is None:
                IssueList.append(MissingValueIssue(self, 'Missing isExternal flag', 'isExternal'))
                
            if not self.vertices:
                IssueList.append(MissingValueIssue(self, 'Missing vertices', 'vertices'))
                
            num_rooms = len(self.rooms)
            if num_rooms not in (1, 2):
                IssueList.append(MissingEdgeIssue(self, f'Wall must have exactly 1 or 2 rooms, found {num_rooms}', 'rooms'))
                
            if isinstance(self.layers,list) and len(self.layers) < 1:
                            IssueList.append(MissingEdgeIssue(self, f'Wall must have at least 1 material layer, found {len(self.layers)}. You can also use Construction.', 'layers'))
            pass

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
class Window(BIM_Node):
    indexing: list['Window'] = list()

    def __init__(self, guid: str|None, name: str|None,
                 u_value: float|None = None,
                 solar_heat_gain_coefficient: float|None = None,
                 vertices: list[tuple[float, float, float]]|None = None,
                 area: float|None = None,
                 azimuth: float|None = None,
                 tilt: float|None = None,):
        super().__init__(guid, name)
        Window.indexing.append(self)
        self.u_value: float|None = u_value
        self.wall: Wall|None = None
        self.shgc: float|None = solar_heat_gain_coefficient
        
        self.vertices: list[tuple[float, float, float]]|None = vertices
        self.area: float|None = area
        self.azimuth: float|None = azimuth
        self.tilt: float|None = tilt
        pass
    
    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()

    def verify(self,
               IssueList: list[Issue]):
        
            if not self.guid:
                IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
            if not self.name:
                IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
                
            if not self.u_value:
                IssueList.append(MissingValueIssue(self, 'Missing U-Value', 'u_value'))
            elif self.u_value <= 0:
                IssueList.append(ValueSanityIssue(self, 'Invalid U-Value', 'u_value', (0.001, float('inf'))))
                
            if not self.shgc:
                IssueList.append(MissingValueIssue(self, 'Missing SHGC', 'shgc'))
            elif self.shgc <= 0:
                IssueList.append(ValueSanityIssue(self, 'Invalid SHGC', 'shgc', (0.001, float('inf'))))
                
            if not self.wall:
                IssueList.append(MissingEdgeIssue(self, 'Window must have a wall pointer', 'wall'))
                
            if not self.vertices:
                IssueList.append(MissingValueIssue(self, 'Missing vertices', 'vertices'))
            pass

class Roof(BIM_Node):
    indexing: list['Roof'] = list()

    def __init__(self, guid: str|None, name: str|None,
                 u_value: float|None = None,
                 vertices: list[tuple[float, float, float]]|None = None,
                 area: float|None = None,
                 azimuth: float|None = None,
                 tilt: float|None = None,
                 sun_exposure: bool|None = None,
                 wind_exposure: bool|None = None):
        super().__init__(guid, name)
        Roof.indexing.append(self)
        self.u_value: float|None = u_value
        self.layers: list[MaterialLayer] | Construction = list()
        self.rooms: list[Room] = list()
        
        self.vertices: list[tuple[float, float, float]]|None = vertices
        self.area: float|None = area
        self.azimuth: float|None = azimuth
        self.tilt: float|None = tilt
        
        self.sun_exposure: bool = sun_exposure if sun_exposure is not None else True
        self.wind_exposure: bool = wind_exposure if wind_exposure is not None else True
        pass

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
    def verify(self,
               IssueList: list[Issue]):
            if not self.guid:
                IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
            if not self.name:
                IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
                
            if not self.u_value:
                IssueList.append(MissingValueIssue(self, 'Missing U-Value', 'u_value'))
            elif self.u_value <= 0:
                IssueList.append(ValueSanityIssue(self, 'Invalid U-Value', 'u_value', (0.001, float('inf'))))
                
            if not self.vertices:
                IssueList.append(MissingValueIssue(self, 'Missing vertices', 'vertices'))
                
            if len(self.rooms) < 1:
                IssueList.append(MissingEdgeIssue(self, 'Roof must be connected to at least 1 room', 'rooms'))
                
            if isinstance(self.layers,list) and len(self.layers) < 1:
                IssueList.append(MissingEdgeIssue(self, f'Roof must have at least 1 material layer, found {len(self.layers)}. You can also use Construction.', 'layers'))
            pass

class Slab(BIM_Node):
    indexing: list['Slab'] = list()

    def __init__(self, guid: str|None, name: str|None,
                 u_value: float|None = None,
                 vertices: list[tuple[float, float, float]]|None = None,
                 area: float|None = None,
                 azimuth: float|None = None,
                 tilt: float|None = None,
                 is_ground: bool|None = None,
                 sun_exposure: bool|None = None,
                 wind_exposure: bool|None = None):
        super().__init__(guid, name)
        Slab.indexing.append(self)
        self.u_value: float|None = u_value
        self.layers: list[MaterialLayer] | Construction = list()
        self.rooms: list[Room] = list()
        
        self.vertices: list[tuple[float, float, float]]|None = vertices
        self.area: float|None = area
        self.azimuth: float|None = azimuth
        self.tilt: float|None = tilt
        
        self.is_ground: bool|None = is_ground
        self.sun_exposure: bool = sun_exposure if sun_exposure is not None else False
        self.wind_exposure: bool = wind_exposure if wind_exposure is not None else False
        pass

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
    def verify(self,
               IssueList: list[Issue]):
            if not self.guid:
                IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
            if not self.name:
                IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
                
            if not self.u_value:
                IssueList.append(MissingValueIssue(self, 'Missing U-Value', 'u_value'))
            elif self.u_value <= 0:
                IssueList.append(ValueSanityIssue(self, 'Invalid U-Value', 'u_value', (0.001, float('inf'))))
                
            if not self.vertices:
                IssueList.append(MissingValueIssue(self, 'Missing vertices', 'vertices'))
                
            num_rooms = len(self.rooms)
            if num_rooms not in (1, 2):
                IssueList.append(MissingEdgeIssue(self, f'Slab must have exactly 1 or 2 rooms, found {num_rooms}', 'rooms'))
            elif num_rooms == 1 and self.is_ground is None:
                IssueList.append(MissingValueIssue(self, f'Exterior slab {self.name} must specify is_ground (True for ground contact, False for exposed floor)', 'is_ground'))
                
            if isinstance(self.layers,list) and len(self.layers) < 1:
                IssueList.append(MissingEdgeIssue(self, f'Slab must have at least 1 material layer, found {len(self.layers)}. You can also use Construction.', 'layers'))
             
            pass
        
class MaterialLayer(BIM_Node):
    indexing: list['MaterialLayer'] = list()

    def __init__(self, guid: str|None, name: str|None,
                 thickness: float|None = None,
                 material_name: str|None = None,
                 conductivity: float|None = None,
                 density: float|None = None,
                 specific_heat: float|None = None,
                 resistance: float|None = None,):
        super().__init__(guid, name)
        MaterialLayer.indexing.append(self)
        self.thickness: float|None = thickness
        self.material_name: str|None = material_name
        self.conductivity: float|None = conductivity
        self.density: float|None = density
        self.specific_heat: float|None = specific_heat
        self.resistance: float|None = resistance
        self.belongs_to: Wall|Roof|Slab|None = None
        pass

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
    def verify(self,
               IssueList: list[Issue]):
            if not self.guid:
                IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
            if not self.name:
                IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
                
            if not self.resistance:
                if not (self.thickness or self.conductivity or self.density or self.specific_heat):
                    IssueList.append(MissingValueIssue(self, 'Missing resistance','resistance'))
                elif not (self.thickness and self.conductivity and self.density and self.specific_heat):
                    if not self.thickness:
                        IssueList.append(MissingValueIssue(self, 'Missing thickness', 'thickness'))
                    elif self.thickness <= 0:
                        IssueList.append(ValueSanityIssue(self, 'Invalid thickness', 'thickness', (0.001, float('inf'))))
                        
                    if not self.conductivity:
                        IssueList.append(MissingValueIssue(self, 'Missing conductivity', 'conductivity'))
                    elif self.conductivity <= 0:
                        IssueList.append(ValueSanityIssue(self, 'Invalid conductivity', 'conductivity', (0.001, float('inf'))))
                        
                    if not self.density:
                        IssueList.append(MissingValueIssue(self, 'Missing density', 'density'))
                    elif self.density <= 0:
                        IssueList.append(ValueSanityIssue(self, 'Invalid density', 'density', (0.001, float('inf'))))
                        
                    if not self.specific_heat:
                        IssueList.append(MissingValueIssue(self, 'Missing specific heat', 'specific_heat'))
                    elif self.specific_heat <= 0:
                        IssueList.append(ValueSanityIssue(self, 'Invalid specific heat', 'specific_heat', (0.001, float('inf'))))
            elif self.resistance <= 0:
                IssueList.append(ValueSanityIssue(self, 'Invalid resistance','resistance',(0.001,float('inf'))))
                
            if not self.material_name:
                IssueList.append(MissingValueIssue(self, 'Missing material name', 'material_name'))
                
            if not self.belongs_to:
                IssueList.append(MissingEdgeIssue(self, 'MaterialLayer must have a belongs_to pointer', 'belongs_to'))
                
            pass

class Construction(BIM_Node):
    indexing: list['Construction'] = list()

    def __init__(self, guid: str|None, name: str|None,
                 u_value: float|None = None,
                 resistance: float|None = None,
                 layer_count: int|None = None,
                 outside_material: str|None = None,
                 inside_material: str|None = None,
                 area_heat_capacity: float|None = None,
                 solar_absorptance: float|None = None):
        super().__init__(guid, name)
        Construction.indexing.append(self)
        self.u_value: float|None = u_value
        self.resistance: float|None = resistance
        self.layer_count: int|None = layer_count
        self.outside_material: str|None = outside_material
        self.inside_material: str|None = inside_material
        self.area_heat_capacity: float|None = area_heat_capacity
        self.solar_absorptance: float|None = solar_absorptance
        pass

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
    def verify(self,
               IssueList: list[Issue]):
        if not self.guid:
            IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
        if not self.name:
            IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
            
        if not self.resistance:
            IssueList.append(MissingValueIssue(self, 'Missing resistance', 'resistance'))
        elif self.resistance <= 0:
            IssueList.append(ValueSanityIssue(self, 'Invalid resistance', 'resistance', (0.001, float('inf'))))
            
        if not self.layer_count:
            IssueList.append(MissingValueIssue(self, 'Missing layer_count', 'layer_count'))
        elif self.layer_count <= 0:
            IssueList.append(ValueSanityIssue(self, 'Invalid layer_count', 'layer_count', (0.001, float('inf'))))
            
        if self.area_heat_capacity is None:
            IssueList.append(MissingValueIssue(self, 'Missing area heat capacity', 'area_heat_capacity'))
        elif self.area_heat_capacity <= 0:
            IssueList.append(ValueSanityIssue(self, 'Invalid area heat capacity (must be > 0 J/(m2·K))', 'area_heat_capacity', (0.001, float('inf'))))
            
        if self.solar_absorptance is not None:
            if self.solar_absorptance < 0.0 or self.solar_absorptance > 1.0:
                IssueList.append(ValueSanityIssue(self, 'Solar absorptance must be between 0.0 and 1.0', 'solar_absorptance', (0.0, 1.0)))
        
        # Should probably make sure these materials exist in materials.csv but lets worry about that later.
        if not self.outside_material:
            IssueList.append(MissingValueIssue(self, 'Missing outside_material', 'outside_material'))
            
        if not self.inside_material:
            IssueList.append(MissingValueIssue(self, 'Missing inside_material', 'inside_material'))

        
        