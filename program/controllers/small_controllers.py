from PyQt6.QtCore import Qt
from ..utils import LinkBase


class Folder(LinkBase):
    def __init__(self, link_name, link_idx, linked=None):
        super().__init__(link_name=link_name, link_idx=link_idx, obj_type='folder', linked=linked)


class TreeRoles:
    """Явное перечисление ролей для хранения данных в элементах дерева (чтобы избежать UserRole + N)"""
    ObjectData = Qt.ItemDataRole.UserRole + 1  # Ссылка на объект бизнес-логики (Folder или GalleryWindow)
    MdiSubWindow = Qt.ItemDataRole.UserRole + 2  # Ссылка на контейнер QMdiSubWindow