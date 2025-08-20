from typing import Any

__version__: str

class Context:
    def __init__(self): ...
    def eval(self, source: str) -> Any: ...

class Undefined:
    def __init__(self): ...
