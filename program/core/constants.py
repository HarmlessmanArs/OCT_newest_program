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


class ProjectConstants:
    """Глобальные константы проекта"""

    # Цвета границ в формате BGR (Blue, Green, Red) для OpenCV
    colourmap = {
        0: (0, 0, 255),  # Красный
        1: (0, 255, 0),  # Зеленый
        2: (255, 0, 0),  # Синий
        3: (0, 255, 255),  # Желтый (Cyan)
        4: (255, 0, 255)  # Пурпурный (Magenta)
    }