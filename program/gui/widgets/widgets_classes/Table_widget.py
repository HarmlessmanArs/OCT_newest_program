from ..base_widget import BaseProjectWidget
from ...windows.ui_table_window import Ui_Form_table


class TableWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_table()
        self.ui.setupUi(self)