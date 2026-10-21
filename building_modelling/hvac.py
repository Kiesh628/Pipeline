from __future__ import annotations
from typing import TYPE_CHECKING, Literal
from building_modelling import BIM_Node

if TYPE_CHECKING:
    from building_modelling.topology import Room

from diagnosis.issues import *

FuelType = Literal["Electricity", "NaturalGas", "Propane", "FuelOilNo1", "DistrictCooling", "DistrictHeating"]
PlantType = Literal["Boiler", "Chiller", "HeatPump", "CoolingTower"]
TerminalType = Literal["VAV", "CAV", "Radiator", "FCU", "SplitAC", "PTAC"]

class PlantSystem(BIM_Node):
    indexing: list['PlantSystem'] = list()

    def __init__(self, guid: str|None = None, name: str|None = None,
                 plant_type: PlantType|None = None,
                 min_supply_temp: float|None = None,
                 max_supply_temp: float|None = None):
        super().__init__(guid, name)
        PlantSystem.indexing.append(self)
        self.plant_type: PlantType|None = plant_type
        
        self.capacity: float|None = None # Watts
        self.pump_flow_rate: float|None = None # m3/s
        
        self.fuel_type: FuelType|None = None
        self.efficiency: float|None = None
        self.min_supply_temp: float|None = min_supply_temp # °C
        self.max_supply_temp: float|None = max_supply_temp # °C
        self.pump_head_pressure: float|None = None # Pascals
        
        self.current_power_draw: float|None = None # Watts
        
        self.served_air_loops: list[AirLoop] = list()
        self.served_terminals: list[ZoneTerminal] = list()
        pass

    @property
    def design_supply_temp(self) -> float | None:
        if self.min_supply_temp is not None and self.max_supply_temp is not None:
            return (self.min_supply_temp + self.max_supply_temp) / 2.0
        return self.min_supply_temp if self.min_supply_temp is not None else self.max_supply_temp

    @design_supply_temp.setter
    def design_supply_temp(self, value: float | None):
        if value is not None:
            if self.min_supply_temp is None and self.max_supply_temp is None:
                if self.plant_type == "Chiller":
                    self.min_supply_temp, self.max_supply_temp = 5.5, 11.0
                elif self.plant_type == "HeatPump":
                    self.min_supply_temp, self.max_supply_temp = 30.0, 50.0
                elif self.plant_type == "Boiler":
                    self.min_supply_temp, self.max_supply_temp = 45.0, 82.0
                else:
                    self.min_supply_temp, self.max_supply_temp = value - 5.0, value + 5.0

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
    def verify(self,
               IssueList: list[Issue]):
        
        if not self.guid:
            IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
        if not self.name:
            IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
            
        if not self.plant_type:
            IssueList.append(MissingValueIssue(self, 'Missing plant type (e.g., Boiler, Chiller)', 'plant_type'))
            
        if self.capacity is None:
            IssueList.append(MissingValueIssue(self, 'Missing capacity', 'capacity'))
        elif self.capacity <= 0:
            IssueList.append(ValueSanityIssue(self, 'Invalid capacity (must be > 0 W)', 'capacity', (0.001, float('inf'))))
                
        if self.pump_flow_rate is None:
            IssueList.append(MissingValueIssue(self, 'Missing pump flow rate', 'pump_flow_rate'))
        elif self.pump_flow_rate <= 0:
            IssueList.append(ValueSanityIssue(self, 'Invalid pump flow rate (must be > 0 m3/s)', 'pump_flow_rate', (0.001, float('inf'))))

        if not self.efficiency:
            IssueList.append(MissingValueIssue(self, 'Missing efficiency (COP)', 'efficiency'))
        elif self.efficiency <= 0:
            IssueList.append(ValueSanityIssue(self, 'Invalid efficiency', 'efficiency', (0.001, float('inf'))))
            
        if self.min_supply_temp is None:
            IssueList.append(MissingValueIssue(self, 'Missing min supply temperature', 'min_supply_temp'))
        if self.max_supply_temp is None:
            IssueList.append(MissingValueIssue(self, 'Missing max supply temperature', 'max_supply_temp'))
        if self.min_supply_temp is not None and self.max_supply_temp is not None:
            if self.min_supply_temp >= self.max_supply_temp:
                IssueList.append(ValueSanityIssue(self, f'min_supply_temp ({self.min_supply_temp}°C) must be strictly less than max_supply_temp ({self.max_supply_temp}°C)', 'min_supply_temp', (-50.0, self.max_supply_temp)))
            
        if not self.fuel_type:
            IssueList.append(MissingValueIssue(self, 'Missing fuel type', 'fuel_type'))
            
        if not self.served_air_loops and not self.served_terminals:
            IssueList.append(MissingEdgeIssue(self, 'PlantSystem is not serving any AirLoops or ZoneTerminals. It is disconnected from the building.', 'served_terminals'))
        pass
     
class AirLoop(BIM_Node):
    indexing: list['AirLoop'] = list()

    def __init__(self, guid: str|None = None, name: str|None = None):
        super().__init__(guid, name)
        AirLoop.indexing.append(self)
        self.heating_source: PlantSystem|None = None
        self.cooling_source: PlantSystem|None = None
        self.served_terminals: list[ZoneTerminal] = list()
        
        self.design_air_flow_rate: float|None = None # m3/s
        
        self.design_supply_air_temp_cooling: float|None = None # °C
        self.design_supply_air_temp_heating: float|None = None # °C
        self.fan_efficiency: float|None = None
        self.fan_pressure_rise: float|None = None # Pascals
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
            
        if not self.heating_source and not self.cooling_source:
            IssueList.append(MissingEdgeIssue(self, 'AirLoop has no heating or cooling source attached.', 'cooling_source'))
        else:
            if self.heating_source and self.heating_source.plant_type not in ['Boiler', 'HeatPump']:
                IssueList.append(Issue(self, f"Plant '{self.heating_source.name}' ({self.heating_source.plant_type}) cannot be used as heating_source for AirLoop.", 'heating_source'))
            if self.cooling_source and self.cooling_source.plant_type not in ['Chiller', 'HeatPump']:
                IssueList.append(Issue(self, f"Plant '{self.cooling_source.name}' ({self.cooling_source.plant_type}) cannot be used as cooling_source for AirLoop.", 'cooling_source'))
            
        if not self.served_terminals:
            IssueList.append(MissingEdgeIssue(self, 'AirLoop is not connected to any ZoneTerminals. It serves no rooms.', 'served_terminals'))
            
        if self.design_air_flow_rate is None:
            IssueList.append(MissingValueIssue(self, 'Missing design air flow rate', 'design_air_flow_rate'))
        elif self.design_air_flow_rate <= 0:
            IssueList.append(ValueSanityIssue(self, 'Invalid design air flow rate (must be > 0 m3/s)', 'design_air_flow_rate', (0.001, float('inf'))))
            
        if self.fan_efficiency is None:
            IssueList.append(MissingValueIssue(self, 'Missing fan efficiency', 'fan_efficiency'))
        elif self.fan_efficiency <= 0 or self.fan_efficiency > 1.0:
            IssueList.append(ValueSanityIssue(self, 'Fan efficiency must be between 0.0 and 1.0', 'fan_efficiency', (0.001, 1.0)))
        pass

class ZoneTerminal(BIM_Node):
    indexing: list['ZoneTerminal'] = list()

    def __init__(self, guid: str|None = None, name: str|None = None,
                 terminal_type: TerminalType|None = None,
                 min_supply_temp: float|None = None,
                 max_supply_temp: float|None = None):
        super().__init__(guid, name)
        ZoneTerminal.indexing.append(self)
        self.terminal_type: TerminalType|None = terminal_type
        
        self.room: Room|None = None
        self.air_loop: AirLoop|None = None
        self.heating_source: PlantSystem|None = None
        self.cooling_source: PlantSystem|None = None
        
        self.efficiency: float|None = None
        self.min_supply_temp: float|None = min_supply_temp # °C
        self.max_supply_temp: float|None = max_supply_temp # °C
        
        self.max_air_flow_rate: float|None = None # m3/s
        self.max_water_flow_rate: float|None = None # m3/s
        
        self.parasitic_power: float|None = None # Watts
        pass

    @property
    def design_supply_temp(self) -> float | None:
        if self.min_supply_temp is not None and self.max_supply_temp is not None:
            return (self.min_supply_temp + self.max_supply_temp) / 2.0
        return self.min_supply_temp if self.min_supply_temp is not None else self.max_supply_temp

    @design_supply_temp.setter
    def design_supply_temp(self, value: float | None) -> None:
        if value is not None:
            self.min_supply_temp = value
            self.max_supply_temp = value
        else:
            self.min_supply_temp = None
            self.max_supply_temp = None

    @classmethod
    def clear_indexing(cls):
        cls.indexing.clear()
    
    def verify(self,
               IssueList: list[Issue]):
        if not self.guid:
            IssueList.append(MissingValueIssue(self, 'Missing GUID', 'guid'))
        if not self.name:
            IssueList.append(MissingValueIssue(self, 'Missing name', 'name'))
            
        if not self.room:
                    IssueList.append(MissingEdgeIssue(self, 'ZoneTerminal must be assigned to a Room.', 'room'))
        
        match self.terminal_type:
            case None:
                IssueList.append(MissingValueIssue(self, 'Missing terminal type (e.g., VAV, FCU)', 'terminal_type'))
            case 'VAV'|'CAV':
                if not self.air_loop:
                    IssueList.append(MissingEdgeIssue(self, f'{self.terminal_type} requires an AirLoop connection.', 'air_loop'))
            case 'SplitAC'|'PTAC':
                if self.air_loop:
                    IssueList.append(Issue(self,f'{self.terminal_type} should not have an associated Airloop connection','air_loop'))
                if self.efficiency is None:
                    IssueList.append(MissingValueIssue(self, 'Missing efficiency (COP)', 'efficiency'))
                elif self.efficiency <= 0:
                    IssueList.append(ValueSanityIssue(self, 'Invalid efficiency', 'efficiency', (0.001, float('inf'))))
                if self.min_supply_temp is None:
                    IssueList.append(MissingValueIssue(self, 'Missing min supply temperature', 'min_supply_temp'))
                if self.max_supply_temp is None:
                    IssueList.append(MissingValueIssue(self, 'Missing max supply temperature', 'max_supply_temp'))
                if self.min_supply_temp is not None and self.max_supply_temp is not None:
                    if self.min_supply_temp >= self.max_supply_temp:
                        IssueList.append(ValueSanityIssue(self, f'min_supply_temp ({self.min_supply_temp}°C) must be strictly less than max_supply_temp ({self.max_supply_temp}°C)', 'min_supply_temp', (-50.0, self.max_supply_temp)))
            case 'Radiator':
                if self.air_loop:
                    IssueList.append(Issue(self,f'{self.terminal_type} should not have an associated Airloop connection','air_loop'))
                if not self.heating_source:
                    IssueList.append(MissingEdgeIssue(self,f'{self.terminal_type} required heating source','heating_source'))
                if self.cooling_source:
                    IssueList.append(Issue(self,f'{self.terminal_type} must not have an associated cooling source','cooling_source'))
            case 'FCU':
                if not (self.cooling_source or self.heating_source):
                    IssueList.append(MissingEdgeIssue(self,f'{self.terminal_type} must have either a cooling_source or a heating_source','cooling_source'))
            
        if self.max_air_flow_rate is None and self.max_water_flow_rate is None:
            IssueList.append(MissingValueIssue(self, 'Missing maximum flow rate data (air or water depending on type).', 'max_air_flow_rate'))
        else:
            if self.max_air_flow_rate is not None and self.max_air_flow_rate <= 0:
                IssueList.append(ValueSanityIssue(self, 'Invalid max air flow rate (must be > 0 m3/s)', 'max_air_flow_rate', (0.001, float('inf'))))
            if self.max_water_flow_rate is not None and self.max_water_flow_rate <= 0:
                IssueList.append(ValueSanityIssue(self, 'Invalid max water flow rate (must be > 0 m3/s)', 'max_water_flow_rate', (0.001, float('inf'))))
        pass

class Thermostat(BIM_Node):
    indexing: list['Thermostat'] = list()

    def __init__(self, guid: str|None = None, name: str|None = None, deadband: float = 2.0):
        super().__init__(guid, name)
        Thermostat.indexing.append(self)
        self.room: Room|None = None
        self.controls_terminal: ZoneTerminal|None = None
        
        self.heating_setpoint: float|None = None # °C
        self.cooling_setpoint: float|None = None # °C
        self.deadband: float = deadband # °C minimum gap between heating and cooling
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
            
        if not self.room:
            IssueList.append(MissingEdgeIssue(self, 'Thermostat must be located in a Room.', 'room'))
            
        if not self.controls_terminal:
            IssueList.append(MissingEdgeIssue(self, 'Thermostat must control at least one ZoneTerminal.', 'controls_terminal'))
        elif self.room and self.controls_terminal.room != self.room:
            term_room_name = self.controls_terminal.room.name if self.controls_terminal.room else 'Unknown'
            IssueList.append(Issue(self, f"Thermostat '{self.name}' in room '{self.room.name}' cannot control terminal '{self.controls_terminal.name}' located in '{term_room_name}'.", 'controls_terminal'))
            
        if self.deadband <= 0:
            IssueList.append(ValueSanityIssue(self, 'Deadband must be > 0 °C', 'deadband', (0.1, 10.0)))
            
        if self.heating_setpoint is None and self.cooling_setpoint is None:
            IssueList.append(MissingValueIssue(self, f'Thermostat {self.name} must have at least one setpoint (heating or cooling).', 'cooling_setpoint'))
            
        if self.heating_setpoint is not None and self.cooling_setpoint is not None:
            if self.cooling_setpoint - self.heating_setpoint < self.deadband:
                IssueList.append(ValueSanityIssue(
                    self, 
                    f'Cooling setpoint ({self.cooling_setpoint}°C) must exceed heating setpoint ({self.heating_setpoint}°C) by at least deadband ({self.deadband}°C). This will cause fighting modes.', 
                    'cooling_setpoint', 
                    (self.heating_setpoint + self.deadband, 100.0)
                ))
        pass
