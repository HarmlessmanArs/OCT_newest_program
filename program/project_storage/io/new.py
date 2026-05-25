from datetime import datetime

def create_empty_project(app_version: str = "1.0") -> dict:
    """
    Генерирует базовый, дефолтный слепок (snapshot) проекта.
    Вызывается при нажатии 'Файл -> Новый проект' или при холодном старте программы.
    """
    return {
        'project_meta': {
            'created_at': datetime.now().isoformat(),
            'last_modified': datetime.now().isoformat(),
            'app_version': app_version,
            'description': 'Новый проект'
        },
        'tree_structure': {
            # Дерево QTreeWidget изначально пустое
        },
        'blocks': {}
        # Поскольку блоков нет, нам не нужно создавать пустые категории
        # (original_images, boundaries_images и т.д.). Они будут созданы
        # динамически при добавлении первого датаблока.
    }