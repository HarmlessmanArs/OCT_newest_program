from dataclasses import dataclass

@dataclass(frozen=True)
class ProjectConstants:
    colourmap = {
        0: (0, 0, 255),
        1: (0, 255, 0),
        2: (255, 0, 0),
        3: (0, 255, 255),
        4: (255, 0, 255)
    }