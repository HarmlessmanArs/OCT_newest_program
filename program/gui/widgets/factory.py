from PyQt6.QtWidgets import QLabel
from .base_widget import BaseProjectWidget
from .widgets_classes import (
GalleryWidget, TableWidget, GraphWidget, RoiWidget, MuTWidget, BoundariesWidget, IntensityWidget
)


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