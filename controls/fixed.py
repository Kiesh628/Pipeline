import numpy as np
from numpy.typing import NDArray

from building_modelling.topology import *
from building_modelling.hvac import *
from repair.geometry import room_volume

air_density = 1.204
air_specific_heat_capacity = 1005.0
indoor_air_film_resistance = 0.12
absolute_zero = 273.15
standard_rating_ambient_temperature_heating = 7.0
standard_rating_ambient_temperature_cooling = 35.0
minimum_temperature_difference_kelvin = 1.0
maximum_coefficient_of_performance = 15.0
electric_resistance_coefficient_of_performance = 1.0

class Uninitialised(Exception):
    pass

def capacitance_per_area(surface: Wall | Roof | Slab) -> float:
    if isinstance(surface.layers, Construction):
        if surface.layers.area_heat_capacity is not None and surface.layers.area_heat_capacity > 0.0:
            return surface.layers.area_heat_capacity
        raise Uninitialised(f"Construction {surface.layers.name} missing valid area_heat_capacity")
    
    elif isinstance(surface.layers, list):
        if len(surface.layers) == 0:
            raise Uninitialised(f"Surface {surface.name} has empty layers")
        total_capacitance = 0.0
        for layer in surface.layers:
            if layer.thickness is not None and layer.density is not None and layer.specific_heat is not None:
                if layer.thickness <= 0.0 or layer.density <= 0.0 or layer.specific_heat <= 0.0:
                    raise Uninitialised(f"Layer {layer.name} has non-positive thermal properties")
                total_capacitance += layer.thickness * layer.density * layer.specific_heat
            else:
                raise Uninitialised(f"Layer {layer.name} missing thickness, density, or specific heat")
        return total_capacitance

    raise Uninitialised(f"Surface {surface.name} has invalid layers configuration")

def C_air_volume() -> NDArray[np.float64]:
    air_volume_capacitances: list[float] = []
    for room in Room.indexing:
        if room.height is None or room.height <= 0.0:
            raise Uninitialised(f"Room {room.name} missing valid height")
        volume = room_volume(room)
        if volume <= 0.0:
            raise Uninitialised(f"Room {room.name} has non-positive volume")
        air_volume_capacitances.append(air_density * air_specific_heat_capacity * volume)
    return np.array(air_volume_capacitances, dtype=np.float64)

def C_wall() -> NDArray[np.float64]:
    wall_capacitances: list[float] = []
    for room in Room.indexing:
        room_wall_capacitance = 0.0
        for wall in room.walls:
            if wall.area is None or wall.area <= 0.0:
                raise Uninitialised(f"Wall {wall.name} missing valid area")
            room_wall_capacitance += 0.5 * wall.area * capacitance_per_area(wall)
        wall_capacitances.append(room_wall_capacitance)
    return np.array(wall_capacitances, dtype=np.float64)

def C_roof() -> NDArray[np.float64]:
    roof_capacitances = np.zeros(len(Room.indexing), dtype=np.float64)
    for roof in Roof.indexing:
        if roof.area is None or roof.area <= 0.0:
            raise Uninitialised(f"Roof {roof.name} missing valid area")
        if len(roof.rooms) == 0:
            raise Uninitialised(f"Roof {roof.name} has no rooms assigned")
        roof_heat_capacity = capacitance_per_area(roof) * roof.area
        for room in roof.rooms:
            if room.height is None or room.height <= 0.0:
                raise Uninitialised(f"Room {room.name} missing valid height")
            volume = room_volume(room)
            if volume <= 0.0:
                raise Uninitialised(f"Room {room.name} has non-positive volume")
            floor_area = volume / room.height
            area_fraction = floor_area / roof.area
            room_index = Room.indexing.index(room)
            roof_capacitances[room_index] += 0.5 * area_fraction * roof_heat_capacity
    return roof_capacitances

def C_slab() -> NDArray[np.float64]:
    slab_capacitances = np.zeros(len(Room.indexing), dtype=np.float64)
    for slab in Slab.indexing:
        if slab.area is None or slab.area <= 0.0:
            raise Uninitialised(f"Slab {slab.name} missing valid area")
        slab_heat_capacity = capacitance_per_area(slab) * slab.area
        match len(slab.rooms):
            case 2:
                room_index_1 = Room.indexing.index(slab.rooms[0])
                room_index_2 = Room.indexing.index(slab.rooms[1])
                slab_capacitances[room_index_1] += 0.5 * slab_heat_capacity
                slab_capacitances[room_index_2] += 0.5 * slab_heat_capacity
            case 1:
                room_index = Room.indexing.index(slab.rooms[0])
                slab_capacitances[room_index] += 0.5 * slab_heat_capacity
            case _:
                raise Uninitialised(f"Slab {slab.name} must connect to 1 or 2 rooms")
    return slab_capacitances

def C_furniture() -> NDArray[np.float64]:
    furniture_capacitances: list[float] = []
    for room in Room.indexing:
        if room.height is None or room.height <= 0.0:
            raise Uninitialised(f"Room {room.name} missing valid height")
        if room.furniture_heat_capacity is None or room.furniture_heat_capacity <= 0.0:
            raise Uninitialised(f"Room {room.name} missing valid furniture_heat_capacity")
        volume = room_volume(room)
        if volume <= 0.0:
            raise Uninitialised(f"Room {room.name} has non-positive volume")
        floor_area = volume / room.height
        furniture_capacitances.append(room.furniture_heat_capacity * floor_area)
    return np.array(furniture_capacitances, dtype=np.float64)

def C() -> NDArray[np.float64]:
    total_capacitances = C_air_volume() + C_wall() + C_roof() + C_slab() + C_furniture()
    return total_capacitances

def K_interroom() -> NDArray[np.float64]:
    number_of_rooms = len(Room.indexing)
    interroom_conductances = np.zeros((number_of_rooms, number_of_rooms), dtype=np.float64)

    for surface in Wall.indexing + Slab.indexing:
        if len(surface.rooms) == 2:
            if surface.u_value is None or surface.u_value <= 0.0:
                raise Uninitialised(f"Surface {surface.name} missing valid U-value")
            if surface.area is None or surface.area <= 0.0:
                raise Uninitialised(f"Surface {surface.name} missing valid area")

            room_index_1 = Room.indexing.index(surface.rooms[0])
            room_index_2 = Room.indexing.index(surface.rooms[1])
            conductance = surface.u_value * surface.area

            interroom_conductances[room_index_1, room_index_2] += conductance
            interroom_conductances[room_index_2, room_index_1] += conductance

    for room_index in range(number_of_rooms):
        interroom_conductances[room_index, room_index] = -np.sum(interroom_conductances[room_index, :])

    return interroom_conductances

def K_ambient() -> NDArray[np.float64]:
    ambient_conductances = np.zeros(len(Room.indexing), dtype=np.float64)

    for room in Room.indexing:
        room_index = Room.indexing.index(room)
        for wall in room.walls:
            if wall.isExternal and not wall.is_ground:
                if wall.u_value is None or wall.u_value <= 0.0:
                    raise Uninitialised(f"Exterior wall {wall.name} missing valid U-value")
                if wall.area is None or wall.area <= 0.0:
                    raise Uninitialised(f"Exterior wall {wall.name} missing valid area")

                total_window_area = 0.0
                total_window_conductance = 0.0
                for window in wall.windows:
                    if window.u_value is None or window.u_value <= 0.0:
                        raise Uninitialised(f"Window {window.name} missing valid U-value")
                    if window.area is None or window.area <= 0.0:
                        raise Uninitialised(f"Window {window.name} missing valid area")
                    total_window_area += window.area
                    total_window_conductance += window.u_value * window.area

                if total_window_area > wall.area:
                    raise Uninitialised(f"Wall {wall.name} window area exceeds wall area")

                net_wall_area = wall.area - total_window_area
                wall_conductance = wall.u_value * net_wall_area
                ambient_conductances[room_index] += wall_conductance + total_window_conductance

    for roof in Roof.indexing:
        number_of_rooms = len(roof.rooms)
        if number_of_rooms == 0:
            raise Uninitialised(f"Roof {roof.name} has no rooms assigned")
        if roof.u_value is None or roof.u_value <= 0.0:
            raise Uninitialised(f"Roof {roof.name} missing valid U-value")
        if roof.area is None or roof.area <= 0.0:
            raise Uninitialised(f"Roof {roof.name} missing valid area")

        conductance_per_room = (roof.u_value * roof.area) / number_of_rooms
        for room in roof.rooms:
            room_index = Room.indexing.index(room)
            ambient_conductances[room_index] += conductance_per_room

    for slab in Slab.indexing:
        if len(slab.rooms) == 1 and slab.is_ground is False:
            if slab.u_value is None or slab.u_value <= 0.0:
                raise Uninitialised(f"Exposed slab {slab.name} missing valid U-value")
            if slab.area is None or slab.area <= 0.0:
                raise Uninitialised(f"Exposed slab {slab.name} missing valid area")
            room_index = Room.indexing.index(slab.rooms[0])
            ambient_conductances[room_index] += slab.u_value * slab.area

    return ambient_conductances

def K_ground() -> NDArray[np.float64]:
    ground_conductances = np.zeros(len(Room.indexing), dtype=np.float64)

    for slab in Slab.indexing:
        if len(slab.rooms) == 1:
            if slab.is_ground is None:
                raise Uninitialised(f"Exterior slab {slab.name} missing is_ground specification")
            if slab.is_ground is True:
                if slab.u_value is None or slab.u_value <= 0.0:
                    raise Uninitialised(f"Ground slab {slab.name} missing valid U-value")
                if slab.area is None or slab.area <= 0.0:
                    raise Uninitialised(f"Ground slab {slab.name} missing valid area")
                room_index = Room.indexing.index(slab.rooms[0])
                ground_conductances[room_index] += slab.u_value * slab.area

    for wall in Wall.indexing:
        if wall.is_ground:
            if len(wall.rooms) == 0:
                raise Uninitialised(f"Underground wall {wall.name} has no rooms assigned")
            if wall.u_value is None or wall.u_value <= 0.0:
                raise Uninitialised(f"Underground wall {wall.name} missing valid U-value")
            if wall.area is None or wall.area <= 0.0:
                raise Uninitialised(f"Underground wall {wall.name} missing valid area")

            conductance_per_room = (wall.u_value * wall.area) / len(wall.rooms)
            for room in wall.rooms:
                room_index = Room.indexing.index(room)
                ground_conductances[room_index] += conductance_per_room

    return ground_conductances

def K_infil_vent() -> NDArray[np.float64]:
    air_exchange_conductances: list[float] = []
    for room in Room.indexing:
        if room.infiltration_rate is None:
            raise Uninitialised(f"Room {room.name} missing infiltration_rate")
        if room.infiltration_rate < 0.0:
            raise Uninitialised(f"Room {room.name} has negative infiltration_rate")

        if room.ventilation_rate is None:
            raise Uninitialised(f"Room {room.name} missing ventilation_rate")
        if room.ventilation_rate < 0.0:
            raise Uninitialised(f"Room {room.name} has negative ventilation_rate")

        volume = room_volume(room)
        if volume <= 0.0:
            raise Uninitialised(f"Room {room.name} has non-positive volume")

        infiltration_volume_flow_rate = (room.infiltration_rate * volume) / 3600.0
        ventilation_volume_flow_rate = room.ventilation_rate
        total_air_volume_flow_rate = infiltration_volume_flow_rate + ventilation_volume_flow_rate

        air_exchange_conductance = air_density * air_specific_heat_capacity * total_air_volume_flow_rate
        air_exchange_conductances.append(air_exchange_conductance)

    return np.array(air_exchange_conductances, dtype=np.float64)

def A_matrix() -> NDArray[np.float64]:
    interroom_conductance_matrix = K_interroom()
    total_loss_conductances = K_ambient() + K_ground() + K_infil_vent()
    return interroom_conductance_matrix - np.diag(total_loss_conductances)


# Disturbance Vectors

def d_ambient(ambient_temperature: float) -> NDArray[np.float64]:
    return K_ambient() * ambient_temperature

def d_infil_vent(ambient_temperature: float) -> NDArray[np.float64]:
    return K_infil_vent() * ambient_temperature

def d_ground(ground_temperature: float) -> NDArray[np.float64]:
    return K_ground() * ground_temperature

def d_lighting(lighting_multiplier: float = 1.0) -> NDArray[np.float64]:
    lighting_powers: list[float] = []
    for room in Room.indexing:
        if room.lighting_load is None:
            raise Uninitialised(f"Room {room.name} missing lighting_load")
        if room.height is None or room.height <= 0.0:
            raise Uninitialised(f"Room {room.name} missing valid height")
        volume = room_volume(room)
        if volume <= 0.0:
            raise Uninitialised(f"Room {room.name} has non-positive volume")
        floor_area = volume / room.height
        lighting_powers.append(room.lighting_load * floor_area * lighting_multiplier)
    return np.array(lighting_powers, dtype=np.float64)

def d_equipment(equipment_multiplier: float = 1.0) -> NDArray[np.float64]:
    equipment_powers: list[float] = []
    for room in Room.indexing:
        if room.equipment_load is None:
            raise Uninitialised(f"Room {room.name} missing equipment_load")
        if room.height is None or room.height <= 0.0:
            raise Uninitialised(f"Room {room.name} missing valid height")
        volume = room_volume(room)
        if volume <= 0.0:
            raise Uninitialised(f"Room {room.name} has non-positive volume")
        floor_area = volume / room.height
        equipment_powers.append(room.equipment_load * floor_area * equipment_multiplier)
    return np.array(equipment_powers, dtype=np.float64)

def d_occupancy_sensible(occupancy_multiplier: float = 1.0) -> NDArray[np.float64]:
    occupant_powers: list[float] = []
    for room in Room.indexing:
        if room.people_density is None:
            raise Uninitialised(f"Room {room.name} missing people_density")
        if room.occupant_sensible_heat is None:
            raise Uninitialised(f"Room {room.name} missing occupant_sensible_heat")
        if room.height is None or room.height <= 0.0:
            raise Uninitialised(f"Room {room.name} missing valid height")
        volume = room_volume(room)
        if volume <= 0.0:
            raise Uninitialised(f"Room {room.name} has non-positive volume")
        floor_area = volume / room.height
        sensible_power = room.people_density * room.occupant_sensible_heat * floor_area * occupancy_multiplier
        occupant_powers.append(sensible_power)
    return np.array(occupant_powers, dtype=np.float64)

def d_solar(solar_irradiances: dict[str, float] | None = None) -> NDArray[np.float64]:
    solar_powers = np.zeros(len(Room.indexing), dtype=np.float64)
    for window in Window.indexing:
        if window.wall is None:
            continue
        if not window.wall.isExternal or window.wall.is_ground:
            continue
        if window.area is None or window.area <= 0.0:
            raise Uninitialised(f"Window {window.name} missing valid area")
        if window.shgc is None or window.shgc <= 0.0:
            raise Uninitialised(f"Window {window.name} missing valid shgc")
        
        incident_irradiance: float = 0.0
        if solar_irradiances is not None and window.name in solar_irradiances:
            incident_irradiance = solar_irradiances[window.name]
        elif solar_irradiances is not None and window.wall.name in solar_irradiances:
            incident_irradiance = solar_irradiances[window.wall.name]
            
        window_solar_gain = window.area * window.shgc * incident_irradiance
        for room in window.wall.rooms:
            room_index = Room.indexing.index(room)
            solar_powers[room_index] += window_solar_gain
            
    return solar_powers

def d_total(
    ambient_temperature: float,
    ground_temperature: float,
    lighting_multiplier: float = 1.0,
    equipment_multiplier: float = 1.0,
    occupancy_multiplier: float = 1.0,
    solar_irradiances: dict[str, float] | None = None,
) -> NDArray[np.float64]:
    return (
        d_ambient(ambient_temperature)
        + d_infil_vent(ambient_temperature)
        + d_ground(ground_temperature)
        + d_lighting(lighting_multiplier)
        + d_equipment(equipment_multiplier)
        + d_occupancy_sensible(occupancy_multiplier)
        + d_solar(solar_irradiances)
    )


# Control Inputs

def control_inputs() -> list[tuple[ZoneTerminal, Literal['heating', 'cooling']]]:
    input_connections: list[tuple[ZoneTerminal, Literal['heating', 'cooling']]] = []
    
    for terminal in ZoneTerminal.indexing:
        if terminal.room is None:
            raise Uninitialised(f"ZoneTerminal {terminal.name} has no room assigned")

        has_heating = False
        has_cooling = False

        if terminal.heating_source is not None:
            has_heating = True
        elif terminal.air_loop is not None and terminal.air_loop.heating_source is not None:
            has_heating = True
        elif terminal.terminal_type in ['PTAC', 'SplitAC']:
            has_heating = True

        if terminal.cooling_source is not None:
            has_cooling = True
        elif terminal.air_loop is not None and terminal.air_loop.cooling_source is not None:
            has_cooling = True
        elif terminal.terminal_type in ['PTAC', 'SplitAC']:
            has_cooling = True

        if has_heating:
            input_connections.append((terminal, 'heating'))
        if has_cooling:
            input_connections.append((terminal, 'cooling'))
        
    return input_connections


def B_thermal(actuator_channels: list[tuple[ZoneTerminal, Literal['heating', 'cooling']]]) -> NDArray[np.float64]:
    thermal_routing_matrix = np.zeros((len(Room.indexing), len(actuator_channels)), dtype=np.float64)
    
    for channel_index, (terminal, mode) in enumerate(actuator_channels):
        if terminal.room is None:
            raise Uninitialised(f"ZoneTerminal {terminal.name} has no room assigned")
        room_index = Room.indexing.index(terminal.room)
        if mode == 'heating':
            thermal_routing_matrix[room_index, channel_index] = 1.0
        elif mode == 'cooling':
            thermal_routing_matrix[room_index, channel_index] = -1.0
            
    return thermal_routing_matrix


def calculate_channel_cop(
    terminal: ZoneTerminal,
    mode: Literal['heating', 'cooling'],
    supply_temperature: float | None,
    ambient_temperature: float,
) -> float:
    plant: PlantSystem | None = None
    if mode == 'heating':
        if terminal.heating_source is not None:
            plant = terminal.heating_source
        elif terminal.air_loop is not None and terminal.air_loop.heating_source is not None:
            plant = terminal.air_loop.heating_source
    elif mode == 'cooling':
        if terminal.cooling_source is not None:
            plant = terminal.cooling_source
        elif terminal.air_loop is not None and terminal.air_loop.cooling_source is not None:
            plant = terminal.air_loop.cooling_source

    if plant is not None:
        if plant.efficiency is None or plant.efficiency <= 0.0:
            raise Uninitialised(f"PlantSystem {plant.name} missing valid efficiency")

        match plant.plant_type:
            case 'Boiler':
                if mode == 'cooling':
                    raise Uninitialised(f"Boiler {plant.name} cannot be used for cooling")
                return plant.efficiency

            case 'HeatPump':
                if plant.design_supply_temp is None:
                    raise Uninitialised(f"HeatPump {plant.name} missing design_supply_temp")

                operating_supply_temperature: float
                if supply_temperature is not None:
                    operating_supply_temperature = supply_temperature
                else:
                    operating_supply_temperature = plant.design_supply_temp

                supply_temperature_kelvin = operating_supply_temperature + absolute_zero
                ambient_temperature_kelvin = ambient_temperature + absolute_zero
                design_supply_temperature_kelvin = plant.design_supply_temp + absolute_zero

                if mode == 'heating':
                    temperature_difference = max(supply_temperature_kelvin - ambient_temperature_kelvin, minimum_temperature_difference_kelvin)
                    carnot_ideal_cop = supply_temperature_kelvin / temperature_difference
                    rated_ambient_kelvin = standard_rating_ambient_temperature_heating + absolute_zero
                    design_carnot_ideal = design_supply_temperature_kelvin / max(design_supply_temperature_kelvin - rated_ambient_kelvin, minimum_temperature_difference_kelvin)
                    carnot_efficiency_factor = plant.efficiency / design_carnot_ideal
                    return float(np.clip(carnot_efficiency_factor * carnot_ideal_cop, electric_resistance_coefficient_of_performance, maximum_coefficient_of_performance))
                else:
                    temperature_difference = max(ambient_temperature_kelvin - supply_temperature_kelvin, minimum_temperature_difference_kelvin)
                    carnot_ideal_cop = supply_temperature_kelvin / temperature_difference
                    rated_ambient_kelvin = standard_rating_ambient_temperature_cooling + absolute_zero
                    design_carnot_ideal = design_supply_temperature_kelvin / max(rated_ambient_kelvin - design_supply_temperature_kelvin, minimum_temperature_difference_kelvin)
                    carnot_efficiency_factor = plant.efficiency / design_carnot_ideal
                    return float(np.clip(carnot_efficiency_factor * carnot_ideal_cop, electric_resistance_coefficient_of_performance, maximum_coefficient_of_performance))

            case 'Chiller':
                if mode == 'heating':
                    raise Uninitialised(f"Chiller {plant.name} cannot be used for heating")

                if plant.design_supply_temp is None:
                    raise Uninitialised(f"Chiller {plant.name} missing design_supply_temp")

                operating_supply_temperature: float
                if supply_temperature is not None:
                    operating_supply_temperature = supply_temperature
                else:
                    operating_supply_temperature = plant.design_supply_temp

                supply_temperature_kelvin = operating_supply_temperature + absolute_zero
                ambient_temperature_kelvin = ambient_temperature + absolute_zero
                design_supply_temperature_kelvin = plant.design_supply_temp + absolute_zero

                temperature_difference = max(ambient_temperature_kelvin - supply_temperature_kelvin, minimum_temperature_difference_kelvin)
                carnot_ideal_cop = supply_temperature_kelvin / temperature_difference
                rated_ambient_kelvin = standard_rating_ambient_temperature_cooling + absolute_zero
                design_carnot_ideal = design_supply_temperature_kelvin / max(rated_ambient_kelvin - design_supply_temperature_kelvin, minimum_temperature_difference_kelvin)
                carnot_efficiency_factor = plant.efficiency / design_carnot_ideal
                return float(np.clip(carnot_efficiency_factor * carnot_ideal_cop, electric_resistance_coefficient_of_performance, maximum_coefficient_of_performance))

            case 'CoolingTower':
                return plant.efficiency

            case _:
                raise Uninitialised(f"PlantSystem {plant.name} has invalid plant_type {plant.plant_type}")

    match terminal.terminal_type:
        case 'PTAC':
            if mode == 'heating':
                return electric_resistance_coefficient_of_performance
            else:
                if terminal.efficiency is None or terminal.efficiency <= 0.0:
                    raise Uninitialised(f"ZoneTerminal {terminal.name} missing valid efficiency")
                if terminal.design_supply_temp is None:
                    raise Uninitialised(f"ZoneTerminal {terminal.name} missing design_supply_temp")

                operating_supply_temperature: float
                if supply_temperature is not None:
                    operating_supply_temperature = supply_temperature
                else:
                    operating_supply_temperature = terminal.design_supply_temp

                supply_temperature_kelvin = operating_supply_temperature + absolute_zero
                ambient_temperature_kelvin = ambient_temperature + absolute_zero
                design_supply_temperature_kelvin = terminal.design_supply_temp + absolute_zero

                temperature_difference = max(ambient_temperature_kelvin - supply_temperature_kelvin, minimum_temperature_difference_kelvin)
                carnot_ideal_cop = supply_temperature_kelvin / temperature_difference
                rated_ambient_kelvin = standard_rating_ambient_temperature_cooling + absolute_zero
                design_carnot_ideal = design_supply_temperature_kelvin / max(rated_ambient_kelvin - design_supply_temperature_kelvin, minimum_temperature_difference_kelvin)
                carnot_efficiency_factor = terminal.efficiency / design_carnot_ideal
                return float(np.clip(carnot_efficiency_factor * carnot_ideal_cop, electric_resistance_coefficient_of_performance, maximum_coefficient_of_performance))

        case 'SplitAC':
            if terminal.efficiency is None or terminal.efficiency <= 0.0:
                raise Uninitialised(f"ZoneTerminal {terminal.name} missing valid efficiency")
            if terminal.design_supply_temp is None:
                raise Uninitialised(f"ZoneTerminal {terminal.name} missing design_supply_temp")

            operating_supply_temperature: float
            if supply_temperature is not None:
                operating_supply_temperature = supply_temperature
            else:
                operating_supply_temperature = terminal.design_supply_temp

            supply_temperature_kelvin = operating_supply_temperature + absolute_zero
            ambient_temperature_kelvin = ambient_temperature + absolute_zero
            design_supply_temperature_kelvin = terminal.design_supply_temp + absolute_zero

            if mode == 'cooling':
                temperature_difference = max(ambient_temperature_kelvin - supply_temperature_kelvin, minimum_temperature_difference_kelvin)
                carnot_ideal_cop = supply_temperature_kelvin / temperature_difference
                rated_ambient_kelvin = standard_rating_ambient_temperature_cooling + absolute_zero
                design_carnot_ideal = design_supply_temperature_kelvin / max(rated_ambient_kelvin - design_supply_temperature_kelvin, minimum_temperature_difference_kelvin)
                carnot_efficiency_factor = terminal.efficiency / design_carnot_ideal
                return float(np.clip(carnot_efficiency_factor * carnot_ideal_cop, electric_resistance_coefficient_of_performance, maximum_coefficient_of_performance))
            else:
                temperature_difference = max(supply_temperature_kelvin - ambient_temperature_kelvin, minimum_temperature_difference_kelvin)
                carnot_ideal_cop = supply_temperature_kelvin / temperature_difference
                rated_ambient_kelvin = standard_rating_ambient_temperature_heating + absolute_zero
                design_carnot_ideal = design_supply_temperature_kelvin / max(design_supply_temperature_kelvin - rated_ambient_kelvin, minimum_temperature_difference_kelvin)
                carnot_efficiency_factor = terminal.efficiency / design_carnot_ideal
                return float(np.clip(carnot_efficiency_factor * carnot_ideal_cop, electric_resistance_coefficient_of_performance, maximum_coefficient_of_performance))

        case 'VAV' | 'CAV':
            if mode == 'heating':
                return electric_resistance_coefficient_of_performance
            raise Uninitialised(f"ZoneTerminal {terminal.name} missing cooling plant source")

        case _:
            raise Uninitialised(f"ZoneTerminal {terminal.name} has no source for {mode}")


def control_matrix(
    input_data: dict[tuple[ZoneTerminal, Literal['heating', 'cooling']], float | None],
    ambient_temperature: float,
) -> NDArray[np.float64]:
    actuator_channels = list(input_data.keys())
    thermal_routing_matrix = B_thermal(actuator_channels)
    coefficients_of_performance = np.zeros(len(actuator_channels), dtype=np.float64)

    for channel_index, (channel, supply_temperature) in enumerate(input_data.items()):
        terminal, mode = channel
        coefficients_of_performance[channel_index] = calculate_channel_cop(
            terminal=terminal,
            mode=mode,
            supply_temperature=supply_temperature,
            ambient_temperature=ambient_temperature,
        )

    actuation_matrix = thermal_routing_matrix * coefficients_of_performance
    return actuation_matrix