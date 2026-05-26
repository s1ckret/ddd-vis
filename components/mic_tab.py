import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtCore import Qt

from audio.mic_manager import MicAudioManager
from components.chart import MultiChannelChart

class MicTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize specialized audio manager
        self.audio_manager = MicAudioManager()
        
        self.init_ui()
        self._connect_signals()
        
        # Initial populate
        self.refresh_mic_list()

    def init_ui(self):
        # Vertical arrangement layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # 1. Controls Bar (Horizontal layout)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        self.lbl_mic = QLabel("Microphone:")
        self.combo_mic = QComboBox()
        self.combo_mic.setMinimumWidth(250)
        self.btn_refresh = QPushButton("Refresh")
        
        controls_layout.addWidget(self.lbl_mic)
        controls_layout.addWidget(self.combo_mic)
        controls_layout.addWidget(self.btn_refresh)

        # Push media buttons to the right-hand side
        controls_layout.addStretch(1)

        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")

        self.btn_start.setMinimumWidth(75)
        self.btn_pause.setMinimumWidth(75)
        self.btn_stop.setMinimumWidth(75)

        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_stop)
        layout.addLayout(controls_layout)

        # 2. Level Oscilloscope Chart
        self.chart = MultiChannelChart(self)
        layout.addWidget(self.chart, 1)  # Expand chart vertically

        # 3. Dedicated Tab Footer Status line
        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setStyleSheet("border-top: 1px solid #c0c0c0; padding-top: 4px;")
        layout.addWidget(self.lbl_status)

    def _connect_signals(self):
        # Connect buttons to stream operations
        self.btn_start.clicked.connect(self.audio_manager.play)
        self.btn_pause.clicked.connect(self.audio_manager.pause)
        self.btn_stop.clicked.connect(self.audio_manager.stop)
        self.btn_refresh.clicked.connect(self.refresh_mic_list)
        
        # Connect microphone combo selection changes
        self.combo_mic.currentIndexChanged.connect(self.on_device_changed)

        # Connect audio signals to chart and status label
        self.audio_manager.levels_updated.connect(self.chart.update_levels)
        self.audio_manager.status_changed.connect(self.on_status_changed)

    def refresh_mic_list(self):
        """Query system devices and reload dropdown options."""
        devices = self.audio_manager.get_input_devices()
        
        self.combo_mic.blockSignals(True)
        self.combo_mic.clear()
        
        if not devices:
            self.combo_mic.addItem("No input microphones found", -1)
            self.combo_mic.setEnabled(False)
            self.combo_mic.blockSignals(False)
            self.on_status_changed("No microphones detected.", False)
            return

        self.combo_mic.setEnabled(True)
        for idx, name, chans in devices:
            self.combo_mic.addItem(f"{name} ({chans} ch)", idx)
            
        self.combo_mic.blockSignals(False)
        
        # Select first option by default
        if self.combo_mic.count() > 0:
            self.on_device_changed(self.combo_mic.currentIndex())

        self.on_status_changed("Microphone list refreshed.", False)

    def on_device_changed(self, index):
        """Pass the selected audio device index to the manager."""
        if index >= 0:
            device_id = self.combo_mic.itemData(index)
            self.audio_manager.set_selected_device_id(device_id)

    def on_status_changed(self, message, is_error=False):
        """Update tab footer status text and output log prefix in console."""
        if is_error:
            self.lbl_status.setText(f"ERROR: {message}")
            self.lbl_status.setStyleSheet("border-top: 1px solid #c0c0c0; padding-top: 4px; color: red; font-weight: bold;")
            print(f"[ERROR] [Mic] {message}", file=sys.stderr, flush=True)
        else:
            self.lbl_status.setText(message)
            self.lbl_status.setStyleSheet("border-top: 1px solid #c0c0c0; padding-top: 4px; color: black; font-weight: normal;")
            print(f"[INFO] [Mic] {message}", flush=True)

    def stop(self):
        """Safely stops active mic stream and resets chart visualization."""
        self.audio_manager.stop()
        self.chart.reset_chart()
