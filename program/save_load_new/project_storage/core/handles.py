from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class DataHandle:
    path: str              # внутри архива
    loader_type: str       # "npy", "json"
    shape: Optional[Tuple] = None
    dtype: Optional[str] = None