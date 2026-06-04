from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog

from ..project_storage.io.saver import SaveProjectWorker
from ..project_storage.io.loader import LoadProjectWorker


class ProjectLifecycleController(QObject):
    """
    Оркестратор жизненного цикла проекта (Этапы 7 и 8).
    Управляет потоками ввода-вывода (I/O). Сборка UI делегирована InterfaceController.
    """

    project_loaded = pyqtSignal(str)
    project_saved = pyqtSignal(str)

    def __init__(self, main_window, project_state):
        super().__init__(main_window)
        self.win = main_window
        self.state = project_state
        self._save_worker = None
        self._load_worker = None
        self.progress_dialog = None

    # =========================================================================
    # ТРАКТ СОХРАНЕНИЯ ПРОЕКТА
    # =========================================================================

    def save_project(self, target_path: str | Path = None):
        if not target_path:
            target_path = getattr(self.win, "current_project_path", None)

        if not target_path:
            path_str, _ = QFileDialog.getSaveFileName(
                self.win, "Save Project", "", "BMIP Project (*.bmip)"
            )
            if not path_str:
                return
            target_path = Path(path_str)

        self.win.current_project_path = Path(target_path)

        # 1. Заставляем InterfaceController скинуть геометрию окон в State
        if hasattr(self.win, 'interface_controller'):
            self.win.interface_controller.save_workspace_geometry_to_state()

        # 2. Только теперь берем слепок
        project_snapshot = self.state.get_complete_snapshot()

        self._create_progress_dialog("Saving project...", "Please wait...")

        self._save_worker = SaveProjectWorker(target_path, project_snapshot)
        self._save_worker.progress.connect(self.progress_dialog.setValue)
        self._save_worker.work_finished.connect(self._on_save_finished)
        self._save_worker.start()

    def _on_save_finished(self, success: bool, message: str):
        if self.progress_dialog:
            self.progress_dialog.close()

        if success:
            self.state.set_modified(False)
            self.project_saved.emit(str(self.win.current_project_path))
            self.win.statusBar().showMessage("Project successfully saved.", 3000)
        else:
            QMessageBox.critical(self.win, "Save Error", f"Failed to save project:\n{message}")

        self._save_worker = None

    # =========================================================================
    # ТРАКТ ЗАГРУЗКИ (Только I/O и Гидратация)
    # =========================================================================

    def load_project(self, file_path: str | Path = None):
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

        self._load_worker = LoadProjectWorker(file_path)
        self._load_worker.progress.connect(self.progress_dialog.setValue)
        self._load_worker.work_finished.connect(self._on_load_finished)
        self._load_worker.start()

    def _on_load_finished(self, success: bool, snapshot_or_error, reader_instance):
        if self.progress_dialog:
            self.progress_dialog.close()

        if not success:
            QMessageBox.critical(self.win, "Load Error", f"Critical read error:\n{snapshot_or_error}")
            self._load_worker = None
            return

        # 1. ЗАЩИТА: Блокируем реактивность State
        self.state.blockSignals(True)

        try:
            # 2. ГИДРАТАЦИЯ СЛОЯ ДАННЫХ (Без UI!)
            self.state.hydrate_from_snapshot(snapshot_or_error, reader_instance)
        finally:
            self.state.blockSignals(False)

        # 3. ЭМИТИРУЕМ СИГНАЛ -> InterfaceController поймает его и построит UI
        self.state.sig_project_loaded.emit()

        self._load_worker = None

        # 4. Финальные статусы приложения
        try:
            if hasattr(self.win, 'hierarchy_controller'):
                self.win.hierarchy_controller.ensure_active_folder_selection()
            self.state.set_modified(False)
            self.project_loaded.emit(str(self.win.current_project_path))
        except Exception as e:
            print(f"Ошибка финальной фокусировки дерева: {e}")

    def _create_progress_dialog(self, title: str, label: str):
        self.progress_dialog = QProgressDialog(label, None, 0, 100, self.win)
        self.progress_dialog.setWindowTitle(title)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()