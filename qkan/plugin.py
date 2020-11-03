import logging
from typing import cast

from qgis.PyQt.QtCore import QCoreApplication
from qgis.gui import QgisInterface


class QKanPlugin:
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self.log = logging.getLogger(f"QKan.{type(self).__name__}")

        self.log.info("Initialised.")

    # noinspection PyMethodMayBeStatic
    def tr(self, message: str) -> str:
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return cast(str, QCoreApplication.translate(type(self).__name__, message))

    def unload(self):
        """
        Override this if you initialized a QDialog anywhere
        """
