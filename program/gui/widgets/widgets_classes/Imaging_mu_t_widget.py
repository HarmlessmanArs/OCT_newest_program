from ..base_widget import BaseProjectWidget
from ...windows.ui_imaging_mu_t_window import Ui_Form_img_mu_t


class MuTWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_mu_t()
        self.ui.setupUi(self)