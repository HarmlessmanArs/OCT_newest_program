import json
import numpy as np
from pathlib import Path
from PyQt6.QtCore import QUuid
# Замени на свой реальный путь импорта:
from ..core.state import ProjectNode


class ProjectSerializer:
    """
    Сериализатор для перевода ProjectState в JSON и обратно.
    Идеально работает с датаклассами ProjectNode.
    """

    @classmethod
    def sanitize_for_json(cls, obj):
        """Очистка Python-типов до стандартного JSON."""
        # Если это датакласс ProjectNode — превращаем его в словарь
        if hasattr(obj, '__dataclass_fields__'):
            node_dict = {k: getattr(obj, k) for k in obj.__dataclass_fields__}
            # ВАЖНО: Тяжелые матрицы NumPy (data) мы НЕ пишем в JSON!
            node_dict['data'] = None
            return cls.sanitize_for_json(node_dict)

        elif isinstance(obj, dict):
            return {str(k): cls.sanitize_for_json(v) for k, v in obj.items()}

        elif isinstance(obj, (list, tuple, set)):
            return [cls.sanitize_for_json(item) for item in obj]

        elif isinstance(obj, QUuid):
            return obj.toString()

        elif isinstance(obj, Path):
            return str(obj)

        elif isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)

        elif isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)

        elif isinstance(obj, np.ndarray):
            return "<Heavy Array>"

        else:
            return obj

    @classmethod
    def serialize_state(cls, state) -> str:
        """
        Берет объект ProjectState и делает из него JSON строку.
        """
        snapshot = {
            "filepath": state.filepath,
            "active_widget_uid": state.active_widget_uid,
            "nodes": state.nodes  # Здесь лежат ProjectNode
        }
        clean_snapshot = cls.sanitize_for_json(snapshot)
        return json.dumps(clean_snapshot, indent=4, ensure_ascii=False)

    @classmethod
    def deserialize_to_state(cls, json_str: str, target_state):
        """
        Читает JSON строку и восстанавливает объекты ProjectNode
        прямо внутрь живого ProjectState.
        """
        if not json_str.strip():
            return

        data = json.loads(json_str)

        # Восстанавливаем базовые настройки стейта
        target_state.filepath = data.get("filepath")
        target_state.active_widget_uid = data.get("active_widget_uid")

        # Очищаем старые узлы
        target_state.nodes.clear()

        # Заново собираем объекты ProjectNode из словарей
        nodes_data = data.get("nodes", {})
        for uid, node_dict in nodes_data.items():
            # Распаковываем словарь обратно в живой объект ProjectNode
            # node_dict содержит: uid, name, node_type, parent_uid, metadata
            node = ProjectNode(**node_dict)
            target_state.nodes[uid] = node