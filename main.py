"""Punto de entrada para la aplicación Genome Annotation Studio con PyQt5."""

import sys
from PyQt5.QtWidgets import QApplication
from app.views.main_window import MainWindow

def main():
    """Inicializa QApplication, crea la ventana principal y entra al loop de eventos."""
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
