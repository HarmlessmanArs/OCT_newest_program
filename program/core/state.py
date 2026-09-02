# program/core/state.py
import uuid
import re
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
        """Полная очистка при создании нового проекта и генерация стартовой папки"""
        self.nodes.clear()
        self.filepath = "[New Project]"
        self.active_widget_uid = None

        # Трубим в шину, что проект обнулился (TreeController очистит старые визуальные элементы)
        bus.project_created.emit()

        # Пункт 4: Создаем папку по умолчанию. Твой метод add_node сам сгенерирует UID
        # и отправит сигнал node_added, благодаря чему папка появится в интерфейсе
        self.add_node(name="Dataset 1", node_type="folder")

        # Так как это чистый стартовый проект, сбрасываем статус "изменен" (убираем [*])
        self.set_modified(False)

    def set_modified(self, modified: bool = True):
        """Помечает проект как измененный и уведомляет интерфейс"""
        if self.is_modified != modified:
            self.is_modified = modified
            bus.project_modified.emit(modified)

    def get_children(self, parent_uid: str) -> List[ProjectNode]:
        """Возвращает всех потомков конкретной папки"""
        return [node for node in self.nodes.values() if node.parent_uid == parent_uid]

    def _generate_unique_name(self, base_name: str) -> str:
        """
        Глобальная уникальность имени.
        Ищет свободный номер по всему проекту. 'Dataset' -> 'Dataset 1' -> 'Dataset 2'
        """
        existing_names = {node.name for node in self.nodes.values()}

        # Отделяем текстовую базу от возможного номера на конце (например, "Dataset" от "1")
        match = re.match(r"^(.*?)(\s+\d+)?$", base_name)
        prefix = match.group(1).strip() if match else base_name

        counter = 1
        while True:
            new_name = f"{prefix} {counter}"
            if new_name not in existing_names:
                return new_name
            counter += 1

    def add_node(self, name: str, node_type: str, parent_uid: Optional[str] = None) -> ProjectNode:
        """Создает новый узел (папку, галерею, расчет ROI)"""
        uid = str(uuid.uuid4())

        # Теперь мы передаем только желаемое имя, счетчик подберется глобально
        safe_name = self._generate_unique_name(name)

        new_node = ProjectNode(
            uid=uid,
            name=safe_name,
            node_type=node_type,
            parent_uid=parent_uid
        )
        self.nodes[uid] = new_node
        self.set_modified(True)

        bus.node_added.emit(uid)
        return new_node

    def rename_node(self, uid: str, new_name: str):
        """Безопасное переименование с глобальной проверкой на дубликаты"""
        if uid not in self.nodes:
            return

        node = self.nodes[uid]
        # Используем существующий механизм защиты от дубликатов
        safe_name = self._generate_unique_name(new_name)

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
        safe_name = self._generate_unique_name(node.name)

        node.parent_uid = new_parent_uid

        if node.name != safe_name:
            node.name = safe_name
            bus.node_renamed.emit(uid, safe_name)

        self.set_modified(True)
        # Сигнал для дерева интерфейса, чтобы оно перерисовалось
        bus.node_moved.emit(uid, new_parent_uid)


# Создаем глобальный экземпляр состояния
state = ProjectState()