from ...libraries import *
from ...patterns_ui import Ui_Form_gallery
from .widgets import WidgetsWindow


class GalleryWindow(WidgetsWindow):

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.setWindowFlag(Qt.WindowType.Window)

        self.ui = Ui_Form_gallery()
        self.ui.setupUi(self)

        self.setWindowTitle(name)