from PyQt6.QtCore import Qt
from ..utils import LinkBase


class Folder(LinkBase):
    def __init__(self, link_name, link_idx, linked=None):
        super().__init__(link_name=link_name, link_idx=link_idx, obj_type='folder', linked=linked)


class TreeRoles:
    """Явное перечисление ролей для хранения данных в элементах дерева (чтобы избежать UserRole + N)"""
    ObjectData = Qt.ItemDataRole.UserRole + 1  # Ссылка на объект бизнес-логики (Folder или GalleryWindow)
    MdiSubWindow = Qt.ItemDataRole.UserRole + 2  # Ссылка на контейнер QMdiSubWindow


class UuidController:
    @staticmethod
    def clean_uuid(val) -> str:
        """
        Извлекает чистую строку UUID в формате {xxxx-xxxx...} из любых объектов.
        Гарантирует 100% совпадение ключей.
        """
        if not val:
            return ""

        # Если это PyQt-объект QUuid, используем его родной метод
        if hasattr(val, 'toString'):
            return val.toString()

        val_str = str(val)

        # Если это замусоренная строка (например, repr от QUuid), вытаскиваем суть
        import re
        match = re.search(r'\{[0-9a-fA-F\-]{36}\}', val_str)
        if match:
            return match.group(0)

        return val_str