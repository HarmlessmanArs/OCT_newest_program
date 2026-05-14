from dataclasses import dataclass, field
from typing import Set, List
import numpy as np


@dataclass(frozen=False)
class GalleryState:
    chosen_indices: Set = field(default_factory=set)
    image_items: List = field(default_factory=list)
    current_image: np.ndarray | None = None
    last_selected: int | None = None