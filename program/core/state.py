# program/core/state.py
from dataclasses import dataclass, field
from typing import Dict, Any
import uuid


@dataclass
class ProjectNode:
    """Узел в дереве проекта (Папка, Галерея, Изображение, Таблица)"""
    uid: str
    name: str
    node_type: str  # 'folder', 'gallery', 'image', 'table', 'graph'
    parent_uid: str | None = None
    data: Any = None  # Сюда будем класть numpy-массивы или метаданные
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProjectState:
    """Единый источник правды (Single Source of Truth)"""

    def __init__(self):
        self.is_modified = False
        self.filepath = None
        self.nodes: Dict[str, ProjectNode] = {}
        self.active_mdi_windows: Dict[str, Any] = {}  # UUID узла -> Дескриптор окна

    def reset(self):
        self.is_modified = False
        self.filepath = None
        self.nodes.clear()
        self.active_mdi_windows.clear()

    def add_node(self, name: str, node_type: str, parent_uid: str = None) -> ProjectNode:
        uid = str(uuid.uuid4())
        node = ProjectNode(uid=uid, name=name, node_type=node_type, parent_uid=parent_uid)
        self.nodes[uid] = node
        self.is_modified = True
        return node

    def remove_node(self, uid: str):
        if uid in self.nodes:
            del self.nodes[uid]
            self.is_modified = True


# Глобальное состояние
state = ProjectState()