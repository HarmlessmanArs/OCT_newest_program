from ..base_widget import BaseProjectWidget
from ...windows.ui_graphic_window import Ui_Form_graph


class GraphWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_graph()
        self.ui.setupUi(self)