from __future__ import annotations
from typing import Literal, Any
import math

from typing import TYPE_CHECKING
from diagnosis import Issue
if TYPE_CHECKING:
    from building_modelling import BIM_Node

class ValueSanityIssue(Issue):
    def __init__(self,
                 node: BIM_Node,
                 explainer: str,
                 variable_name: str,
                 acceptable_range:tuple[float,float],
                 category: Literal['Auto-Fix','User-Choice','Fatal']|None = None,):
        super().__init__(node, explainer, variable_name, category)
        
        self.variable_name: str = variable_name
        self.variable_value: Any = getattr(node,variable_name)
        self.acceptable_range: tuple[float,float] = acceptable_range
        self.explainer = f' The value of {self.variable_value} does not make sense for {self.variable_name} of {self.node.name}. \n Value must be between {acceptable_range[0]} and {acceptable_range[1]}.'
        pass
    
    
class MissingValueIssue(Issue):
    def __init__(self,
                 node: BIM_Node,
                 explainer: str,
                 variable_name: str,
                 category: Literal['Auto-Fix','User-Choice','Fatal']|None = None,):
        super().__init__(node, explainer, variable_name, category)
        
        self.variable_name = variable_name
        self.explainer = f'The {self.variable_name} property is missing on {self.node.name}.'
        pass


class MissingEdgeIssue(Issue):
    def __init__(self,
                 node: BIM_Node,
                 explainer: str,
                 variable_name: str,
                 category: Literal['Auto-Fix','User-Choice','Fatal']|None = None,):
        super().__init__(node, explainer, variable_name, category)
        
        self.variable_name = variable_name
        self.explainer = f'Some object for {self.variable_name} is expected on {self.node.name}. We found few options: '
        pass
