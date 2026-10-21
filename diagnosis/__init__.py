from building_modelling import BIM_Node

from typing import Literal, Any, get_type_hints, get_origin, get_args, Union

class Issue:
    def __init__(self,
                 node: BIM_Node,
                 explainer: str, # Explaining general issue
                 variable_name: str,
                 category: Literal['Auto-Fix','User-Choice','Fatal']|None = None,
                 description: str|None = None, # Describing solutions for later
                 ):
        self.node: BIM_Node = node
        self.explainer: str = explainer
        self.variable_name: str = variable_name
        self.description: str|None= description
        self.category: Literal['Auto-Fix','User-Choice','Fatal']|None = category
        
        self.proposed_solution: list[Solution] = list()
        pass
    
    def __str__(self) -> str:
        return f"[{self.category}] {self.node.__class__.__name__} '{self.node.name}': {self.explainer}"
    
class Mutation:
    def __init__(self,
                 node: BIM_Node,
                 variable_name: str,
                 new_value: Any,
                 operation: Literal['Set','Append'] = 'Set'):
        self.node: BIM_Node = node
        self.variable_name: str = variable_name
        self.new_value: Any = new_value
        self.old_value: Any = getattr(node,variable_name)
        self.operation: Literal['Set','Append'] = operation
        pass

class DataSwap:
    def __init__(self,
                 node: BIM_Node,
                 lookup_type: Literal['constructions','materials','room_loads','schedules','hvac_equipment','hvac_templates']):
        self.node: BIM_Node = node
        self.lookup_type: Literal['constructions','materials','room_loads','schedules','hvac_equipment','hvac_templates'] = lookup_type
        pass
    
    def __str__(self) -> str:
        return str(self.node.name) if self.node.name else self.lookup_type
    
    def resolve(self, user_selection: str) -> list[Mutation]:
        if self.lookup_type == 'hvac_templates':
            from building_modelling.topology import Room
            if not isinstance(self.node, Room):
                raise ValueError("HVAC templates can only be applied to Room nodes.")
            from repair.resolver import unpack_hvac_template
            return unpack_hvac_template(user_selection, self.node)
            
        from repair.resolver import node_packer
        template_node = node_packer(self.lookup_type, user_selection)
        if not template_node:
            raise ValueError(f"Could not find '{user_selection}' in {self.lookup_type}.csv")

        mutations: list[Mutation] = []
        for var_name, template_val in vars(template_node).items():
            if isinstance(template_val, list) and len(template_val) == 0:
                continue
                
            if template_val is not None and template_val != "":
                mutations.append(Mutation(
                    node=self.node,
                    variable_name=var_name,
                    new_value=template_val,
                    operation='Set'
                ))
                
        return mutations

class Form:
    def __init__(self,
                 node: BIM_Node,
                 variable_name: str,
                 ):
        self.node: BIM_Node = node
        self.variable_name: str = variable_name
        hints = get_type_hints(node.__class__)
        if variable_name not in hints:
            try:
                hints = get_type_hints(node.__init__)
            except Exception:
                pass
        self.datatype: Any = hints.get(variable_name)
    
    def __str__(self) -> str:
        return f'node: {self.node}, variable_name: {self.variable_name}'
    
    def resolve(self,
                value: Any,
                operation: Literal['Set','Append'] = 'Set') -> Mutation:
        target_type = self.datatype
        if target_type is not None:
            origin = get_origin(target_type)
            if origin is Union or str(origin) == "<class 'types.UnionType'>":
                non_none = [a for a in get_args(target_type) if a is not type(None)]
                if non_none:
                    target_type = non_none[0]
                
        coerced = value
        try:
            if target_type is float:
                coerced = float(value)
            elif target_type is int:
                coerced = int(value)
            elif target_type is bool:
                if isinstance(value, str):
                    coerced = value.lower() in ("true", "1", "yes")
                else:
                    coerced = bool(value)
            elif target_type is str:
                coerced = str(value)
            elif target_type is None and isinstance(value, str):
                try:
                    coerced = int(value)
                except ValueError:
                    try:
                        coerced = float(value)
                    except ValueError:
                        coerced = value
        except (ValueError, TypeError) as e:
            raise TypeError(f"Form cannot be resolved with value '{value}' of type '{type(value).__name__}'. Requires {self.datatype}") from e

        return Mutation(node=self.node,
                        variable_name=self.variable_name,
                        new_value=coerced,
                        operation=operation)

def resolve_form(form: Form, user_input: Any, operation: Literal['Set', 'Append'] = 'Set') -> Mutation:
    return form.resolve(user_input, operation=operation)

def resolve_dataswap(dataswap: DataSwap, user_choice: str) -> list[Mutation]:
    return dataswap.resolve(user_choice)

class Solution:
    def __init__(self,
                 mutations: list[Mutation|DataSwap|Form],
                 description: str|None = None,):
        self.description: str|None = description
        self.mutations: list[Mutation|DataSwap|Form] = mutations
        pass


class Fatality(Issue):
    def __init__(self,
                 issue: Issue,
                 description: str):
        self.__dict__.update(issue.__dict__)
        self.description = description
        pass

class UnresolvedPromiseException(Exception):
    pass

def apply_changes(changes: Mutation | Solution) -> list[str]:
    logs = []
    if isinstance(changes, Mutation):
        if changes.operation == 'Set':
            val = changes.new_value
            if changes.variable_name == 'weather_file' and isinstance(val, str) and val.startswith(('http://', 'https://')):
                from weather import download_weather_file_from_url
                val = str(download_weather_file_from_url(val))
            setattr(changes.node, changes.variable_name, val)
            logs.append(f"Set '{changes.variable_name}' on {changes.node.__class__.__name__} '{changes.node.name}' to '{val}'")
        elif changes.operation == 'Append':
            target_list:list[Any] = getattr(changes.node, changes.variable_name)
            target_list.append(changes.new_value)
            val_str = getattr(changes.new_value, 'name', str(changes.new_value))
            logs.append(f"Appended '{val_str}' to '{changes.variable_name}' on {changes.node.__class__.__name__} '{changes.node.name}'")
        return logs
    elif isinstance(changes, Solution):
        for mutation in changes.mutations:
            if isinstance(mutation, Mutation):
                logs.extend(apply_changes(changes=mutation))
            else:
                raise UnresolvedPromiseException(f'Unresolved Dataswap/Form for {mutation} present in Solution class.')
        return logs
    return logs