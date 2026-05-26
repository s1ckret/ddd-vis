import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog
from PyQt6.QtCore import Qt

from audio.file_manager import FileAudioManager
from components.chart import MultiChannelChart

class FileTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize specialized audio manager
        self.audio_manager = FileAudioManager()
        
        self.init_ui()
        self._connect_signals()

    def init_ui(self):
        # Vertical arrangement layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # 1. Controls Bar (Horizontal layout)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        self.lbl_file = QLabel("WAV File:")
        self.line_file = QLineEdit()
        self.line_file.setReadOnly(True)
        self.line_file.setMinimumWidth(250)
        self.btn_browse = QPushButton("Browse...")
        
        controls_layout.addWidget(self.lbl_file)
        controls_layout.addWidget(self.line_file)
        controls_layout.addWidget(self.btn_browse)

        # Push media buttons to the right-hand side
        controls_layout.addStretch(1)

        self.btn_play = QPushButton("Play")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")

        self.btn_play.setMinimumWidth(75)
        self.btn_pause.setMinimumWidth(75)
        self.btn_stop.setMinimumWidth(75)

        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_stop)
        layout.addLayout(controls_layout)

        # 2. Level Oscilloscope Chart
        self.chart = MultiChannelChart(self)
        layout.addWidget(self.chart, 1)  # Expand chart vertically

        # 3. Dedicated Tab Footer Status line
        self.lbl_status = QLabel("Ready. Please browse and open a WAV file to play.")
        self.lbl_status.setStyleSheet("border-top: 1px solid #c0c0c0; padding-top: 4px;")
        layout.addWidget(self.lbl_status)

    def _connect_signals(self):
        # Connect buttons to stream operations
        self.btn_play.clicked.connect(self.audio_manager.play)
        self.btn_pause.clicked.connect(self.audio_manager.pause)
        self.btn_stop.clicked.connect(self.audio_manager.stop)
        self.btn_browse.clicked.connect(self.on_browse_file)

        # Connect audio signals to chart and status label
        self.audio_manager.levels_updated.connect(self.chart.update_levels)
        self.audio_manager.status_changed.connect(self.on_status_changed)

    def on_browse_file(self):
        """Browse and select a WAV file from system explorer."""
        self.chart.reset_chart()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Audio File", 
            "", 
            "WAV Audio Files (*.wav)"
        )
        if file_path:
            self.line_file.setText(file_path)
            self.audio_manager.load_wav(file_path)

    def on_status_changed(self, message, is_error=False):
        """Update tab footer status text and output log prefix in console."""
        if is_error:
            self.lbl_status.setText(f"ERROR: {message}")
            self.lbl_status.setStyleSheet("border-top: 1px solid #c0c0c0; padding-top: 4px; color: red; font-weight: bold;")
            print(f"[ERROR] [File] {message}", file=sys.stderr, flush=True)
        else:
            self.lbl_status.setText(message)
            self.lbl_status.setStyleSheet("border-top: 1px solid #c0c0c0; padding-top: 4px; color: black; font-weight: normal;")
            print(f"[INFO] [File] {message}", flush=True)

    def stop(self):
        """Safely stops active playback stream and resets chart visualization."""
        self.audio_manager.stop()
        self.chart.reset_chart()
