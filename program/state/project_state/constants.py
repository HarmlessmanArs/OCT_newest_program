from dataclasses import dataclass


class WidgetTypes:
    """Строгие идентификаторы типов окон для дескрипторов"""
    FOLDER = "folder"
    GALLERY = "gallery"
    GRAPH = "graph"
    TABLE = "table"
    ROI = "roi"
    BOUNDARIES = "boundaries"
    MU_T = "imaging_mu_t"
    AVERAGE_INTENSITY = "imaging_av_int"


@dataclass(frozen=True)
class ProjectConstants:
    colourmap = {
        0: (0, 0, 255),
        1: (0, 255, 0),
        2: (255, 0, 0),
        3: (0, 255, 255),
        4: (255, 0, 255)
    }