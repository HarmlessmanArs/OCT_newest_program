from PyQt6.QtWidgets import QLabel
from .base_widget import BaseProjectWidget

from ..windows.ui_table_window import Ui_Form_table
from ..windows.ui_gallery_window import Ui_Form_gallery
from ..windows.ui_graphic_window import Ui_Form_graph
from ..windows.ui_imaging_mu_t_window import Ui_Form_img_mu_t
from ..windows.ui_imaging_roi_window import Ui_Form_img_roi
from ..windows.ui_imaging_boundaries_window import Ui_Form_img_bound
from ..windows.ui_imaging_av_int_window import Ui_Form_img_av_int


class GalleryWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_gallery()
        self.ui.setupUi(self)

        # Заглушка, пока не импортируешь UI
        from PyQt6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Gallery UI will be here"))


class TableWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_table()
        self.ui.setupUi(self)


class GraphWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_graph()
        self.ui.setupUi(self)


class RoiWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_roi()
        self.ui.setupUi(self)


class BoundariesWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_bound()
        self.ui.setupUi(self)


class IntensityWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_av_int()
        self.ui.setupUi(self)


class MuTWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_mu_t()
        self.ui.setupUi(self)


class WidgetFactory:
    """Определяет, какой интерфейс загрузить в зависимости от типа узла"""

    _registry = {
        'gallery': GalleryWidget,
        'table': TableWidget,
        'graph': GraphWidget,
        'roi': RoiWidget,
        'boundaries': BoundariesWidget,
        'intensity': IntensityWidget,
        'mu_t': MuTWidget
    }

    @classmethod
    def create(cls, node_type: str, uid: str) -> BaseProjectWidget:
        widget_class = cls._registry.get(node_type)
        if widget_class:
            return widget_class(uid)

        # Защитный механизм, если тип еще не реализован
        fallback = BaseProjectWidget(uid)
        from PyQt6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(fallback)
        layout.addWidget(QLabel(f"No UI registered for type: {node_type}"))
        return fallback