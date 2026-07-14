from PyQt6.QtWidgets import QWidget, QMdiSubWindow
from PyQt6.QtCore import QObject
import re


class RuntimeRegistry(QObject):
    """
    Реестр живых UI-объектов программы (Этап 2).
    Связывает строковый UUID из State с реальными экземплярами окон и виджетов в RAM.
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self.win = main_window

        # Хранилища живых ссылок
        self._widgets = {}  # {widget_uuid_str: QWidget}
        self._sub_windows = {}  # {widget_uuid_str: QMdiSubWindow}

    @staticmethod
    def _clean_uuid(val) -> str:
        """
        Извлекает чистую строку UUID в формате {xxxx-xxxx...} из любых объектов.
        Гарантирует 100% совпадение ключей.
        """
        if not val:
            return ""

        if hasattr(val, 'toString'):
            return val.toString()

        val_str = str(val)

        match = re.search(r'\{[0-9a-fA-F\-]{36}\}', val_str)
        if match:
            return match.group(0)

        return val_str

    def register_widget(self, uuid_str: str, widget: QWidget, sub_window: QMdiSubWindow = None):
        """Регистрирует живые компоненты интерфейса и подписывается на их закрытие."""
        uuid_str = self._clean_uuid(uuid_str)
        self._widgets[uuid_str] = widget

        if sub_window:
            self._sub_windows[uuid_str] = sub_window

        # Подключаем автоматическую очистку при закрытии окна пользователем
        if hasattr(widget, 'window_closed'):
            # Защита от двойного подключения
            try:
                widget.window_closed.disconnect(self._on_widget_window_closed)
            except (TypeError, RuntimeError):
                pass
            widget.window_closed.connect(self._on_widget_window_closed)

    def _on_widget_window_closed(self, widget_obj):
        """Внутренний слот, срабатывающий при ручном закрытии окна пользователем."""
        if not hasattr(widget_obj, 'link_idx'):
            return

        uuid_str = self._clean_uuid(widget_obj.link_idx)
        print(f"[REGISTRY AUTO-CLEAN] Окно {uuid_str} закрыто пользователем. Запуск зачистки.")

        # Вызываем единый пайплайн удаления
        self.unregister_and_destroy(uuid_str, unregister_from_state=True)

    def get_widget(self, uuid_str: str) -> QWidget | None:
        return self._widgets.get(self._clean_uuid(uuid_str))

    def get_sub_window(self, uuid_str: str) -> QMdiSubWindow | None:
        return self._sub_windows.get(self._clean_uuid(uuid_str))

    def unregister_and_destroy(self, uuid_str: str, unregister_from_state: bool = False):
        """
        Единый пайплайн удаления (Этап 9).
        Безопасен к "мертвым" C++ объектам. Полностью вычищает следы из RAM и State.
        """
        uuid_str = self._clean_uuid(uuid_str)

        # 1. Безопасно извлекаем MDI контейнер из словаря
        sub = self._sub_windows.pop(uuid_str, None)

        if sub:
            try:
                widget_window = sub.widget()
                if widget_window:
                    if hasattr(widget_window, '_force_close'):
                        widget_window._force_close = True
                    # Отключаем сигнал, чтобы не вызвать рекурсию при закрытии
                    if hasattr(widget_window, 'window_closed'):
                        widget_window.window_closed.disconnect(self._on_widget_window_closed)

                sub.close()
                sub.deleteLater()
            except RuntimeError:
                # C++ объект уже удален силами Qt, игнорируем ошибку взаимодействия
                pass

        # 2. Безопасно удаляем ссылку на сам виджет из реестра
        self._widgets.pop(uuid_str, None)

        # 3. Синхронизируем с ProjectState (КРИТИЧЕСКИЙ ФИКС БАГА С ФАНТОМАМИ + ДЕРЕВОМ)
        if unregister_from_state and hasattr(self.win, 'project_state'):
            try:
                state = self.win.project_state
                if uuid_str in state.widgets:
                    state.widgets.pop(uuid_str, None)

                    # 1. Вызываем физическое удаление строки из QTreeView
                    if hasattr(self.win, 'interface_controller'):
                        self.win.interface_controller.remove_item_from_tree_by_uuid(uuid_str)
                    elif hasattr(self.win, 'hierarchy_controller'):
                        self.win.hierarchy_controller.remove_item_from_tree_by_uuid(uuid_str)

                    # 2. Выставляем флаг изменения проекта
                    state.set_modified(True)
                    print(f"[REGISTRY State SYNC] UUID {uuid_str} удален из State и из QTreeView.")
            except Exception as e:
                print(f"[REGISTRY ERROR] Ошибка синхронизации со State при удалении: {e}")

    def clear_all(self):
        """Полная зачистка интерфейса перед загрузкой нового проекта (Этап 7)"""
        all_uuids = list(self._sub_windows.keys()) + list(self._widgets.keys())
        for uuid_str in set(all_uuids):
            # При полном сбросе проекта из State удалять по одному не нужно,
            # так как State сожгут целиком через дефолтный шаблон.
            self.unregister_and_destroy(uuid_str, unregister_from_state=False)

        self._widgets.clear()
        self._sub_windows.clear()