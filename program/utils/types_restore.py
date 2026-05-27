from pathlib import Path
from PyQt6.QtCore import QUuid


def restore_snapshot_types(obj):
    """
    Рекурсивно восстанавливает типы данных из JSON-совместимых структур.
    """
    if isinstance(obj, dict):
        restored_dict = {}
        for k, v in obj.items():
            # 1. Восстанавливаем QUuid в ключах словарей
            if isinstance(k, str) and k.startswith('{') and k.endswith('}'):
                q_id = QUuid(k)
                key = q_id if not q_id.isNull() else k
            else:
                key = k

            restored_dict[key] = restore_snapshot_types(v)
        return restored_dict

    elif isinstance(obj, list):
        # Если интерфейсу где-то критически важен tuple вместо list,
        # можно завязаться на имя ключа или восстанавливать списки до кортежей точечно.
        return [restore_snapshot_types(item) for item in obj]

    elif isinstance(obj, str):
        # 2. Восстанавливаем QUuid в значениях
        if obj.startswith('{') and obj.endswith('}'):
            q_id = QUuid(obj)
            if not q_id.isNull():
                return q_id

        # 3. Пример: Восстанавливаем Path, если строка выглядит как абсолютный
        # или специфичный для проекта путь (опционально, если нужно в State)
        # if '\\' in obj or '/' in obj:
        #     return Path(obj)

        return obj

    return obj