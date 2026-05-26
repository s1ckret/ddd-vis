import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel
from PyQt6.QtCore import QObject, pyqtSignal, Qt

# 1. The custom handler that bridges logging and Qt
class LogHandler(logging.Handler, QObject):
    # Define a signal to send the log message to the UI thread
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)

# 2. The UI component
class LogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Header with toggle button
        header_layout = QHBoxLayout()
        self.toggle_btn = QPushButton("Show Logs ▾")
        self.toggle_btn.clicked.connect(self.toggle_logs)
        self.status_label = QLabel("Ready")
        
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()
        header_layout.addWidget(self.toggle_btn)

        # Log Area
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setMaximumHeight(200)
        self.text_area.hide()

        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.text_area)

        # Setup Logging
        self.handler = LogHandler()
        self.handler.log_signal.connect(self.update_log_ui)
        logging.getLogger().addHandler(self.handler)
        logging.getLogger().setLevel(logging.INFO)

    def update_log_ui(self, message):
        self.status_label.setText(message)
        self.text_area.append(message)

    def toggle_logs(self):
        is_visible = self.text_area.isVisible()
        self.text_area.setVisible(not is_visible)
        self.toggle_btn.setText("Hide Logs ▴" if not is_visible else "Show Logs ▾")