from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog
from PyQt6.QtGui import QStandardItem

from ..project_storage.io.saver import SaveProjectWorker
from ..project_storage.io.loader import LoadProjectWorker


class ProjectLifecycleController(QObject):
    """
    Оркестратор жизненного цикла проекта (Этапы 7 и 8).
    Управляет потоками ввода-вывода (I/O) и координирует полную регенерацию UI из State.
    """

    # Сигналы для уведомления других систем (например, для изменения заголовка окна)
    project_loaded = pyqtSignal(str)  # Передает путь к открытому файлу
    project_saved = pyqtSignal(str)

    def __init__(self, main_window, project_state):
        super().__init__(main_window)
        self.win = main_window
        self.state = project_state

        # Ссылки на фоновые воркеры
        self._save_worker = None
        self._load_worker = None

        # Индикатор прогресса для долгих дисковых операций
        self.progress_dialog = None

    # =========================================================================
    # ТРАКТ СОХРАНЕНИЯ ПРОЕКТА
    # =========================================================================

    def save_project(self, target_path: str | Path = None):
        """Собирает snapshot из ProjectState и отправляет его на запись в поток."""
        if not target_path:
            target_path = getattr(self.win, "current_project_path", None)

        if not target_path:
            # Если проект новый — открываем диалог сохранения
            path_str, _ = QFileDialog.getSaveFileName(
                self.win, "Save Project", "", "BMIP Project (*.bmip)"
            )
            if not path_str:
                return
            target_path = Path(path_str)

        self.win.current_project_path = Path(target_path)

        # 1. Запрашиваем чистый снимок данных из нашего State
        # Сюда входят project_meta, tree_structure (иерархия) и блоки данных
        project_snapshot = self.state.get_complete_snapshot()

        # 2. Инициализируем диалог прогресса
        self._create_progress_dialog("Saving project...", "Please wait...")

        # 3. Запускаем ваш SaveProjectWorker в ОПЕРАТИВНОМ ПОТОКЕ
        self._save_worker = SaveProjectWorker(target_path, project_snapshot)
        self._save_worker.progress.connect(self.progress_dialog.setValue)
        self._save_worker.finished.connect(self._on_save_finished)
        self._save_worker.start()

    def _on_save_finished(self, success: bool, message: str):
        """Коллбэк завершения сохранения."""
        if self.progress_dialog:
            self.progress_dialog.close()

        if success:
            self.state.set_modified(False)  # Сбрасываем флаг изменений
            self.project_saved.emit(str(self.win.current_project_path))
            self.win.statusBar().showMessage("Project successfully saved.", 3000)
        else:
            QMessageBox.critical(self.win, "Save Error", f"Failed to save project:\n{message}")

        self._save_worker = None

    # =========================================================================
    # ТРАКТ ЗАГРУЗКИ И РЕСТАВРАЦИИ (Restoration Service)
    # =========================================================================

    def load_project(self, file_path: str | Path = None):
        """Запускает поток чтения и парсинга файла .bmip."""
        if not file_path:
            path_str, _ = QFileDialog.getOpenFileName(
                self.win, "Open Project", "", "BMIP Project (*.bmip)"
            )
            if not path_str:
                return
            file_path = Path(path_str)

        if self.state.is_modified():
            reply = QMessageBox.question(
                self.win, "Unsaved Changes",
                "The current project has unsaved changes. Do you want to proceed without saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        self.win.current_project_path = Path(file_path)
        self._create_progress_dialog("Loading project...", "Reading Zarr archive...")

        # Запуск вашего фонового LoadProjectWorker
        self._load_worker = LoadProjectWorker(file_path)
        self._load_worker.progress.connect(self.progress_dialog.setValue)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.start()

    def _on_load_finished(self, success: bool, snapshot_or_error, reader_instance):
        """
        Точка сборки (Этап 8). Срабатывает в GUI-потоке, когда диск полностью считан.
        Принимает ленивый snapshot и живой экземпляр ридера Zarr.
        """
        if self.progress_dialog:
            self.progress_dialog.close()

        if not success:
            QMessageBox.critical(self.win, "Load Error", f"Critical read error:\n{snapshot_or_error}")
            self._load_worker = None
            return

        snapshot = snapshot_or_error

        try:
            # === ШАГ 1. ТОТАЛЬНАЯ ЗАЧИСТКА ТЕКУЩЕГО ИНТЕРФЕЙСА ===
            # Вычищаем старые виджеты через реестр без утечек памяти
            self.win.runtime_registry.clear_all()
            # Очищаем визуальное дерево
            self.win.tree_model.clear()
            self.win.tree_model.setHorizontalHeaderLabels(["Project Structure"])

            # === ШАГ 2. ГИДРАТАЦИЯ СТЕЙТА ===
            # Передаем ленивые массивы и метаданные в ProjectState
            # Сохраняем ссылку на открытый reader в стейте, чтобы виджеты могли читать тяжелые кубы по требованию
            self.state.hydrate_from_snapshot(snapshot, reader_instance)

            # === ШАГ 3. ВОССТАНОВЛЕНИЕ ИЕРАРХИИ И ГЕНЕРАЦИЯ ОКOН ===
            # Извлекаем сохраненную структуру дерева (tree_structure)
            tree_data = snapshot.get('tree_structure', {})

            # Рекурсивно строим дерево элементов QStandardItem и спавним окна через фабрику
            self._reconstruct_ui_layer(tree_data, self.win.tree_model.invisibleRootItem())

            # Переводим фокус на первый элемент
            self.win.hierarchy_controller.ensure_active_folder_selection()
            self.state.set_modified(False)
            self.project_loaded.emit(str(self.win.current_project_path))

        except Exception as e:
            QMessageBox.critical(self.win, "Restoration Error", f"Ошибка воссоздания UI-слоя:\n{str(e)}")
        finally:
            self._load_worker = None

    # =========================================================================
    # РЕКУРСИВНЫЙ ОРКЕСТРАТОР РЕСТАВРАЦИИ UI
    # =========================================================================

    def _reconstruct_ui_layer(self, node_data: dict, parent_item):
        """
        Рекурсивный обход древовидной структуры метаданных.
        Восстанавливает логические узлы в QTreeView и дает команду фабрике на материализацию MDI.
        """
        if not node_data:
            return

        # Наш узел (папка или виджет)
        uuid_str = node_data.get("uuid")
        name = node_data.get("text", "Unnamed Node")
        node_type = node_data.get("type")

        if not uuid_str:
            return

        # Если это корневой контейнер верхнего уровня структуры
        if node_type == "root":
            for child_node in node_data.get("children", []):
                self._reconstruct_ui_layer(child_node, parent_item)
            return

        # Нам нужно восстановить элемент дерева
        current_item = None

        if node_type == "folder":
            # Восстанавливаем папку
            current_item = QStandardItem(name)
            current_item.setData(uuid_str, Qt.ItemDataRole.UserRole)
            parent_item.appendRow(current_item)

        elif node_type in ["gallery", "table", "graph"]:
            # Достаем дескриптор виджета из стейта для передачи фабрике
            descriptor = self.state.get_widget_descriptor(uuid_str)
            if descriptor:
                # Даем команду фабрике: "Материализуй окно в ОЗУ, упакуй в MDI и пропиши в реестр"
                self.win.widget_factory.restore_window_from_descriptor(descriptor, parent_item)
                # Фабрика сама добавит элемент в дерево, находим его:
                current_item = self.win.hierarchy_controller.find_item_by_uuid(uuid_str)

        # Идем каскадом вниз по дереву, если у этого узла есть дети (актуально для папок)
        next_parent = current_item if current_item else parent_item
        for child_node in node_data.get("children", []):
            self._reconstruct_ui_layer(child_node, next_parent)

    def _create_progress_dialog(self, title: str, label: str):
        self.progress_dialog = QProgressDialog(label, None, 0, 100, self.win)
        self.progress_dialog.setWindowTitle(title)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()