import logging
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedLayout,

    QVBoxLayout,
    QWidget,
    QLabel
)

from tabs.file_tab import FileTab
from tabs.mic_tab import MicTab
from widgets.log_widget import LogWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Channel Audio Visualizer")
        self.setMinimumSize(950, 500)
        main_layout = QVBoxLayout()
        
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)

        tabs.addTab(FileTab(), "file")
        tabs.addTab(MicTab(), "mic")

        # Add the log widget at the bottom
        self.log_widget = LogWidget()
        
        main_layout.addWidget(tabs)
        main_layout.addWidget(self.log_widget)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        
        logging.info("Application started.")

def main():
    app = QApplication(sys.argv)
    
    # Optional: Apply native window styles adjustments if any
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
