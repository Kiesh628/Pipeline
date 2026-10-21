
class BIM_Node():
    registry: list['BIM_Node'] = []
    
    def __init__(self,
                 guid: str | None = None,
                 name: str | None = None,):
        self.guid: str|None = guid
        self.name: str|None = name
        
        BIM_Node.registry.append(self)
        pass
    
    def verify(self,*args,**kwargs):
        raise NotImplementedError('You shouldnt be verifiying a blank BIM node...')
        
    @classmethod
    def clear_registry(cls):
        cls.registry.clear()
        for sub in cls.__subclasses__():
            clear_fn = getattr(sub, 'clear_indexing', None)
            if callable(clear_fn):
                clear_fn()