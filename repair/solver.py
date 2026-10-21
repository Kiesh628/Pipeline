from diagnosis import Mutation, DataSwap, Solution, Issue, Fatality, Form
from building_modelling.topology import *
from building_modelling import BIM_Node
from building_modelling.hvac import *
from .geometry import bounding_box, isIntersecting, room_volume, centriod, distance_to_plane

def propose_solutions(issue: Issue, model: Model) -> list[Solution] | Fatality:
    
    if not hasattr(issue, 'variable_name'):
        return Fatality(issue,'Server Error: cannot find variable_name')
    
    match issue.variable_name:
        
        # 1. Names
        case 'name': 
            auto_name = f'{issue.node.__class__.__name__}_{id(issue.node)}'
            return [
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name=issue.variable_name, new_value=auto_name, operation='Set')],
                    description=f'Assign name {auto_name} to node {issue.node}'
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                    description='Enter custom name'
                )
            ]
            
        case 'height':
            return [ Solution(mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                              description='Enter room height manually')]
                              
        # 1b. Geometric Healing: Missing Volume
        case 'volume':
            room_node: Room = issue.node #type:ignore
            if not getattr(room_node, 'vertices', None) or not getattr(room_node, 'height', None):
                return Fatality(issue, f'Cannot calculate volume for {room_node.name} because vertices or height are missing.')
            
            calc_volume:float = room_volume(room_node) #type:ignore
            
            return [
                Solution(
                    mutations=[Mutation(node=room_node, variable_name='volume', new_value=calc_volume, operation='Set')],
                    description=f"Auto-calculate volume: {calc_volume:.2f} m³"
                ),
                Solution(
                    mutations=[Form(node=room_node, variable_name='volume')],
                    description="Enter room volume manually"
                )
            ]
        
        # 2. Site Coordinates & Elevation
        case 'latitude' | 'longitude' | 'elevation' | 'shgc':
            return [
                Solution(
                    mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                    description=f'Enter {issue.variable_name} manually'
                )
            ]
            
        # 2b. Site Weather File Resolution
        case 'weather_file':
            from weather import find_nearest_weather_stations
            site_node: Site = issue.node #type: ignore
            weather_solutions = []
            if site_node.latitude is not None and site_node.longitude is not None:
                try:
                    stations = find_nearest_weather_stations(site_node.latitude, site_node.longitude, top_k=3)
                    for idx, station in enumerate(stations):
                        prefix = "(Recommended) " if idx == 0 else ""
                        weather_solutions.append(
                            Solution(
                                mutations=[Mutation(node=site_node, variable_name='weather_file', new_value=station['epw_url'], operation='Set')],
                                description=f"{prefix}Use nearest station: {station['title']} ({station['distance_km']:.1f} km away)"
                            )
                        )
                except Exception:
                    pass
            weather_solutions.append(
                Solution(
                    mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                    description="Enter local EPW file path manually"
                )
            )
            return weather_solutions
            
        # 3. Constructions (Walls, Roofs, Slabs)
        case 'u_value' | 'layers' | 'construction_name' | 'area_heat_capacity' | 'solar_absorptance':
            return [
                Solution(
                    mutations=[DataSwap(node=issue.node, lookup_type='constructions')],
                    description='Swap with standard ASHRAE Construction'
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                    description=f'Enter a custom {issue.variable_name} manually'
                )
            ]
            
        # 4. Materials (MaterialLayer properties)
        case 'density' | 'conductivity' | 'specific_heat' | 'thickness' | 'resistance':
            return [
                Solution(
                    mutations=[DataSwap(node=issue.node, lookup_type='materials')],
                    description='Swap with standard ASHRAE Material'
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                    description=f'Enter a custom {issue.variable_name} manually'
                )
            ]
            
        # 5. Room Loads
        case 'lighting_load' | 'occupant_sensible_heat' | 'occupant_latent_heat' | 'infiltration_rate' | 'people_density' | 'ventilation_rate':
            return [
                Solution(
                    mutations=[DataSwap(node=issue.node, lookup_type='room_loads')],
                    description='Apply Standard ASHRAE Room Loads Template'
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                    description=f'Enter a custom {issue.variable_name} manually'
                )
            ]
            
        # 5b. Slab Ground Contact vs Exposed
        case 'is_ground':
            return [
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name='is_ground', new_value=True, operation='Set')],
                    description='Set slab to Ground Contact (Slab on grade / basement)'
                ),
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name='is_ground', new_value=False, operation='Set')],
                    description='Set slab to Exposed / Cantilevered Exterior Floor'
                )
            ]
            
        # 5c. Thermostat Deadband
        case 'deadband':
            return [
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name='deadband', new_value=2.0, operation='Set')],
                    description='Set standard 2.0 °C deadband'
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name='deadband')],
                    description='Enter custom deadband (°C) manually'
                )
            ]
            
        # 5d. Furniture Heat Capacity
        case 'furniture_heat_capacity':
            return [
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name='furniture_heat_capacity', new_value=20000.0, operation='Set')],
                    description='Set default ASHRAE furniture heat capacity (20,000 J/m²·K)'
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name='furniture_heat_capacity')],
                    description='Enter custom furniture heat capacity (J/m²·K) manually'
                )
            ]
            
        # 6. Schedules
        case 'occupancy_schedule' | 'lighting_schedule':
            return [
                Solution(
                    mutations=[DataSwap(node=issue.node, lookup_type='schedules')],
                    description='Apply Standard ASHRAE Schedule'
                )
            ]
            
        # 7. Geometric Healing: Missing Rooms
        case 'rooms':
            if not isinstance(issue.node, (Wall, Roof, Slab)):
                return Fatality(issue, 'rooms case only applies to Wall, Roof, or Slab')
            node = issue.node
            if node.vertices is None or len(node.vertices) == 0:
                return Fatality(issue, f'Cannot find touching rooms for {node.name} because its vertices are missing.')
                
            node_bb = bounding_box(node.vertices)
            found_rooms = []
            
            for floor in model.floors:
                if floor.elevation is None:
                    continue
                for room in floor.rooms:
                    if room.height is None or not room.vertices:
                        continue
                    min_x = min(v[0] for v in room.vertices)
                    max_x = max(v[0] for v in room.vertices)
                    min_y = min(v[1] for v in room.vertices)
                    max_y = max(v[1] for v in room.vertices)
                    
                    room_bb = [(min_x, min_y, floor.elevation), (max_x, max_y, floor.elevation + room.height)]
                    
                    if isIntersecting(node_bb, room_bb, tolerance=0.15):
                        found_rooms.append(room)
                        
            if not found_rooms:
                return Fatality(issue, f'Could not find any touching rooms for {issue.node.name}.')
                
            mutations = []
            for room in found_rooms:
                mutations.append(Mutation(node=issue.node, variable_name='rooms', new_value=room, operation='Append'))
                
            if issue.node.__class__.__name__ == 'Wall':
                mutations.append(Mutation(node=issue.node, variable_name='isExternal', new_value=(len(found_rooms) == 1), operation='Set'))
                
            desc = f"Auto-link to {len(found_rooms)} touching rooms"
            if issue.node.__class__.__name__ == 'Wall':
                desc += " and set isExternal flag"
                
            return [Solution(mutations=mutations, description=desc)]
            
        # 8. Geometric Healing: Missing Wall on Window
        case 'wall':
            if not isinstance(issue.node, Window):
                return Fatality(issue, 'wall case only applies to Window')
            node = issue.node
            if node.vertices is None or len(node.vertices) == 0:
                return Fatality(issue, f'Cannot find host wall for {node.name} because window vertices are missing.')
                
            window_bb = bounding_box(node.vertices)
            window_center = centriod(node.vertices)
            found_wall = None
            min_dist = 0.15 # Max tolerance
            
            for wall in [n for n in BIM_Node.registry if isinstance(n, Wall)]:
                if wall.vertices is None or len(wall.vertices) < 3:
                    continue
                    
                wall_bb = bounding_box(wall.vertices)
                
                # 1. Rough check: Do their 3D bounding boxes overlap?
                if isIntersecting(window_bb, wall_bb, tolerance=0.15):
                    # 2. Precise check: Distance from window center to wall plane
                    dist = distance_to_plane(window_center, wall.vertices)
                    if dist < min_dist:
                        min_dist = dist
                        found_wall = wall
                                
            if not found_wall:
                return Fatality(issue, f'Could not find any overlapping host wall for window {node.name}.')
                
            return [
                Solution(
                    mutations=[Mutation(node=node, variable_name='wall', new_value=found_wall, operation='Set')],
                    description=f"Auto-link to host wall {found_wall.name} (dist: {min_dist:.3f}m)"
                )
            ]
            
        # 9. Geometric Healing: Missing Roof on Room
        case 'roofs':
            if not isinstance(issue.node, Room):
                return Fatality(issue, 'roofs case only applies to Room')
            node = issue.node
            
            if node.vertices is None or len(node.vertices) == 0 or node.height is None:
                return Fatality(issue, f'Cannot generate roof for {node.name} because room footprint or height is missing.')
            if node.floor is None or node.floor.elevation is None:
                return Fatality(issue, f'Cannot generate roof for {node.name} because room floor elevation is missing.')
            
            import uuid
            
            # The roof sits exactly at the ceiling height
            roof_z = node.floor.elevation + node.height
            roof_vertices = [(v[0], v[1], roof_z) for v in node.vertices]
            
            auto_roof = Roof(guid=str(uuid.uuid4()), name=f"{node.name}_AutoRoof", vertices=roof_vertices)
            auto_roof.rooms.append(node) # Bidirectional link
            
            return [
                Solution(
                    mutations=[Mutation(node=node, variable_name='roofs', new_value=auto_roof, operation='Append')],
                    description="Auto-generate Flat Roof from room footprint"
                )
            ]
            
        # 10. Geometric Healing: Missing Floor/Slab on Room
        case 'floor':
            if not isinstance(issue.node, Room):
                return Fatality(issue, 'floor case only applies to Room')
            room_floor_node = issue.node
            
            if room_floor_node.vertices is None or len(room_floor_node.vertices) == 0:
                return Fatality(issue, f'Cannot generate floor slab for {room_floor_node.name} because room footprint is missing.')
            if room_floor_node.floor is None or room_floor_node.floor.elevation is None:
                return Fatality(issue, f'Cannot generate floor slab for {room_floor_node.name} because room floor elevation is missing.')
            
            import uuid
            # The slab sits exactly at the floor elevation
            slab_z = room_floor_node.floor.elevation
            slab_vertices = [(v[0], v[1], slab_z) for v in room_floor_node.vertices]
            
            auto_slab = Slab(guid=str(uuid.uuid4()), name=f"{room_floor_node.name}_AutoSlab", vertices=slab_vertices)
            auto_slab.rooms.append(room_floor_node) # Bidirectional link
            
            return [
                Solution(
                    mutations=[Mutation(node=room_floor_node, variable_name='slabs', new_value=auto_slab, operation='Append')],
                    description="Auto-generate Floor Slab from room footprint"
                )
            ]
            
        # 11. Missing Parent Building on Floor
        case 'building':
            if not isinstance(issue.node, Floor):
                return Fatality(issue, 'building case only applies to Floor')
            
            return [
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name='building', new_value=model, operation='Set')],
                    description=f"Auto-link to current model '{model.name}'"
                )
            ]
            
        # 12. HVAC: Missing Thermostat on Conditioned Room
        case 'thermostat':
            import uuid
            auto_thermo = Thermostat(guid=str(uuid.uuid4()), name=f"{issue.node.name}_Thermostat")
            auto_thermo.room = issue.node #type: ignore
            auto_thermo.heating_setpoint = 21.0
            auto_thermo.cooling_setpoint = 24.0
            if hasattr(issue.node, 'equipment') and getattr(issue.node, 'equipment'):
                auto_thermo.controls_terminal = getattr(issue.node, 'equipment')[0]
                
            return [
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name='thermostat', new_value=auto_thermo, operation='Set')],
                    description="Auto-create standard Thermostat (21°C Heat / 24°C Cool)"
                )
            ]
            
        # 13. HVAC: Setpoints
        case 'heating_setpoint':
            return [
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name='heating_setpoint', new_value=21.0, operation='Set')],
                    description="Apply Standard ASHRAE Heating Setpoint (21.0°C)"
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name='heating_setpoint')],
                    description="Enter heating setpoint manually"
                )
            ]
            
        case 'cooling_setpoint':
            return [
                Solution(
                    mutations=[Mutation(node=issue.node, variable_name='cooling_setpoint', new_value=24.0, operation='Set')],
                    description="Apply Standard ASHRAE Cooling Setpoint (24.0°C)"
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name='cooling_setpoint')],
                    description="Enter cooling setpoint manually"
                )
            ]
            
        # 14. HVAC: Equipment Sizing
        case 'capacity' | 'pump_flow_rate' | 'design_air_flow_rate' | 'max_air_flow_rate' | 'max_water_flow_rate':
            solutions: list[Solution] = []
            try:
                from autosize import autosize
                sizing_mutations: list[Mutation | DataSwap | Form] = list(autosize(issue.node)) # type: ignore
                solutions.append(
                    Solution(
                        mutations=sizing_mutations,
                        description=f"(Recommended) Calculate physical ratings via EnergyPlus sizing pass"
                    )
                )
            except Exception:
                pass

            solutions.extend([
                Solution(
                    mutations=[DataSwap(node=issue.node, lookup_type='hvac_equipment')],
                    description="Select rated equipment from ASHRAE Catalog"
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                    description=f"Enter {issue.variable_name} manually"
                )
            ])
            return solutions
            
        # 14b. HVAC: General Equipment Properties & Catalog
        case 'efficiency' | 'design_supply_temp' | 'min_supply_temp' | 'max_supply_temp' | 'fan_efficiency' | 'fan_pressure_rise':
            return [
                Solution(
                    mutations=[DataSwap(node=issue.node, lookup_type='hvac_equipment')],
                    description="Swap with standard ASHRAE HVAC Equipment catalog"
                ),
                Solution(
                    mutations=[Form(node=issue.node, variable_name=issue.variable_name)],
                    description=f"Enter {issue.variable_name} manually"
                )
            ]
            
        # 15. HVAC: AirLoop Connection
        case 'air_loop':
            available_loops = [n for n in BIM_Node.registry if isinstance(n, AirLoop)]
            if not available_loops:
                return Fatality(issue, f"No AirLoops exist in the building to connect terminal '{issue.node.name}' to.")
            loop_solutions = []
            for loop in available_loops:
                loop_solutions.append(
                    Solution(
                        mutations=[
                            Mutation(node=issue.node, variable_name='air_loop', new_value=loop, operation='Set'),
                            Mutation(node=loop, variable_name='served_terminals', new_value=issue.node, operation='Append')
                        ],
                        description=f"Connect to AirLoop '{loop.name}'"
                    )
                )
            return loop_solutions
            
        # 16. HVAC: Plant Sources (Heating & Cooling)
        case 'heating_source':
            available_heaters = [n for n in BIM_Node.registry if isinstance(n, PlantSystem) and n.plant_type in ['Boiler', 'HeatPump']]
            if not available_heaters:
                return Fatality(issue, f"No Boilers or HeatPumps exist in the building to supply '{issue.node.name}'.")
            heat_solutions = []
            for plant in available_heaters:
                muts: list[Mutation | DataSwap | Form] = [Mutation(node=issue.node, variable_name='heating_source', new_value=plant, operation='Set')]
                if isinstance(issue.node, AirLoop):
                    muts.append(Mutation(node=plant, variable_name='served_air_loops', new_value=issue.node, operation='Append'))
                elif isinstance(issue.node, ZoneTerminal):
                    muts.append(Mutation(node=plant, variable_name='served_terminals', new_value=issue.node, operation='Append'))
                heat_solutions.append(Solution(mutations=muts, description=f"Connect heating to '{plant.name}' ({plant.plant_type})"))
            return heat_solutions
            
        case 'cooling_source':
            available_coolers = [n for n in BIM_Node.registry if isinstance(n, PlantSystem) and n.plant_type in ['Chiller', 'HeatPump']]
            if not available_coolers:
                return Fatality(issue, f"No Chillers or HeatPumps exist in the building to supply '{issue.node.name}'.")
            cool_solutions = []
            for plant in available_coolers:
                muts: list[Mutation | DataSwap | Form] = [Mutation(node=issue.node, variable_name='cooling_source', new_value=plant, operation='Set')]
                if isinstance(issue.node, AirLoop):
                    muts.append(Mutation(node=plant, variable_name='served_air_loops', new_value=issue.node, operation='Append'))
                elif isinstance(issue.node, ZoneTerminal):
                    muts.append(Mutation(node=plant, variable_name='served_terminals', new_value=issue.node, operation='Append'))
                cool_solutions.append(Solution(mutations=muts, description=f"Connect cooling to '{plant.name}' ({plant.plant_type})"))
            return cool_solutions
            
        # 17. HVAC: Thermostat terminal linkage
        case 'controls_terminal':
            thermo: Thermostat = issue.node #type: ignore
            if thermo.room and hasattr(thermo.room, 'equipment') and getattr(thermo.room, 'equipment'):
                terminals = getattr(thermo.room, 'equipment')
                return [
                    Solution(
                        mutations=[Mutation(node=thermo, variable_name='controls_terminal', new_value=term, operation='Set')],
                        description=f"Auto-link to terminal '{term.name}' in same room"
                    ) for term in terminals
                ]
            return Fatality(issue, f"No terminal equipment found in room '{thermo.room.name if thermo.room else 'None'}' to control.")
            
        case _:
            return Fatality(issue, f'No solver logic currently implemented for variable: {issue.variable_name}')