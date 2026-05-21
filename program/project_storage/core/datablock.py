from dataclasses import dataclass
from typing import Any, Dict
from .handles import DataHandle


@dataclass
class DataBlock:
    name: str
    type: str
    handle: DataHandle
    meta: Dict[str, Any]