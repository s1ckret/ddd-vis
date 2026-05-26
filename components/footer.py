from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt

class FooterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # Setup vertical arrangement to house a top divider and the status label
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Simple status text label
        self.lbl_status = QLabel("Ready. Select microphone or WAV file to begin.")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        layout.addWidget(self.lbl_status)
        
        # Add a subtle frame boundary style for separation
        self.setFrameStyle(True)

    def setFrameStyle(self, show_border=True):
        """Helper to style the widget with standard desktop framing."""
        if show_border:
            # We can use QSS for a standard top border
            self.setStyleSheet("FooterWidget { border-top: 1px solid #c0c0c0; }")
        else:
            self.setStyleSheet("")

    def set_status(self, message: str, is_error: bool = False):
        """Update the displayed status text. Error messages are prefixed for clarity."""
        if is_error:
            self.lbl_status.setText(f"ERROR: {message}")
            self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.lbl_status.setText(message)
            self.lbl_status.setStyleSheet("color: black; font-weight: normal;")
