"""Application entry point."""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from main_window import MainWindow
from resources import ICON_PATH


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
