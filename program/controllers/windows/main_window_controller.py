from PyQt6 import QtWidgets
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QAction
from PyQt6.QtCore import Qt
import re  # Импортируем для поиска номеров в именах элементов

from ...gui.windows import Ui_MainWindow
from ...state.project_state.state import ProjectState

# Импортируем контроллеры
from .add_controllers.project_io_controller import ProjectIOController
from .add_controllers.widget_factory_controller import WidgetFactoryController
from .add_controllers.hierarchy_controller import HierarchyController
from .add_controllers.interface_controller import InterfaceController


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # 1. Системные переменные приложения
        self.folder_count = 1
        self.gallery_count = 1
        self.graph_count = 1
        self.table_count = 1
        self.app_name = 'OCT project'
        self._close_requested_after_save: bool | None = None

        # 2. Инициализация State и реакция на него
        self.project_state = ProjectState()
        self.project_state.sig_modified_changed.connect(self.update_window_title)
        self.project_state.sig_project_path_changed.connect(self.update_window_title)
        self.project_state.sig_data_reset.connect(self._on_project_reset)

        # 3. Настройка компонентов дерева (Паттерн Model/View)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Project tree"])
        self.file_info.setModel(self.tree_model)

        # 4. ВНЕДРЕНИЕ КОНТРОЛЛЕРОВ
        self.io_controller = ProjectIOController(self, self.project_state)
        self.widget_factory = WidgetFactoryController(self, self.project_state)
        self.hierarchy_controller = HierarchyController(self, self.project_state)
        self.interface_controller = InterfaceController(self, self.project_state, self.widget_factory)

        # 5. Хоткеи и периферия интерфейса
        self._setup_shortcuts()

        # 6. Стартовое состояние
        self._on_project_reset()

    def _setup_shortcuts(self):
        """Вынесенная настройка клавиатурных сокращений."""
        self.delete_action = QAction(self)
        self.delete_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.delete_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.delete_action.triggered.connect(self.hierarchy_controller.on_delete_shortcut_triggered)
        self.file_info.addAction(self.delete_action)

    def update_window_title(self):
        path = self.project_state.current_path
        project_name = path.name if path else "New project"
        marker = " *" if self.project_state.modified else ""
        self.setWindowTitle(f"[{project_name}]{marker} — {self.app_name}")

    def clear_mdi_area_safely(self):
        """Безопасно уничтожает MDI окна без вызова побочных эффектов."""
        for sub_window in self.widgets_area.subWindowList():
            widget = sub_window.widget()
            if widget:
                # === ИСПРАВЛЕНИЕ: Добавляем флаг тихого закрытия ===
                if hasattr(widget, '_force_close'):
                    widget._force_close = True
                # ===================================================

                if hasattr(widget, 'window_closed'):
                    try:
                        widget.window_closed.disconnect()
                    except TypeError:
                        pass

            sub_window.close()
            sub_window.deleteLater()

    def _on_project_reset(self):
        """Вызывается при полной очистке/создании нового проекта."""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Project Files"])

        # Безопасная очистка окон
        self.clear_mdi_area_safely()

        # ==================== ИСПРАВЛЕНИЕ ЗДЕСЬ ====================
        # Принудительно очищаем внутренние реестры окон в контроллерах,
        # чтобы в них не оставалось ссылок на уничтоженные C++ объекты.
        # (Замените 'opened_windows' на реальные имена словарей/списков в ваших контроллерах)
        if hasattr(self.widget_factory, 'opened_windows'):
            self.widget_factory.opened_windows.clear()
        if hasattr(self.hierarchy_controller, 'opened_windows'):
            self.hierarchy_controller.opened_windows.clear()
        # ===========================================================

        self.folder_count = 1
        self.gallery_count = 1
        self.graph_count = 1
        self.table_count = 1

        if not self.project_state.project_data.get("hierarchy"):
            init_folder = self.widget_factory.create_folder("Folder 0")
            self.file_info.setCurrentIndex(self.tree_model.indexFromItem(init_folder))

        self.project_state.set_modified(False)
        self.update_window_title()

    def closeEvent(self, event):
        """
        Перехватывает закрытие программы.
        Реализует трехкнопочный диалог: Yes (Сохранить), No (Не сохранять), Cancel (Отмена)
        с учетом фонового асинхронного сохранения.
        """
        # Если проект НЕ изменен (или мы закрываемся ПОВТОРНО после успешного сохранения)
        if not getattr(self.project_state, 'modified', False):
            # Выполняем финальный пайплайн очистки
            if hasattr(self, 'io_controller'):
                self.io_controller.close_all_windows_silently()

            if hasattr(self.project_state, 'project_reader') and self.project_state.project_reader:
                try:
                    self.project_state.project_reader.close()
                except:
                    pass

            event.accept()  # Закрываем программу
            return

        # Если изменения есть, показываем классический трехкнопочный диалог
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The current project has unsaved changes. Do you want to save changes before exiting?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes  # Кнопка по умолчанию
        )

        # Сценарий 1: Отмена — просто остаемся в программе
        if reply == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return

        # Сценарий 2: Выйти без сохранения
        elif reply == QMessageBox.StandardButton.No:
            # Принудительно сбрасываем флаг modified, чтобы повторный вызов close() прошел без вопросов
            self.project_state.set_modified(False)

            if hasattr(self, 'io_controller'):
                self.io_controller.close_all_windows_silently()

            if hasattr(self.project_state, 'project_reader') and self.project_state.project_reader:
                try:
                    self.project_state.project_reader.close()
                except:
                    pass

            event.accept()
            return

        # Сценарий 3: Сохранить и выйти
        elif reply == QMessageBox.StandardButton.Yes:
            # Взводим флаг: "Когда фоновый поток закончит сохранение, нужно закрыть приложение"
            self._close_requested_after_save = True

            # Запускаем сохранение (методы теперь возвращают True, если процесс пошел,
            # и False, если пользователь нажал Отмена в QFileDialog)
            save_started = self.io_controller.on_save_project()

            if not save_started:
                # Если пользователь передумал на этапе выбора папки, сбрасываем флаг закрытия
                self._close_requested_after_save = False

            # В любом случае ИГНОРИРУЕМ текущее событие закрытия.
            # Окно закроется позже автоматически из недр IO-контроллера.
            event.ignore()
            return
