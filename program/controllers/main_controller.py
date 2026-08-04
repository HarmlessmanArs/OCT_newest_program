# program/controllers/main_controller.py
from pathlib import Path
from PyQt6.QtWidgets import QMainWindow, QMdiSubWindow, QMenu, QFileDialog, QMessageBox
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from ..gui.windows.ui_main_window import Ui_MainWindow
from ..core.events import bus
from ..core.state import state
from .tree_controller import TreeController
from ..state.user_settings_state import UserSettingsState
from ..state.temp_manager import TempWorkspace

# --- Новая архитектура Ввода/Вывода (I/O) ---
from ..io.project_manager import ProjectManager
from ..io.saver import SaveProjectWorker
from ..io.loader import LoadProjectWorker


class MainController(QMainWindow):
    def __init__(self, settings: UserSettingsState, temp_workspace: TempWorkspace):
        super().__init__()

        self.settings = settings
        self.temp_workspace = temp_workspace

        # Инициализируем главный менеджер I/O
        self.project_manager = ProjectManager(self.temp_workspace)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Словарь открытых окон {uid: QMdiSubWindow}
        self.active_mdi_windows = {}

        # Ссылка на активный фоновый поток (защита от сборщика мусора)
        self._current_worker = None

        self._setup_ui()
        self._setup_connections()
        self._subscribe_to_events()

        # Принудительно стартуем чистый проект при запуске программы
        self.on_new_project()

    def _setup_ui(self):
        """Настройка дополнительных элементов UI"""
        # --- Инициализация нашего контроллера дерева ---
        self.tree_controller = TreeController(self.ui.file_info)

        # --- Скрывающаяся боковая панель (file_info) ---
        self.toggle_sidebar_action = QAction("Show/Hide Explorer", self)
        self.toggle_sidebar_action.setShortcut("Ctrl+B")
        self.toggle_sidebar_action.triggered.connect(self.toggle_sidebar)
        self.addAction(self.toggle_sidebar_action)
        if hasattr(self.ui, 'menuFile'):
            self.ui.menuFile.addAction(self.toggle_sidebar_action)

        # --- Контекстное меню для MDI-области (ПКМ) ---
        self.ui.widgets_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.widgets_area.customContextMenuRequested.connect(self._show_mdi_context_menu)

    def toggle_sidebar(self):
        """Показывает или скрывает QTreeView (file_info)"""
        is_visible = self.ui.file_info.isVisible()
        self.ui.file_info.setVisible(not is_visible)

    def _setup_connections(self):
        """Подключение кнопок из menubar к методам с учетом точных имен из UI"""
        # Меню File
        if hasattr(self.ui, 'actionNew'):
            self.ui.actionNew.triggered.connect(self.on_new_project)
        if hasattr(self.ui, 'actionOpen'):
            self.ui.actionOpen.triggered.connect(self.on_open_project)
        elif hasattr(self.ui, 'actionOpen_project'):
            self.ui.actionOpen_project.triggered.connect(self.on_open_project)

        if hasattr(self.ui, 'actionSave'):
            self.ui.actionSave.triggered.connect(self.on_save_project)
        elif hasattr(self.ui, 'actionSave_project'):
            self.ui.actionSave_project.triggered.connect(self.on_save_project)

        if hasattr(self.ui, 'actionSave_as'):
            self.ui.actionSave_as.triggered.connect(self.on_save_project_as)

        if hasattr(self.ui, 'actionQuit'):
            self.ui.actionQuit.triggered.connect(self.close)

        # Меню Instruments & Settings
        if hasattr(self.ui, 'actionCreate_new_gallery'):
            self.ui.actionCreate_new_gallery.triggered.connect(self.on_create_gallery)
        if hasattr(self.ui, 'actionTMP_path'):
            self.ui.actionTMP_path.triggered.connect(self.on_change_temp_path)

    def _subscribe_to_events(self):
        """Подписка на глобальную шину событий"""
        bus.request_open_widget.connect(self._handle_open_widget)
        bus.node_removed.connect(self._handle_node_removed)
        bus.project_modified.connect(self._update_window_title)
        bus.active_widget_changed.connect(self._handle_active_widget_changed)

    # =========================================================================
    # ЛОГИКА УПРАВЛЕНИЯ ПРОЕКТОМ (NEW, OPEN, SAVE)
    # =========================================================================

    def on_new_project(self):
        """Сброс состояния при создании нового проекта"""
        if not self._check_unsaved_changes():
            return

        # Очищаем визуальные MDI-окна
        self._close_all_mdi_windows()

        # Сбрасываем временную папку и ядро проекта
        self.temp_workspace.reset()
        state.reset()

        # Обновляем заголовок
        self._update_window_title(False)
        self.statusBar().showMessage("Создан новый проект", 3000)

    def on_save_project(self):
        """Сохранение проекта (Ctrl+S)"""
        if not state.filepath or state.filepath == "[New Project]":
            self.on_save_project_as()
        else:
            self._start_save_worker(state.filepath)

    def on_save_project_as(self):
        """Сохранение проекта с выбором пути (Save As)"""
        # Читаем последний путь из настроек
        start_path = str(self.settings.last_save_project_folder)

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект ОКТ",
            start_path,
            "ОКТ Проект (*.bmip);;Все файлы (*.*)"
        )

        if filepath:
            # Запоминаем папку, в которую сохранили файл, и обновляем settings.json
            self.settings.last_save_project_folder = Path(filepath).parent
            self.settings.save()

            self._start_save_worker(filepath)

    def on_open_project(self):
        """Открытие файла проекта .bmip"""
        if not self._check_unsaved_changes():
            return

        # Читаем последний путь из настроек
        start_path = str(self.settings.last_open_folder)

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект ОКТ",
            start_path,
            "ОКТ Проект (*.bmip);;Все файлы (*.*)"
        )

        if filepath:
            # Запоминаем папку, откуда открыли файл, и обновляем settings.json
            self.settings.last_open_folder = Path(filepath).parent
            self.settings.save()

            self._start_load_worker(filepath)

    # =========================================================================
    # ВОРКЕРЫ ПОТОКОВ (ASYNC I/O)
    # =========================================================================

    def _start_save_worker(self, target_filepath: str):
        """Запуск фонового потока сохранения"""
        self.statusBar().showMessage("Сохранение проекта...")

        self._current_worker = SaveProjectWorker(state, target_filepath, self.project_manager)
        self._current_worker.work_finished.connect(self._on_save_finished)
        self._current_worker.progress.connect(lambda p: self.statusBar().showMessage(f"Сохранение... {p}%"))
        self._current_worker.start()

    def _on_save_finished(self, success: bool, error_message: str):
        """Обработка завершения сохранения"""
        if success:
            self.statusBar().showMessage("Проект успешно сохранен", 4000)
            self._update_window_title(False)
        else:
            self.statusBar().showMessage("Ошибка сохранения!", 4000)
            QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось сохранить проект:\n{error_message}")

        self._current_worker = None

    def _start_load_worker(self, source_filepath: str):
        """Запуск фонового потока загрузки"""
        self.statusBar().showMessage("Загрузка проекта...")
        self._close_all_mdi_windows()

        self._current_worker = LoadProjectWorker(state, source_filepath, self.project_manager)
        self._current_worker.work_finished.connect(self._on_load_finished)
        self._current_worker.progress.connect(lambda p: self.statusBar().showMessage(f"Загрузка... {p}%"))
        self._current_worker.start()

    def _on_load_finished(self, success: bool, error_message: str):
        """Обработка завершения загрузки"""
        if success:
            self.statusBar().showMessage("Проект успешно загружен", 4000)
            self._update_window_title(False)

            # 1. Сигнализируем о "новом" проекте (TreeController очистит старые элементы)
            bus.project_created.emit()

            # 2. Заставляем дерево перерисовать все загруженные из файла узлы
            for uid in state.nodes:
                bus.node_added.emit(uid)
        else:
            self.statusBar().showMessage("Ошибка загрузки!", 4000)
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось открыть проект:\n{error_message}")

        self._current_worker = None

    # =========================================================================
    # СОЗДАНИЕ УЗЛОВ И РАБОТА С ГАЛЕРЕЯМИ
    # =========================================================================

    def on_create_gallery(self):
        """Создание новой пустой галереи внутри выбранной папки"""
        parent_uid = None

        # 1. Пытаемся получить выделенный элемент из дерева
        selection = self.ui.file_info.selectionModel().selectedIndexes()
        if selection:
            index = selection[0]
            item = self.tree_controller.model.itemFromIndex(index)
            selected_uid = item.data(Qt.ItemDataRole.UserRole)

            node = state.get_node(selected_uid)
            if node:
                parent_uid = node.uid if node.node_type == "folder" else node.parent_uid

        # 2. Если ничего не выделено, берем первую папку
        if not parent_uid:
            folders = [uid for uid, n in state.nodes.items() if n.node_type == "folder"]
            if folders:
                parent_uid = folders[0]
            else:
                new_folder = state.add_node(name="Dataset", node_type="folder")
                parent_uid = new_folder.uid

        # 3. Создаем галерею
        new_node = state.add_node(name="New Gallery", node_type="gallery", parent_uid=parent_uid)

        # 4. Открываем виджет
        bus.request_open_widget.emit(new_node.uid)

    def on_create_folder(self):
        """Пользователь запросил создание новой папки"""
        state.add_node("Dataset", "folder")

    def _show_mdi_context_menu(self, pos):
        """Создает и показывает контекстное меню по правому клику в MDI области"""
        context_menu = QMenu(self)

        action_new_folder = QAction("Create new folder", self)
        action_new_gallery = QAction("Create new gallery", self)

        action_new_folder.triggered.connect(self.on_create_folder)
        action_new_gallery.triggered.connect(self.on_create_gallery)

        context_menu.addAction(action_new_folder)
        context_menu.addAction(action_new_gallery)
        context_menu.exec(self.ui.widgets_area.mapToGlobal(pos))

    # =========================================================================
    # УПРАВЛЕНИЕ ОКНАМИ В MDI (OriginPro Style)
    # =========================================================================

    def _update_mdi_visibility(self, active_folder_uid: str):
        """Оставляет видимыми только те окна, которые принадлежат к выбранной папке"""
        for uid, sub_window in self.active_mdi_windows.items():
            node = state.get_node(uid)
            if not node:
                continue

            if node.parent_uid == active_folder_uid:
                sub_window.show()
                sub_window.raise_()
                sub_window.activateWindow()
            else:
                sub_window.hide()

    def _handle_open_widget(self, node_uid: str):
        """Открытие MDI окна (когда мы кликаем по галерее в дереве)"""
        node = state.get_node(node_uid)
        if not node:
            return

        if node_uid in self.active_mdi_windows:
            sub = self.active_mdi_windows[node_uid]
            sub.show()
            sub.raise_()
            sub.activateWindow()
            sub.setFocus()
            return

        from program.gui.widgets.factory import WidgetFactory

        widget = WidgetFactory.create(node.node_type, node.uid)
        sub_window = self.ui.widgets_area.addSubWindow(widget)

        sub_window.resize(widget.minimumSize().width() + 20,
                          widget.minimumSize().height() + 40)

        sub_window.setWindowTitle(node.name)
        sub_window.show()

        self.active_mdi_windows[node_uid] = sub_window

    def _handle_active_widget_changed(self, uid: str):
        """Обработка одинарного клика в дереве для фильтрации окон"""
        node = state.get_node(uid)
        if not node:
            return
        if node.node_type == "folder":
            self._update_mdi_visibility(uid)
        elif node.parent_uid:
            self._update_mdi_visibility(node.parent_uid)

    def _handle_node_removed(self, node_uid: str):
        """Гарантированное уничтожение MDI окна при удалении узла"""
        if node_uid in self.active_mdi_windows:
            sub_window = self.active_mdi_windows.pop(node_uid)
            try:
                sub_window.close()
                sub_window.deleteLater()
            except RuntimeError:
                pass

    def _update_window_title(self, is_modified: bool):
        """Обновление заголовка с правильной обработкой [*]"""
        project_name = state.filepath if state.filepath else "[New Project]"
        self.setWindowTitle(f"OCT Image Processing - {project_name}[*]")
        self.setWindowModified(is_modified)

    # =========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ И НАСТРОЙКИ
    # =========================================================================

    def _check_unsaved_changes(self) -> bool:
        """Проверка наличия несохраненных изменений"""
        if state.is_modified:
            reply = QMessageBox.question(
                self,
                "Несохраненные изменения",
                "В текущем проекте есть несохраненные изменения. Сохранить их перед продолжением?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if reply == QMessageBox.StandardButton.Save:
                self.on_save_project()
                return not state.is_modified
            elif reply == QMessageBox.StandardButton.Cancel:
                return False

        return True

    def _close_all_mdi_windows(self):
        """Безопасное закрытие всех sub-window в MDI зоне"""
        for sub_window in list(self.active_mdi_windows.values()):
            try:
                sub_window.close()
                sub_window.deleteLater()
            except RuntimeError:
                pass
        self.active_mdi_windows.clear()

    def on_change_temp_path(self):
        """Обработчик выбора рабочей временной папки (Scratch Disk)"""
        current_path = str(self.settings.workspace_temp_folder) if self.settings.workspace_temp_folder else str(Path.home())

        new_dir = QFileDialog.getExistingDirectory(
            self,
            "Выберите диск/папку для временных файлов (Scratch Disk)",
            current_path
        )

        if new_dir:
            self.settings.workspace_temp_folder = Path(new_dir)
            self.settings.save()