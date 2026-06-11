import numpy as np


class GalleryStateManager:
    def __init__(self, project_state):
        """
        Менеджер под-состояния галереи.
        Принимает ссылку на корневой ProjectState.
        """
        self._state = project_state

    def add_original_image(self, datablock_uuid: str, img_uuid: str, file_name: str, img_array: np.ndarray):
        """
        Записывает бинарный массив изображения в датаблок.
        """
        datablock_uuid = self._state.clean_uuid(datablock_uuid)
        img_uuid = self._state.clean_uuid(img_uuid)

        if not datablock_uuid or not img_uuid:
            return

        # Гарантируем, что датаблок существует (используем твой метод)
        self._state.add_datablock(datablock_uuid)
        datablock = self._state.get_datablock(datablock_uuid)

        # Безопасно сохраняем данные согласно SAVE.md
        original_images = datablock.setdefault("original_images", {})

        original_images[img_uuid] = {
            "name": file_name,
            "data": img_array  # Массив NumPy. Твой Writer сам превратит его в Zarr!
        }

        self._state.set_modified(True)

    def get_original_images(self, datablock_uuid: str) -> dict:
        """Возвращает словарь всех изображений для конкретного датаблока."""
        datablock = self._state.get_datablock(datablock_uuid)
        original_images = datablock.get("original_images", {})

        # Гарантируем, что Галерея получит словарь с чистыми строковыми ключами,
        # даже если утилита восстановления превратила их в QUuid
        clean_images = {}
        for img_key, img_data in original_images.items():
            clean_key = self._state.clean_uuid(img_key)
            clean_images[clean_key] = img_data

        return clean_images