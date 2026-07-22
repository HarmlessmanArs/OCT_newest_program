from program.core.state import state

# Имитируем создание папки
folder = state.add_node("Dataset 1", "folder")

# Создаем две галереи с одинаковыми именами (имитация бага пользователя)
gal1 = state.add_node("Gallery", "gallery", parent_uid=folder.uid)
gal2 = state.add_node("Gallery", "gallery", parent_uid=folder.uid)

print(f"Имя первой: {gal1.name}") # Выведет: Gallery
print(f"Имя второй: {gal2.name}") # Выведет: Gallery (1)  <-- Баг №3 устранен!

# Проверяем каскадное удаление
print(f"Всего узлов до удаления: {len(state.nodes)}") # 3 (папка + 2 галереи)
state.remove_node(folder.uid)
print(f"Всего узлов после: {len(state.nodes)}") # 0 (папка удалилась, потянув за собой галереи)