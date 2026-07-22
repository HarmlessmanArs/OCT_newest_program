# program/core/state.py
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from .events import bus


@dataclass
class ProjectNode:
    """Универсальный контейнер для любой сущности проекта"""
    uid: str
    name: str
    node_type: str  # 'folder', 'gallery', 'table', 'roi', 'boundaries', 'mu_t' и т.д.
    parent_uid: Optional[str] = None
    data: Any = None  # Здесь будут лежать numpy-массивы или pandas-таблицы
    metadata: Dict[str, Any] = field(default_factory=dict)  # Различные настройки


class ProjectState:
    """Единый источник правды. Хранит всю структуру проекта."""

    def __init__(self):
        self.nodes: Dict[str, ProjectNode] = {}
        self.is_modified: bool = False
        self.filepath: Optional[str] = None
        self.active_widget_uid: Optional[str] = None

    def reset(self):
        """Полная очистка при создании нового проекта"""
        self.nodes.clear()
        self.filepath = None
        self.active_widget_uid = None
        self.set_modified(False)

    def set_modified(self, modified: bool = True):
        """Помечает проект как измененный и уведомляет интерфейс"""
        if self.is_modified != modified:
            self.is_modified = modified
            bus.project_modified.emit(modified)

    def get_children(self, parent_uid: str) -> List[ProjectNode]:
        """Возвращает всех потомков конкретной папки"""
        return [node for node in self.nodes.values() if node.parent_uid == parent_uid]

    def _generate_unique_name(self, base_name: str, parent_uid: Optional[str]) -> str:
        """
        Решение проблемы дубликатов:
        Если в папке уже есть 'Gallery 1', вернет 'Gallery 1 (1)'
        """
        existing_names = {
            node.name for node in self.nodes.values()
            if node.parent_uid == parent_uid
        }

        if base_name not in existing_names:
            return base_name

        counter = 1
        new_name = f"{base_name} ({counter})"
        while new_name in existing_names:
            counter += 1
            new_name = f"{base_name} ({counter})"

        return new_name

    def add_node(self, name: str, node_type: str, parent_uid: Optional[str] = None) -> ProjectNode:
        """Создает новый узел (папку, галерею, расчет ROI)"""
        uid = str(uuid.uuid4())

        # Гарантируем уникальность имени в рамках родителя
        safe_name = self._generate_unique_name(name, parent_uid)

        new_node = ProjectNode(
            uid=uid,
            name=safe_name,
            node_type=node_type,
            parent_uid=parent_uid
        )
        self.nodes[uid] = new_node
        self.set_modified(True)

        # Трубим на всю программу, что данные добавились (Дерево услышит и обновится)
        bus.node_added.emit(uid)
        return new_node

    def remove_node(self, uid: str):
        """Удаляет узел и КАСКАДНО удаляет всех его детей (виджеты внутри папки)"""
        if uid not in self.nodes:
            return

        # Сначала рекурсивно удаляем всех детей
        children = self.get_children(uid)
        for child in children:
            self.remove_node(child.uid)

        # Затем удаляем сам узел
        del self.nodes[uid]
        self.set_modified(True)

        # Окна и Дерево услышат это и самоуничтожатся (Решает проблему окон-призраков)
        bus.node_removed.emit(uid)

    def rename_node(self, uid: str, new_name: str):
        """Безопасное переименование"""
        if uid not in self.nodes:
            return

        node = self.nodes[uid]
        safe_name = self._generate_unique_name(new_name, node.parent_uid)

        if node.name != safe_name:
            node.name = safe_name
            self.set_modified(True)
            bus.node_renamed.emit(uid, safe_name)

    def get_node(self, uid: str) -> Optional[ProjectNode]:
        """Безопасное получение узла по UID"""
        return self.nodes.get(uid)

    def get_nodes_by_type(self, parent_uid: str, node_type: str) -> List[ProjectNode]:
        """Возвращает все узлы определенного типа внутри родителя"""
        return [
            node for node in self.nodes.values()
            if node.parent_uid == parent_uid and node.node_type == node_type
        ]

    def move_node(self, uid: str, new_parent_uid: str):
        """Перемещение узла в другую папку с защитой конфликта имен"""
        node = self.get_node(uid)
        if not node or node.parent_uid == new_parent_uid:
            return

        # Проверяем, нет ли в новой папке файла с таким же именем
        safe_name = self._generate_unique_name(node.name, new_parent_uid)

        node.parent_uid = new_parent_uid

        if node.name != safe_name:
            node.name = safe_name
            bus.node_renamed.emit(uid, safe_name)

        self.set_modified(True)
        # Сигнал для дерева интерфейса, чтобы оно перерисовалось
        bus.node_moved.emit(uid, new_parent_uid)


# Создаем глобальный экземпляр состояния
state = ProjectState()